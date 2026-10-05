"""Probe Open-Meteo for the wind layer before building it.

  1. How many locations fit in one request (URL length / API limit)?
  2. Hourly 100 m wind (turbine hub height) for a past day (past_days / start_date)
     and today, and how long a 1-degree grid over Europe takes.
  3. The ERA5 archive API for an older day (the 30-day archive needs past days).

Open-Meteo's free API is for non-commercial use, CC BY 4.0, 10,000 calls a day; a
request with many locations counts one call per location.

    uv run python scripts/probe_open_meteo_wind.py
"""

from __future__ import annotations

import time

import httpx

c = httpx.Client(timeout=120)
URL = "https://api.open-meteo.com/v1/forecast"


def grid(step: float) -> tuple[list[float], list[float]]:
    lats, lons = [], []
    lat = 34.0
    while lat <= 72.0:
        lon = -25.0
        while lon <= 45.0:
            lats.append(round(lat, 2))
            lons.append(round(lon, 2))
            lon += step
        lat += step
    return lats, lons


print("== 1. locations per request")
for n in (100, 500, 1000):
    lats, lons = grid(1.0)
    r = c.get(
        URL,
        params={
            "latitude": ",".join(map(str, lats[:n])),
            "longitude": ",".join(map(str, lons[:n])),
            "current": "wind_speed_10m",
        },
    )
    print(f"{n} points: HTTP {r.status_code} {r.text[:120] if r.status_code != 200 else ''}")

print("\n== 2. hourly 100 m wind, one day, 2-degree grid")
lats, lons = grid(2.0)
print(f"grid: {len(lats)} points")
t0 = time.monotonic()
got = []
for i in range(0, len(lats), 500):
    r = c.get(
        URL,
        params={
            "latitude": ",".join(map(str, lats[i : i + 500])),
            "longitude": ",".join(map(str, lons[i : i + 500])),
            "hourly": "wind_speed_100m,wind_direction_100m",
            "wind_speed_unit": "ms",
            "start_date": "2026-10-03",
            "end_date": "2026-10-03",
            "timezone": "GMT",
        },
    )
    print(f"  batch {i}: HTTP {r.status_code}, {len(r.content) / 1e3:.0f} kB")
    if r.status_code == 200:
        got += r.json() if isinstance(r.json(), list) else [r.json()]
print(f"{len(got)} points in {time.monotonic() - t0:.1f}s")
if got:
    h = got[len(got) // 2]["hourly"]
    print("middle point:", got[len(got) // 2]["latitude"], got[len(got) // 2]["longitude"])
    print("  times", h["time"][:3], "...", len(h["time"]))
    print("  speed", h["wind_speed_100m"][:6], "dir", h["wind_direction_100m"][:6])

print("\n== 3. archive API (ERA5) for 2026-09-10, 3 points")
r = c.get(
    "https://archive-api.open-meteo.com/v1/archive",
    params={
        "latitude": "50,55,60",
        "longitude": "5,10,15",
        "hourly": "wind_speed_100m,wind_direction_100m",
        "wind_speed_unit": "ms",
        "start_date": "2026-09-10",
        "end_date": "2026-09-10",
    },
)
print("HTTP", r.status_code, r.text[:300])
