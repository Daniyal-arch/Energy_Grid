"""Probe candidate sources for the next features (small requests only).

1. Open-Meteo: current 10 m wind for many points in one request (weather layer)
2. GIE ALSI: LNG terminal send-out (AGSI_API_KEY works for both)
3. ENTSOG Transparency: physical gas flows at EU entry points
4. Ember: is there an EU aggregate entity, and monthly data?
5. Energy-Charts: back up?

  uv run python scripts/probe_next_sources.py
"""

from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

load_dotenv()
c = httpx.Client(timeout=60, headers={"User-Agent": "Europe-InfraAtlas/0.2 (probe)"})

print("== 1. Open-Meteo, 3x3 grid in one call")
lats = [40, 50, 60] * 3
lons = [0] * 3 + [10] * 3 + [20] * 3
r = c.get(
    "https://api.open-meteo.com/v1/forecast",
    params={
        "latitude": ",".join(map(str, lats)),
        "longitude": ",".join(map(str, lons)),
        "current": "wind_speed_10m,wind_direction_10m,cloud_cover,shortwave_radiation",
        "wind_speed_unit": "ms",
    },
)
d = r.json()
print(
    "HTTP", r.status_code, "type", type(d).__name__, "points", len(d) if isinstance(d, list) else 1
)
first = d[0] if isinstance(d, list) else d
print("  first:", first.get("latitude"), first.get("longitude"), first.get("current"))

print("\n== 2. GIE ALSI LNG, EU and one terminal country")
key = os.environ.get("AGSI_API_KEY", "")
for params in ({"type": "eu", "size": "2"}, {"country": "ES", "size": "2"}):
    r = c.get("https://alsi.gie.eu/api", params=params, headers={"x-key": key})
    d = r.json()
    print(params, "HTTP", r.status_code, "pages", d.get("last_page"))
    for row in d.get("data", [])[:2]:
        print(
            "  ",
            {
                k: row.get(k)
                for k in ("name", "code", "gasDayStart", "inventory", "sendOut", "dtmi", "dtrs")
            },
        )

print("\n== 3. ENTSOG physical flows (one day, entry points)")
r = c.get(
    "https://transparency.entsog.eu/api/v1/operationalData",
    params={
        "indicator": "Physical Flow",
        "periodType": "day",
        "from": "2026-10-01",
        "to": "2026-10-01",
        "limit": "5",
        "pointDirection": "",
    },
)
print("HTTP", r.status_code, r.text[:300].replace("\n", " "))

print("\n== 4. Ember EU aggregate and monthly")
ek = os.environ.get("EMBER_API_KEY", "")
for code in ("EU", "EU27", "European Union"):
    r = c.get(
        "https://api.ember-energy.org/v1/electricity-generation/yearly",
        params={"entity": code, "start_date": "2024", "api_key": ek},
    )
    rows = r.json().get("data", []) if r.status_code == 200 else []
    print(f"entity={code!r}: HTTP {r.status_code}, rows {len(rows)}", rows[:1])
r = c.get(
    "https://api.ember-energy.org/v1/electricity-generation/monthly",
    params={"entity_code": "DEU", "start_date": "2026-06", "api_key": ek},
)
rows = r.json().get("data", []) if r.status_code == 200 else []
print("monthly DEU HTTP", r.status_code, "rows", len(rows), rows[:1])

print("\n== 5. Energy-Charts")
r = c.get("https://api.energy-charts.info/price", params={"bzn": "DE-LU"})
print("HTTP", r.status_code)
