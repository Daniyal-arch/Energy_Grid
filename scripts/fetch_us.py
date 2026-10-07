"""The US grid from EIA-930 (EIA API v2, EIA_API_KEY), for the World tab.

The 13 EIA regions and the Lower 48 (scripts/probe_eia.py):
  region-data       hourly demand (D), net generation (NG) and total interchange (TI,
                    positive = net export), newest hour about 1 h behind
  fuel-type-data    hourly generation by fuel, newest hour about a day behind
  interchange-data  hourly flow between regions (and to Canada and Mexico), newest
                    hour about two days behind: EIA's sign, positive = from the first
                    region to the second

Each value is passthrough with its own hour (UTC). Fuels are grouped like the rest of
the app (wind + wind with battery, solar + solar with battery, storage types together);
storage can be negative while charging.

Writes frontend/public/data/eu/us.json:
  {"source", "fetched", "regions": {ID: {"name", "demand": [hour, MW], "generation":
   [hour, MW], "interchange": [hour, MW], "mix": {"hour", "mw": {group: MW}}}},
   "us48_demand": [[hour, MW], ...] (last 48 h), "flows": {"hour", "pairs": [{"a", "b",
   "mw"}]}}

    uv run python scripts/fetch_us.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
BASE = "https://api.eia.gov/v2/electricity/rto"
REGIONS = ["CAL", "CAR", "CENT", "FLA", "MIDA", "MIDW", "NE", "NY", "NW", "SE", "SW", "TEN", "TEX"]
NEIGHBOURS = ["CAN", "MEX"]
FUEL_GROUP = {
    "COL": "coal",
    "NG": "gas",
    "NUC": "nuclear",
    "OIL": "oil",
    "WAT": "hydro",
    "SUN": "solar",
    "SNB": "solar",
    "WND": "wind",
    "WNB": "wind",
    "GEO": "other",
    "OTH": "other",
    "UNK": "other",
    "PS": "storage",
    "BAT": "storage",
    "OES": "storage",
    "UES": "storage",
}


def rows(client: httpx.Client, route: str, params: dict) -> list[dict]:
    """Every row of a query (EIA answers 5,000 rows per page)."""
    out: list[dict] = []
    offset = 0
    while True:
        query = {
            "api_key": os.environ["EIA_API_KEY"],
            "frequency": "hourly",
            "data[0]": "value",
            "length": 5000,
            "offset": offset,
            **params,
        }
        for attempt in range(4):
            try:
                r = client.get(f"{BASE}/{route}/data/", params=query)
            except httpx.TransportError:
                time.sleep(10 * (attempt + 1))
                continue
            if r.status_code == 200:
                break
            time.sleep(10 * (attempt + 1))
        else:
            raise RuntimeError(f"EIA {route}: no answer")
        page = r.json()["response"]
        out += page["data"]
        offset += 5000
        if offset >= int(page.get("total") or 0):
            return out


def num(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out: Path = parser.parse_args().out
    now = datetime.now(UTC)
    start = (now - timedelta(days=4)).strftime("%Y-%m-%dT%H")
    with httpx.Client(timeout=120, headers={"User-Agent": "Europe-InfraAtlas/0.3"}) as client:
        region = rows(
            client,
            "region-data",
            {
                "facets[respondent][]": ["US48", *REGIONS],
                "facets[type][]": ["D", "NG", "TI"],
                "start": start,
            },
        )
        fuel = rows(client, "fuel-type-data", {"facets[respondent][]": REGIONS, "start": start})
        inter = rows(client, "interchange-data", {"facets[fromba][]": REGIONS, "start": start})
    print(f"rows: region {len(region)}, fuel {len(fuel)}, interchange {len(inter)}", flush=True)

    names: dict[str, str] = {}
    newest: dict[tuple[str, str], tuple[str, float]] = {}
    us48: dict[str, float] = {}
    for r in region:
        v = num(r["value"])
        if v is None:
            continue
        names[r["respondent"]] = r["respondent-name"]
        key = (r["respondent"], r["type"])
        if key not in newest or r["period"] > newest[key][0]:
            newest[key] = (r["period"], v)
        if r["respondent"] == "US48" and r["type"] == "D":
            us48[r["period"]] = v

    # generation mix: the newest hour in which the region reports any fuel
    by_hour: dict[str, dict[str, dict[str, float]]] = {}
    for r in fuel:
        v = num(r["value"])
        if v is None:
            continue
        group = FUEL_GROUP.get(r["fueltype"], "other")
        cell = by_hour.setdefault(r["respondent"], {}).setdefault(r["period"], {})
        cell[group] = cell.get(group, 0.0) + v
    mix = {
        rid: {
            "hour": max(hours),
            "mw": {g: round(v, 1) for g, v in sorted(hours[max(hours)].items())},
        }
        for rid, hours in by_hour.items()
    }

    # flows: the newest hour in which every region pair has a value; one direction per pair
    pairs_by_hour: dict[str, dict[tuple[str, str], float]] = {}
    for r in inter:
        v = num(r["value"])
        a, b = r["fromba"], r["toba"]
        if v is None or b not in REGIONS + NEIGHBOURS:
            continue
        key = (a, b) if (a < b or b in NEIGHBOURS) else (b, a)
        if b not in NEIGHBOURS and key != (a, b):
            v = -v  # reported by the other side: flip to the pair's direction
        pairs_by_hour.setdefault(r["period"], {}).setdefault(key, v)
    all_pairs = set().union(*[set(p) for p in pairs_by_hour.values()]) if pairs_by_hour else set()
    full = [h for h, p in pairs_by_hour.items() if set(p) >= all_pairs]
    flow_hour = max(full) if full else (max(pairs_by_hour) if pairs_by_hour else None)
    flows = {
        "hour": flow_hour,
        "pairs": [
            {"a": a, "b": b, "mw": round(v, 1)}
            for (a, b), v in sorted((pairs_by_hour.get(flow_hour or "", {})).items())
        ],
    }

    def cell(rid: str, t: str) -> list | None:
        got = newest.get((rid, t))
        return [got[0], round(got[1], 1)] if got else None

    payload = {
        "source": "EIA-930 Hourly Electric Grid Monitor (EIA API v2), public domain",
        "fetched": now.isoformat(timespec="seconds"),
        "regions": {
            rid: {
                "name": names.get(rid, rid),
                "demand": cell(rid, "D"),
                "generation": cell(rid, "NG"),
                "interchange": cell(rid, "TI"),
                "mix": mix.get(rid),
            }
            for rid in ["US48", *REGIONS]
        },
        "us48_demand": [[h, round(v, 1)] for h, v in sorted(us48.items())][-48:],
        "flows": flows,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "us.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    us = payload["regions"]["US48"]
    print(
        f"us.json: US48 demand {us['demand']}, generation {us['generation']}; "
        f"{len(mix)} regions with a mix (newest {max((m['hour'] for m in mix.values()), default='-')}); "
        f"{len(flows['pairs'])} flows at {flows['hour']}"
    )


if __name__ == "__main__":
    main()
