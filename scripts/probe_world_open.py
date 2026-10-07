"""Probe the open (no key) world sources before building the World view.

1. World Bank API: access to electricity (% of population), all countries, latest years
2. Ember monthly generation, all entities, one month
3. AEMO NEM summary (Australia, 5-min): prices, demand, interchange per region
4. OpenStreetMap via Overpass: data centres worldwide (count only)

  uv run python scripts/probe_world_open.py
"""

from __future__ import annotations

import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()
c = httpx.Client(
    timeout=180, headers={"User-Agent": "Europe-InfraAtlas/0.3 (probe)"}, follow_redirects=True
)

print("== 1. World Bank: EG.ELC.ACCS.ZS")
r = c.get(
    "https://api.worldbank.org/v2/country/all/indicator/EG.ELC.ACCS.ZS",
    params={"format": "json", "per_page": "20000", "date": "2000:2025"},
)
meta, rows = r.json()
have = [x for x in rows if x["value"] is not None]
print(f"HTTP {r.status_code}, rows {len(rows)}, with values {len(have)}, pages {meta.get('pages')}")
latest = max(int(x["date"]) for x in have)
print(
    "latest year",
    latest,
    "sample",
    [(x["countryiso3code"], x["date"], x["value"]) for x in have[:3]],
)

print("\n== 2. Ember monthly, all entities, 2026-06")
r = c.get(
    "https://api.ember-energy.org/v1/electricity-generation/monthly",
    params={"start_date": "2026-06", "end_date": "2026-06", "api_key": os.environ["EMBER_API_KEY"]},
)
rows = r.json().get("data", [])
print(f"HTTP {r.status_code}, rows {len(rows)}, entities {len({x['entity'] for x in rows})}")

print("\n== 3. AEMO NEM summary")
t0 = time.monotonic()
r = c.get("https://visualisations.aemo.com.au/aemo/apps/api/report/ELEC_NEM_SUMMARY")
print(f"HTTP {r.status_code} in {time.monotonic() - t0:.1f}s, {len(r.content) / 1e3:.0f} kB")
if r.status_code == 200:
    d = r.json()
    print("keys", list(d)[:6])
    rows = d.get("ELEC_NEM_SUMMARY", [])
    for row in rows[:5]:
        print(
            "  ",
            {
                k: row.get(k)
                for k in (
                    "REGIONID",
                    "SETTLEMENTDATE",
                    "PRICE",
                    "TOTALDEMAND",
                    "NETINTERCHANGE",
                    "SCHEDULEDGENERATION",
                    "SEMISCHEDULEDGENERATION",
                )
            },
        )
    inter = d.get("ELEC_NEM_SUMMARY_MARKET_NOTICE") or d.get("ELEC_NEM_SUMMARY_PRICES")
    print("other blocks:", [k for k in d if k != "ELEC_NEM_SUMMARY"])

print("\n== 4. Overpass: data centres worldwide (count)")
q = '[out:json][timeout:120];(nwr["telecom"="data_center"];nwr["building"="data_center"];);out count;'
t0 = time.monotonic()
r = c.post("https://overpass-api.de/api/interpreter", data={"data": q})
print(f"HTTP {r.status_code} in {time.monotonic() - t0:.1f}s", r.text[:300])
