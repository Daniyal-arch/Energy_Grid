"""Emissions per facility worldwide (Climate TRACE API v6, CC BY 4.0, no key).

Climate TRACE models each asset's emissions from satellites and other data: the values are
modelled estimates, passed through and labelled as such. scripts/probe_climate_trace.py shows
the API: `/v6/assets?sectors=...&year=...` lists assets sorted by their emissions (largest
first) with `Centroid` (lon, lat), `Country` (ISO3), `Sector` (the subsector), `Owners` and
`EmissionsSummary` (CO2e, 100-year GWP, tonnes). The API serves one figure per asset and year;
it has no monthly series per asset.

Kept: assets of the sectors power, manufacturing, fossil-fuel operations and mineral
extraction with at least THRESHOLD_T t CO2e in the newest complete year (the calendar year
before this one), and their figure for the year before (joined by asset id).

Writes frontend/public/data/eu/ctrace.json:
  {"fetched", "source", "year", "threshold_t", "subsectors": [...], "groups": [...],
   "group_of": [group per subsector],
   "rows": [[lon, lat, ISO3, name, subsector, t CO2e year, t CO2e year before | null, owner | null]]}

    uv run python scripts/fetch_climate_trace.py [--out DIR] [--year 2025]
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
API = "https://api.climatetrace.org/v6/assets"
SOURCE = "Climate TRACE (modelled emissions per asset, CO2e 100-year GWP; CC BY 4.0)"
SECTORS = ["power", "manufacturing", "fossil-fuel-operations", "mineral-extraction"]
THRESHOLD_T = 100_000
PAGE = 1000

GROUPS = [
    "Power and heat",
    "Steel and metals",
    "Cement and lime",
    "Chemicals and refining",
    "Oil and gas production",
    "Coal and mining",
    "Other industry",
]
GROUP_OF_SUBSECTOR = {
    **dict.fromkeys(["electricity-generation", "heat-plants", "other-energy-use"], 0),
    **dict.fromkeys(["iron-and-steel", "aluminum", "other-metals"], 1),
    **dict.fromkeys(["cement", "lime"], 2),
    **dict.fromkeys(
        ["chemicals", "other-chemicals", "petrochemical-steam-cracking", "oil-and-gas-refining"], 3
    ),
    **dict.fromkeys(["oil-and-gas-production", "oil-and-gas-transport"], 4),
    **dict.fromkeys(
        [
            "coal-mining",
            "iron-mining",
            "copper-mining",
            "bauxite-mining",
            "other-mining-quarrying",
            "rock-quarrying",
            "sand-quarrying",
        ],
        5,
    ),
}


def get(client: httpx.Client, params: dict) -> list[dict]:
    for attempt in range(5):
        try:
            r = client.get(API, params=params)
            if r.status_code == 200:
                return r.json().get("assets") or []
        except httpx.TransportError:
            pass
        time.sleep(5 * (attempt + 1))
    raise SystemExit(f"Climate TRACE: no answer for {params}")


def co2e(asset: dict) -> float | None:
    for e in asset.get("EmissionsSummary") or []:
        if e.get("Gas") == "co2e_100yr" and e.get("EmissionsQuantity") is not None:
            return float(e["EmissionsQuantity"])
    return None


def assets(client: httpx.Client, sector: str, year: int, threshold: float) -> list[dict]:
    """A sector's assets down to the threshold (the API lists the largest first)."""
    out: list[dict] = []
    offset = 0
    while True:
        page = get(client, {"sectors": sector, "year": year, "limit": PAGE, "offset": offset})
        out += [a for a in page if (co2e(a) or 0) >= threshold]
        if len(page) < PAGE or (co2e(page[-1]) or 0) < threshold:
            return out
        offset += PAGE


def owner(asset: dict) -> str | None:
    names = list(dict.fromkeys(o.get("CompanyName") for o in asset.get("Owners") or []))
    names = [n for n in names if n]
    return "; ".join(names[:2]) if names else None


def build(now: list[dict], before: list[dict], year: int) -> dict:
    prev = {a["Id"]: co2e(a) for a in before}
    subsectors: list[str] = []
    rows: list[list] = []
    seen: set[int] = set()
    for a in sorted(now, key=lambda a: -(co2e(a) or 0)):
        c = (a.get("Centroid") or {}).get("Geometry")
        if a["Id"] in seen or not c or c[0] is None or c[1] is None:
            continue
        seen.add(a["Id"])
        sub = a.get("Sector") or "other"
        if sub not in subsectors:
            subsectors.append(sub)
        rows.append(
            [
                round(c[0], 4),
                round(c[1], 4),
                a.get("Country"),
                (a.get("Name") or "").strip(),
                subsectors.index(sub),
                round(co2e(a) or 0),
                round(prev[a["Id"]]) if prev.get(a["Id"]) is not None else None,
                owner(a),
            ]
        )
    return {
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": SOURCE,
        "year": year,
        "threshold_t": THRESHOLD_T,
        "subsectors": subsectors,
        "groups": GROUPS,
        "group_of": [GROUP_OF_SUBSECTOR.get(s, len(GROUPS) - 1) for s in subsectors],
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--year", type=int, default=datetime.now(UTC).year - 1)
    args = parser.parse_args()
    client = httpx.Client(timeout=180)
    now: list[dict] = []
    before: list[dict] = []
    for sector in SECTORS:
        a = assets(client, sector, args.year, THRESHOLD_T)
        # the year before, down to half the threshold, so a facility that grew still has a figure
        b = assets(client, sector, args.year - 1, THRESHOLD_T / 2)
        print(f"  {sector}: {len(a)} assets >= {THRESHOLD_T:,} t in {args.year}")
        now += a
        before += b
    out = build(now, before, args.year)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "ctrace.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    total = sum(r[5] for r in out["rows"])
    print(f"{len(out['rows'])} assets, {total / 1e9:.2f} Gt CO2e in {args.year} -> {path}")


if __name__ == "__main__":
    main()
