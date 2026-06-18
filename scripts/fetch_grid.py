"""Fetch the German high-voltage transmission backbone (380/220 kV) from OSM Overpass
and save it as a GeoJSON layer asset for the frontend (geometry = layer, not DB).

Lines → LineString features with voltage; transmission substations → Point features.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = {"User-Agent": "gridwatch-grid/1.0 (research)"}
OUT = Path("frontend/public/grid_transmission.geojson")

# Germany, lines at 220 kV / 380 kV (the transmission backbone), + transmission substations
Q = """
[out:json][timeout:240];
area["ISO3166-1"="DE"][admin_level=2]->.de;
(
  way["power"="line"]["voltage"~"220000|380000"](area.de);
);
out geom;
(
  node["power"="substation"]["voltage"~"220000|380000"](area.de);
  way["power"="substation"]["voltage"~"220000|380000"](area.de);
);
out center;
"""


def volt(tags: dict) -> int:
    raw = (tags.get("voltage") or "0").split(";")
    return max((int(v) for v in raw if v.strip().isdigit()), default=0)


def main() -> None:
    print("querying Overpass for the German transmission grid…")
    r = httpx.post(OVERPASS, data=Q, headers=UA, timeout=300)
    r.raise_for_status()
    els = r.json()["elements"]

    feats = []
    n_line = n_sub = 0
    for e in els:
        t = e.get("tags", {})
        if e["type"] == "way" and "geometry" in e and t.get("power") == "line":
            coords = [[p["lon"], p["lat"]] for p in e["geometry"]]
            if len(coords) < 2:
                continue
            feats.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {"kind": "line", "voltage": volt(t), "cables": t.get("cables")},
            })
            n_line += 1
        elif t.get("power") == "substation":
            lon = e.get("lon") or (e.get("center") or {}).get("lon")
            lat = e.get("lat") or (e.get("center") or {}).get("lat")
            if lon is None or lat is None:
                continue
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"kind": "substation", "voltage": volt(t), "name": t.get("name")},
            })
            n_sub += 1

    fc = {"type": "FeatureCollection", "features": feats}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fc), encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(f"lines: {n_line}  substations: {n_sub}  → {OUT} ({kb:.0f} KB)")


if __name__ == "__main__":
    main()
