"""Download OpenStreetMap mainline rail geometry for Germany (+ border strip).

One-time input for scripts/build_rail_day.py: trains in the day animation follow
real track instead of straight stop-to-stop lines (the gtfs.de feeds have no
shapes.txt, and the simplified DB InfraGO layer is too fragmented to route on).

Fetches railway=rail ways without a service tag (no sidings/yards/spurs) in four
tiles via Overpass (~190 MB in total), then writes a compact file with node
coordinates and way node lists: data/osm_rail/rail.json.gz
(© OpenStreetMap contributors, ODbL).

    uv run python scripts/fetch_rail_osm.py
"""

from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "data" / "osm_rail"
# main instance first, then a public mirror; Overpass answers 504 when busy
URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
HEADERS = {
    "User-Agent": "Germany-InfraAtlas/0.1 (rail day animation)",
    "Accept": "application/json",
}
# Germany plus ~30 km so cross-border runs reach the first foreign stations
SOUTH, WEST, NORTH, EAST = 47.0, 5.5, 55.2, 15.4
MID_LAT, MID_LON = 51.1, 10.45
TILES = [
    (SOUTH, WEST, MID_LAT, MID_LON),
    (SOUTH, MID_LON, MID_LAT, EAST),
    (MID_LAT, WEST, NORTH, MID_LON),
    (MID_LAT, MID_LON, NORTH, EAST),
]


def download(i: int, url: str, query: str) -> bytes:
    started = time.time()
    got = 0
    chunks = []
    with httpx.stream("POST", url, data={"data": query}, headers=HEADERS, timeout=None) as r:
        r.raise_for_status()
        for chunk in r.iter_bytes():
            chunks.append(chunk)
            got += len(chunk)
            print(
                f"\rtile {i}: {got / 1e6:6.1f} MB  {time.time() - started:4.0f} s",
                end="",
                flush=True,
            )
    print()
    return b"".join(chunks)


def fetch_tile(i: int, bbox: tuple[float, float, float, float]) -> dict:
    path = OUT / f"tile_{i}.json"
    if path.exists():
        print(f"tile {i}: cached")
        return json.loads(path.read_text(encoding="utf-8"))
    s, w, n, e = bbox
    query = (
        f'[out:json][timeout:900];way["railway"="rail"][!"service"]({s},{w},{n},{e});'
        "(._;>;);out skel qt;"
    )
    for attempt in range(6):
        url = URLS[attempt % len(URLS)]
        try:
            raw = download(i, url, query)
            data = json.loads(raw)
            path.write_bytes(raw)
            return data
        except (httpx.HTTPError, json.JSONDecodeError) as err:
            wait = 30 * (attempt + 1)
            print(f"\ntile {i}: {err.__class__.__name__} from {url}; retry in {wait} s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"tile {i}: Overpass unavailable after retries")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    nodes: dict[int, tuple[float, float]] = {}
    ways: dict[int, list[int]] = {}
    for i, bbox in enumerate(TILES):
        data = fetch_tile(i, bbox)
        for el in data["elements"]:
            if el["type"] == "node":
                nodes[el["id"]] = (round(el["lon"], 6), round(el["lat"], 6))
            elif el["type"] == "way":
                ways[el["id"]] = el["nodes"]
    out = OUT / "rail.json.gz"
    out.write_bytes(
        gzip.compress(
            json.dumps(
                {
                    "source": "OpenStreetMap contributors (ODbL), railway=rail without service tag",
                    "nodes": {str(k): v for k, v in nodes.items()},
                    "ways": list(ways.values()),
                },
                separators=(",", ":"),
            ).encode()
        )
    )
    print(f"{len(ways):,} ways · {len(nodes):,} nodes -> {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    sys.exit(main())
