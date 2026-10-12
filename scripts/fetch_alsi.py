"""LNG send-out per terminal in Europe (GIE ALSI), the last 30 gas days.

GIE ALSI (alsi.gie.eu, the same key as AGSI+: AGSI_API_KEY, sent as the x-key header) lists
every terminal (`/api/about?show=listing`) and serves one row per terminal and gas day with
the terminal's position (scripts/probe_alsi_terminals.py):

  sendOut    gas sent out of the terminal into the grid in the gas day (GWh/d)
  inventory  LNG in the tanks at the end of the gas day (gwh: GWh)
  dtrs       declared total reference send-out (GWh/d): the terminal's declared capacity
  status     GIE's flag per row: C confirmed, E estimated, N no data

Values are passed through at GIE's precision. Left out: terminals not in operation (a start
date in the future, an end date in the past), the Spanish virtual balancing tank (TVB,
country "ES*": an account, not a place) and terminals with no reported send-out in the window
(the British terminals have reported none since Brexit).

Writes frontend/public/data/eu/lng_terminals.json:
  {"fetched", "source", "date" (newest gas day with data),
   "terminals": [{"eic", "name", "type" (LAND|FSRU), "country", "operator", "lon", "lat",
                  "series": [[gas day, send-out GWh/d, in tanks GWh, declared GWh/d, status]]}]}

    uv run python scripts/fetch_alsi.py [--out DIR] [--days 30]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
URL = "https://alsi.gie.eu/api"
SOURCE = "GIE ALSI (Gas Infrastructure Europe, LNG transparency platform), per terminal and gas day"

Row = list  # [gas day, send-out, in tanks, declared send-out, status]


def get(client: httpx.Client, url: str, params: dict) -> dict | list | None:
    for attempt in range(4):
        try:
            r = client.get(url, params=params)
        except httpx.TransportError:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(10 * (attempt + 1))
            continue
        return r.json() if r.status_code == 200 else None
    return None


def num(v: object) -> float | None:
    """GIE's number as given ("136.1"); "-" and blanks are no value."""
    if v in (None, "", "-"):
        return None
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def in_operation(f: dict, today: str) -> bool:
    start = f.get("operational_start_date") or "0000"
    end = f.get("operational_end_date") or "9999"
    return start <= today < end and not str(f.get("country", "")).endswith("*")


def terminal_rows(rows: list[dict]) -> list[Row]:
    """One row per gas day, oldest first, as [day, send-out, in tanks, declared, status]."""
    out = []
    for r in sorted(rows, key=lambda r: r["gasDayStart"]):
        inv = r.get("inventory") if isinstance(r.get("inventory"), dict) else {}
        out.append(
            [
                r["gasDayStart"],
                num(r.get("sendOut")),
                num(inv.get("gwh")),
                num(r.get("dtrs")),
                r.get("status") or None,
            ]
        )
    return out


def terminal(f: dict, operator: str, rows: list[dict]) -> dict | None:
    series = terminal_rows(rows)
    if not any(s[1] is not None for s in series):
        return None
    pos = next((r for r in rows if num(r.get("longitude")) and num(r.get("latitude"))), None)
    if pos is None:
        return None
    return {
        "eic": f["eic"],
        "name": f["name"],
        "type": f.get("type"),
        "country": f["country"],
        "operator": operator,
        "lon": num(pos["longitude"]),
        "lat": num(pos["latitude"]),
        "series": series,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    key = os.environ.get("AGSI_API_KEY", "").strip()
    if not key:
        raise SystemExit("AGSI_API_KEY not set (free at https://agsi.gie.eu/account)")
    client = httpx.Client(timeout=60, headers={"x-key": key})
    listing = get(client, f"{URL}/about", {"show": "listing"})
    if not isinstance(listing, list):
        raise SystemExit("ALSI listing unavailable")
    today = date.today().isoformat()
    since = (date.today() - timedelta(days=args.days + 2)).isoformat()
    terminals: list[dict] = []
    for company in listing:
        for f in company.get("facilities", []):
            if not in_operation(f, today):
                continue
            d = get(
                client,
                URL,
                {
                    "country": f["country"],
                    "company": f["company"],
                    "facility": f["eic"],
                    "from": since,
                    "size": "60",
                },
            )
            rows = (d or {}).get("data", []) if isinstance(d, dict) else []
            t = terminal(f, company.get("short_name") or company["name"], rows)
            print(f"  {f['country']} {f['name']}: {'ok' if t else 'no send-out'}")
            if t:
                t["series"] = t["series"][-args.days :]
                terminals.append(t)
    if not terminals:
        raise SystemExit("no terminal data; keeping the last file")
    newest = max(s[0] for t in terminals for s in t["series"] if s[1] is not None)
    terminals.sort(key=lambda t: (t["country"], t["name"]))
    out = {
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": SOURCE,
        "date": newest,
        "terminals": terminals,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "lng_terminals.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(terminals)} terminals, newest gas day {newest} -> {path}")


if __name__ == "__main__":
    main()
