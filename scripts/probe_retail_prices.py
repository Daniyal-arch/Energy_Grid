"""Probe retail energy prices: Eurostat half-yearly prices by consumption band, EIA monthly
average retail price per state and sector.

    uv run python scripts/probe_retail_prices.py
"""

from __future__ import annotations

import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
c = httpx.Client(timeout=120)
ES = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

for code in ("nrg_pc_204", "nrg_pc_205", "nrg_pc_202", "nrg_pc_203", "nrg_pc_204_c"):
    r = c.get(
        f"{ES}/{code}", params={"format": "JSON", "lang": "EN", "geo": "DE", "lastTimePeriod": 2}
    )
    print(f"\n== {code}: HTTP {r.status_code}, {len(r.content)} bytes")
    if r.status_code != 200:
        print(r.text[:300])
        continue
    d = r.json()
    print("  label:", d.get("label"), "| updated", d.get("updated"))
    for dim in d["id"]:
        cat = d["dimension"][dim]["category"]
        labels = cat.get("label", {})
        print(f"  {dim} ({len(labels)}):", json.dumps(labels, ensure_ascii=False)[:400])
    vals = d.get("value", {})
    print("  values:", len(vals), list(vals.items())[:6])
    print("  status:", list(d.get("status", {}).items())[:6])

print("\n== one household value: DE, 2,500-4,999 kWh, all taxes, EUR/kWh, newest half-year")
r = c.get(
    f"{ES}/nrg_pc_204",
    params={
        "format": "JSON",
        "lang": "EN",
        "geo": "DE",
        "nrg_cons": "KWH2500-4999",
        "unit": "KWH",
        "currency": "EUR",
        "tax": "I_TAX",
        "lastTimePeriod": 4,
    },
)
d = r.json()
times = d["dimension"]["time"]["category"]["index"]
print({t: d["value"].get(str(i)) for t, i in times.items()})

print("\n== EIA retail sales API: average price by state and sector, monthly")
key = os.environ.get("EIA_API_KEY", "").strip()
r = c.get(
    "https://api.eia.gov/v2/electricity/retail-sales/data/",
    params={
        "api_key": key,
        "frequency": "monthly",
        "data[0]": "price",
        "facets[stateid][]": ["TX", "CA"],
        "facets[sectorid][]": ["RES", "COM", "IND"],
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 12,
    },
)
d = r.json()
print("HTTP", r.status_code, {k: v for k, v in d.get("response", {}).items() if k != "data"})
for row in d.get("response", {}).get("data", [])[:8]:
    print("  ", row)
