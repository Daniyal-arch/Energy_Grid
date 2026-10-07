"""Probe OpenStreetMap (Overpass) for high-voltage power lines (>= 220 kV) by region.

The world grid layer should show the connected high-voltage backbone with real voltages
(Gridfinder has no voltage). One query per bounding box: line count, points, voltage
mix, answer size and time, for two test regions.

    uv run python scripts/probe_osm_hv.py
"""

from __future__ import annotations

import time
from collections import Counter

import httpx

# any ';'-separated voltage component of 200 kV or more (200000 .. 9999999 V)
HV = r"(^|;)([2-9][0-9]{5}|[1-9][0-9]{6})($|;)"
c = httpx.Client(timeout=400, headers={"User-Agent": "Europe-InfraAtlas/0.3 (probe)"})

for label, bbox in (("India", "6,68,36,98"), ("South America south", "-56,-82,-20,-34")):
    q = f'[out:json][timeout:300];way["power"="line"]["voltage"~"{HV}"]({bbox});out tags geom;'
    t0 = time.monotonic()
    r = c.post("https://overpass-api.de/api/interpreter", data={"data": q})
    if r.status_code != 200:
        print(label, "HTTP", r.status_code, r.text[:200])
        continue
    els = r.json()["elements"]
    pts = sum(len(e.get("geometry", [])) for e in els)
    volts = Counter(e["tags"].get("voltage") for e in els)
    print(
        f"{label}: {len(els)} ways, {pts:,} points, {len(r.content) / 1e6:.1f} MB, {time.monotonic() - t0:.0f}s"
    )
    print("   voltages:", volts.most_common(8))
    time.sleep(30)
