"""Probe EIA's API v2 (EIA-930, hourly US grid data) before the US live view.

1. region-data: demand / net generation / interchange for the 13 EIA regions + US48,
   newest hours: which respondents, how late the newest hour is
2. fuel-type-data: generation by fuel per region, newest hour
3. interchange-data: flows between regions or balancing authorities, newest hour
4. Paging limits (rows per request)

  uv run python scripts/probe_eia.py
"""

from __future__ import annotations

import os
from collections import Counter
from datetime import UTC, datetime

import httpx
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ["EIA_API_KEY"]
BASE = "https://api.eia.gov/v2/electricity/rto"
c = httpx.Client(timeout=120)


def get(route: str, **params: object) -> dict:
    q = {
        "api_key": KEY,
        "frequency": "hourly",
        "data[0]": "value",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 5000,
        **params,
    }
    r = c.get(f"{BASE}/{route}/data/", params=q)
    print(f"  {route}: HTTP {r.status_code}, {len(r.content) / 1e3:.0f} kB")
    r.raise_for_status()
    return r.json()["response"]


print("== 1. region-data, newest rows")
d = get("region-data")
rows = d["data"]
print("  total rows available:", d.get("total"), "returned", len(rows))
print("  columns:", list(rows[0].keys()))
types = Counter(r["type"] for r in rows)
print("  types:", dict(types))
resp = sorted({(r["respondent"], r.get("respondent-name")) for r in rows})
print(f"  respondents in newest {len(rows)} rows: {len(resp)}")
print("  ", resp[:80])
newest = rows[0]["period"]
print("  newest period:", newest, "now UTC:", datetime.now(UTC).strftime("%Y-%m-%dT%H"))
regions = [
    r
    for r in rows
    if r["respondent"]
    in (
        "US48",
        "CAL",
        "TEX",
        "NE",
        "NY",
        "MIDA",
        "MIDW",
        "CENT",
        "SE",
        "FLA",
        "CAR",
        "TEN",
        "SW",
        "NW",
    )
]
print(
    "  region rows sample:",
    [(r["period"], r["respondent"], r["type"], r["value"]) for r in regions[:12]],
)

print("\n== 2. fuel-type-data, regions")
d = get("fuel-type-data", **{"facets[respondent][]": ["US48", "CAL", "TEX"]})
rows = d["data"]
print("  columns:", list(rows[0].keys()))
print("  fuels:", sorted({(r["fueltype"], r.get("type-name")) for r in rows}))
print("  sample:", [(r["period"], r["respondent"], r["fueltype"], r["value"]) for r in rows[:8]])

print("\n== 3. interchange-data")
d = get("interchange-data")
rows = d["data"]
print("  columns:", list(rows[0].keys()))
pairs = sorted({(r["fromba"], r["toba"]) for r in rows})
print(
    f"  {len(pairs)} pairs in newest rows; region-level pairs:",
    [
        p
        for p in pairs
        if p[0]
        in ("CAL", "TEX", "NE", "NY", "MIDA", "MIDW", "CENT", "SE", "FLA", "CAR", "TEN", "SW", "NW")
    ][:40],
)
print("  sample:", [(r["period"], r["fromba"], r["toba"], r["value"]) for r in rows[:5]])

print("\n== 4. newest hour per region (region filter, last 3 days)")
REG = [
    "US48",
    "CAL",
    "CAR",
    "CENT",
    "FLA",
    "MIDA",
    "MIDW",
    "NE",
    "NY",
    "NW",
    "SE",
    "SW",
    "TEN",
    "TEX",
]
since = (datetime.now(UTC).replace(minute=0, second=0, microsecond=0)).strftime("%Y-%m-%dT%H")
for route, facet in (("region-data", {"facets[type][]": ["D", "NG"]}), ("fuel-type-data", {})):
    d = get(route, **{"facets[respondent][]": REG, "start": "2026-10-04T00", **facet})
    newest: dict[str, str] = {}
    for r in d["data"]:
        if r["value"] is not None:
            newest[r["respondent"]] = max(newest.get(r["respondent"], ""), r["period"])
    print(f"  {route}: rows {len(d['data'])} of {d.get('total')}; newest per region:", newest)
d = get("interchange-data", **{"facets[fromba][]": REG[1:], "start": "2026-10-04T00"})
newest = {}
for r in d["data"]:
    newest[r["fromba"]] = max(newest.get(r["fromba"], ""), r["period"])
print(f"  interchange: rows {len(d['data'])} of {d.get('total')}; newest per from-region:", newest)
print("  now UTC", since)
