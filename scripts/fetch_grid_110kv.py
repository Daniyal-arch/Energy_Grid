"""Add the 110 kV tier to the transmission backbone layer.

Probed first (see chat): 380/220 kV nationally total 10,046 line ways and fetch fine
in one query. 110 kV alone is 38,470 ways — a plain COUNT query against that many
ways already took ~2 min, so a single national `out geom;` pull risks Overpass's
query timeout. Chunking by federal state (16 much smaller queries) keeps each request
in the same size class as the existing 380/220 kV pull.

Below 110 kV, OSM coverage in Germany falls off a cliff (60kV: 128 ways, 30kV: 91,
20kV: 224, 10kV: 36, 400V: 5 — probed live) because distribution-level lines are
underground and not surveyed. Not worth adding — would look like random gaps, not a
real layer.

Merges into the existing frontend/public/grid_transmission.geojson (same schema:
kind/voltage/cables for lines, kind/voltage/name for substations) so no changes are
needed to tile-grid.mjs or the GeoJSON's consumers — only lib/grid.ts's voltColor()
gets a third tier.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = {"User-Agent": "gridwatch-grid/1.0 (research)"}
OUT = Path("frontend/public/grid_transmission.geojson")

STATES = [
    "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen", "Hamburg",
    "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen", "Nordrhein-Westfalen",
    "Rheinland-Pfalz", "Saarland", "Sachsen", "Sachsen-Anhalt",
    "Schleswig-Holstein", "Thüringen",
]


def volt(tags: dict) -> int:
    raw = (tags.get("voltage") or "0").split(";")
    return max((int(v) for v in raw if v.strip().isdigit()), default=0)


def fetch_state(state: str) -> list[dict]:
    q = f"""
    [out:json][timeout:120];
    area["ISO3166-1"="DE"][admin_level=2]->.de;
    area["name"="{state}"][admin_level=4](area.de)->.st;
    (
      way["power"="line"]["voltage"~"110000"](area.st);
    );
    out geom;
    (
      node["power"="substation"]["voltage"~"110000"](area.st);
      way["power"="substation"]["voltage"~"110000"](area.st);
    );
    out center;
    """
    for attempt in range(3):
        try:
            r = httpx.post(OVERPASS, data=q, headers=UA, timeout=180)
            r.raise_for_status()
            return r.json()["elements"]
        except (httpx.HTTPStatusError, httpx.ReadTimeout) as e:
            print(f"  {state}: attempt {attempt + 1} failed ({e}), retrying...")
            time.sleep(10)
    raise RuntimeError(f"{state}: failed after 3 attempts")


def main() -> None:
    fc = json.loads(OUT.read_text(encoding="utf-8"))
    before = len(fc["features"])

    n_line = n_sub = 0
    for state in STATES:
        print(f"querying {state}...")
        els = fetch_state(state)
        for e in els:
            t = e.get("tags", {})
            if e["type"] == "way" and "geometry" in e and t.get("power") == "line":
                coords = [[p["lon"], p["lat"]] for p in e["geometry"]]
                if len(coords) < 2:
                    continue
                fc["features"].append({
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
                fc["features"].append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {"kind": "substation", "voltage": volt(t), "name": t.get("name")},
                })
                n_sub += 1
        time.sleep(2)  # be polite to the shared public Overpass instance between states

    OUT.write_text(json.dumps(fc), encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(
        f"\nadded {n_line} lines + {n_sub} substations (110 kV) — "
        f"{before} -> {len(fc['features'])} total features, {kb:.0f} KB"
    )


if __name__ == "__main__":
    main()
