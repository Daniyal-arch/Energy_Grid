"""Great Britain's generating units offline now (brief 22, family 8), beside ENTSO-E's A80 file.

    python scripts/fetch_gb_outages.py [--out DIR]

Elexon's REMIT messages (Insights API, no key; ENTSO-E has no GB data since 2021): the events
running now (`/remit/list/by-event` over the next minute, latest revision only), each message read
in batches of 40 (`/remit?messageId=...`). Kept: production unavailability, event status Active,
started and not yet ended. Offline = the message's unavailable capacity (MW, as published);
planned or unplanned (shown as forced) as the message says; fuel grouped as the ENTSO-E file.
Units above 2,000 MW are left out as mis-reported, as fetch_outages.py does. Closed plants stay
published as open-ended unavailability (Ratcliffe, Fiddlers Ferry, Hinkley Point B, to 2050): an
event that began more than 365 days ago or ends more than ten years ahead is left out as a closure
and counted ("long_term", with its MW).

Merged into <out>/outages.json as zone and country "GB" (run after fetch_outages.py); the Europe
totals are recomputed as the sum of the countries.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wave7_common as w7  # noqa: E402
from fetch_eu_snapshot import FUEL_GROUP  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu"
API = "https://data.elexon.co.uk/bmrs/api/v1"
MAX_UNIT_MW = 2000
GROUP = {k.lower(): v for k, v in FUEL_GROUP.items()}
TYPE = {"Planned": "planned", "Unplanned": "forced"}


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


LONG_AGO = timedelta(days=365)
FAR_AHEAD = timedelta(days=3650)


def units(messages: list[dict], now: datetime) -> tuple[list[dict], int, dict]:
    """(units offline now, reports mis-reported, closures left out) from REMIT messages."""
    out, left_out = [], 0
    long_term = {"n": 0, "mw": 0.0}
    for m in messages:
        if m.get("eventType") != "Production unavailability" or m.get("eventStatus") != "Active":
            continue
        start, end = m.get("eventStartTime"), m.get("eventEndTime")
        if not start or _t(start) > now or (end and _t(end) <= now):
            continue
        off = m.get("unavailableCapacity")
        if off is None or off < 1:
            continue
        if _t(start) < now - LONG_AGO or (end and _t(end) > now + FAR_AHEAD):
            long_term["n"] += 1
            long_term["mw"] = round(long_term["mw"] + off, 1)
            continue
        if (m.get("normalCapacity") or 0) > MAX_UNIT_MW:
            left_out += 1
            continue
        out.append(
            {
                "zone": "GB",
                "country": "GB",
                "unit": m.get("affectedUnit") or m.get("assetId") or "",
                "plant": m.get("assetId") or m.get("affectedUnit") or "",
                "fuel": GROUP.get((m.get("fuelType") or "").lower(), "other"),
                "nominal_mw": m.get("normalCapacity"),
                "available_mw": m.get("availableCapacity") or 0.0,
                "offline_mw": round(float(off), 1),
                "type": TYPE.get(m.get("unavailabilityType") or "", "unknown"),
                "start": _t(start).strftime("%Y-%m-%dT%H:%MZ"),
                "end": _t(end).strftime("%Y-%m-%dT%H:%MZ") if end else None,
                "cause": m.get("cause"),
            }
        )
    return sorted(out, key=lambda u: -u["offline_mw"]), left_out, long_term


def merge(f: dict, gb: list[dict], left_out: int, at: str, long_term: dict) -> dict:
    """GB into the outages file: its zone, country and units; Europe's totals recomputed."""
    z = {
        "country": "GB",
        "offline_mw": 0.0,
        "planned_mw": 0.0,
        "forced_mw": 0.0,
        "left_out": left_out,
        "by_fuel": {},
    }
    for u in gb:
        z["offline_mw"] += u["offline_mw"]
        if u["type"] in ("planned", "forced"):
            z[f"{u['type']}_mw"] += u["offline_mw"]
        z["by_fuel"][u["fuel"]] = z["by_fuel"].get(u["fuel"], 0.0) + u["offline_mw"]
    for k in ("offline_mw", "planned_mw", "forced_mw"):
        z[k] = round(z[k], 1)
    z["by_fuel"] = {k: round(v, 1) for k, v in sorted(z["by_fuel"].items(), key=lambda kv: -kv[1])}
    f["zones"]["GB"] = z
    f["countries"]["GB"] = {k: z[k] for k in ("offline_mw", "planned_mw", "forced_mw", "left_out")}
    f["countries"] = dict(sorted(f["countries"].items()))
    f["zones"] = dict(sorted(f["zones"].items()))
    f["units"] = sorted(
        [u for u in f["units"] if u["country"] != "GB"] + gb, key=lambda u: -u["offline_mw"]
    )
    f["total"] = {
        k: round(sum(c[k] for c in f["countries"].values()), 1)
        for k in ("offline_mw", "planned_mw", "forced_mw", "left_out")
    }
    f["gb"] = {
        "source": "Elexon REMIT messages (Insights API), production unavailability",
        "at": at,
        "long_term": long_term,
    }
    return f


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    params = {
        "from": now.strftime("%Y-%m-%dT%H:%MZ"),
        "to": (now + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%MZ"),
        "latestRevisionOnly": "true",
        "format": "json",
    }
    ids = [r["id"] for r in w7.get(f"{API}/remit/list/by-event", params=params).json()["data"]]
    messages: list[dict] = []
    for i in range(0, len(ids), 40):
        q = "&".join(f"messageId={x}" for x in ids[i : i + 40])
        messages += w7.get(f"{API}/remit?{q}&format=json").json()["data"]
    gb, left_out, long_term = units(messages, now)
    path = args.out / "outages.json"
    f = json.loads(path.read_text(encoding="utf-8"))
    f = merge(f, gb, left_out, now.isoformat(timespec="seconds"), long_term)
    path.write_text(json.dumps(f, separators=(",", ":")), encoding="utf-8")
    print(
        f"GB: {len(messages)} REMIT messages, {len(gb)} units offline, "
        f"{f['countries']['GB']['offline_mw'] / 1000:.1f} GW; closures left out {long_term} -> {path}"
    )


if __name__ == "__main__":
    main()
