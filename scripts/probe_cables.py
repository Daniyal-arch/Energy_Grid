"""Probe OpenStreetMap (Overpass) for undersea power cables worldwide before the layer.

Counts ways tagged power=cable with location=underwater or submarine=yes, the tags
they carry (voltage, name, frequency = 0 for HVDC) and the size of a geometry answer.

    uv run python scripts/probe_cables.py
"""

from __future__ import annotations

import time
from collections import Counter

import httpx

c = httpx.Client(timeout=400, headers={"User-Agent": "Europe-InfraAtlas/0.3 (probe)"})
Q = '[out:json][timeout:300];(way["power"="cable"]["location"="underwater"];way["power"="cable"]["submarine"="yes"];);out tags geom;'
for attempt in range(4):
    t0 = time.monotonic()
    r = c.post("https://overpass-api.de/api/interpreter", data={"data": Q})
    if r.status_code == 200 and r.content.lstrip().startswith(b"{"):
        break
    print("HTTP", r.status_code, "waiting")
    time.sleep(60 * (attempt + 1))
els = r.json()["elements"]
print(f"{len(els)} ways in {time.monotonic() - t0:.0f}s, {len(r.content) / 1e6:.1f} MB")
tags = Counter(k for e in els for k in e.get("tags", {}))
print("tags:", tags.most_common(15))
named = [e["tags"].get("name") for e in els if e.get("tags", {}).get("name")]
print(len(named), "named, e.g.", sorted(set(named))[:25])
volt = Counter(e["tags"].get("voltage") for e in els)
print("voltages:", volt.most_common(10))
print("frequency:", Counter(e["tags"].get("frequency") for e in els).most_common(5))
pts = sum(len(e.get("geometry", [])) for e in els)
print("points:", pts)
