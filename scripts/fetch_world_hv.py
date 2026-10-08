"""The world's high-voltage power lines (220 kV and more) from OpenStreetMap.

Overpass (no key; OpenStreetMap contributors, ODbL; scripts/probe_osm_hv.py): ways
tagged power=line whose voltage tag has a component of 200 kV or more, fetched in 10°
boxes over one region (boxes that time out are split into quarters), then each line
written once with its highest voltage in kV. The workflow (.github/workflows/world-hv.yml)
runs the regions in parallel and merges them (a line in two regions is kept once). OpenStreetMap is a mapped subset:
complete in much of Europe and North America, patchier elsewhere.

Writes one GeoJSON feature per line (GeoJSONSeq), with tippecanoe's minimum zoom so the
backbone (500 kV and more) shows at every zoom and lower voltages appear zoomed in:
  {"type": "Feature", "tippecanoe": {"minzoom"}, "properties": {"kv", "name"}, "geometry": LineString}

    uv run python scripts/fetch_world_hv.py --region eu --out data/world/hv-eu.geojsons
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx

OVERPASS = "https://overpass-api.de/api/interpreter"
# regions (south, west, north, east) that together cover the land between 60° S and 80° N
REGIONS = {
    "na": (10, -170, 80, -50),
    "sa": (-60, -95, 10, -30),
    "eu": (35, -25, 72, 45),
    "af": (-36, -20, 35, 55),
    "mea": (10, 45, 45, 90),
    "north": (45, 45, 80, 180),
    "asia": (-12, 60, 45, 150),
    "oc": (-50, 110, -10, 180),
}
BOX = 10
HV = r"(^|;)([2-9][0-9]{5}|[1-9][0-9]{6})($|;)"
PAUSE_S = 10


def kilovolts(tag: str) -> int | None:
    values = []
    for part in tag.replace(",", ";").split(";"):
        try:
            values.append(int(float(part.strip())) // 1000)
        except ValueError:
            continue
    return max(values) if values else None


def query(
    client: httpx.Client,
    s: float,
    w: float,
    n: float,
    e: float,
    depth: int = 0,
    endpoint: str = OVERPASS,
) -> list[dict]:
    """Lines in one box; a box Overpass cannot finish is split into four."""
    q = f'[out:json][timeout:240];way["power"="line"]["voltage"~"{HV}"]({s},{w},{n},{e});out tags geom;'
    for attempt in range(3):
        try:
            r = client.post(endpoint, data={"data": q})
        except httpx.TransportError:
            time.sleep(30 * (attempt + 1))
            continue
        if r.status_code == 200 and r.content.lstrip().startswith(b"{"):
            data = r.json()
            if "remark" in data and "timed out" in data.get("remark", ""):
                break  # a partial answer: split instead
            time.sleep(PAUSE_S)
            return data["elements"]
        if r.status_code == 429:
            time.sleep(60 * (attempt + 1))
            continue
        break  # 504 and friends: the box is too big
    if depth >= 4:
        print(f"  gave up on box {s},{w},{n},{e}", flush=True)
        return []
    time.sleep(PAUSE_S)
    ms, mw = (s + n) / 2, (w + e) / 2
    out: list[dict] = []
    for box in ((s, w, ms, mw), (s, mw, ms, e), (ms, w, n, mw), (ms, mw, n, e)):
        out += query(client, *box, depth=depth + 1, endpoint=endpoint)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", choices=sorted(REGIONS), required=True)
    parser.add_argument("--overpass", default=OVERPASS, help="Overpass endpoint")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out: Path = args.out
    south, west, north, east = REGIONS[args.region]
    seen: set[int] = set()
    count = points = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with (
        httpx.Client(
            timeout=300, headers={"User-Agent": "Europe-InfraAtlas/0.3 (world grid)"}
        ) as client,
        out.open("w", encoding="utf-8") as f,
    ):
        for s in range(south, north, BOX):
            for w in range(west, east, BOX):
                elements = query(
                    client, s, w, min(north, s + BOX), min(east, w + BOX), endpoint=args.overpass
                )
                new = 0
                for el in elements:
                    if el["id"] in seen or len(el.get("geometry", [])) < 2:
                        continue
                    seen.add(el["id"])
                    tags = el.get("tags", {})
                    coords = [[round(p["lon"], 4), round(p["lat"], 4)] for p in el["geometry"]]
                    kv = kilovolts(tags.get("voltage", "")) or 0
                    feature = {
                        "type": "Feature",
                        # the backbone first: 500 kV+ at every zoom, lower voltages zoomed in
                        "tippecanoe": {"minzoom": 0 if kv >= 500 else 1 if kv >= 300 else 3},
                        "properties": {"id": el["id"], "kv": kv or None, "name": tags.get("name")},
                        "geometry": {"type": "LineString", "coordinates": coords},
                    }
                    f.write(json.dumps(feature, separators=(",", ":"), ensure_ascii=False) + "\n")
                    new += 1
                    points += len(coords)
                count += new
                print(f"box {s},{w}: {new} lines (total {count:,}, {points:,} points)", flush=True)
    print(f"{out}: {count:,} lines, {points:,} points, {out.stat().st_size / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
