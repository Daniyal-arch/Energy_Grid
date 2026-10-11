"""US transmission lines (100 kV and more) from OpenStreetMap, read through Overture Maps.

HIFLD's "Electric Power Transmission Lines" is no longer public: the HIFLD geoplatform holds
no open copy since the 2025 change, and Esri's copy is archived (last data 30 Sep 2024)
under the Esri Master License Agreement (scripts/probe_hifld.py). grid/world-hv.pmtiles
holds no North American lines. So the US layer is OpenStreetMap's (ODbL), the source the
world grid already uses, from 100 kV (NERC's bulk electric system threshold) instead of
world-hv's 220 kV, because 115-161 kV lines carry much of the US grid.

Overture Maps (base theme, type infrastructure; scripts/probe_us_lines.py): OSM ways of class
power_line and cable with their OSM tags in source_tags, as GeoParquet on Overture's public
S3 bucket (newest release, found by listing the bucket), read with DuckDB box by box (lower
48, Alaska, Hawaii). Kept: lines whose voltage tag's highest value is 100 kV or more and
that touch a US state (Census outlines, frontend/public/data/us/states.json; lines crossing
a border are kept whole). Each line once, with its highest voltage, OSM name, HVDC
(frequency=0) and cable (underground or submarine) flags, coordinates rounded to 0.0001°.

Writes GeoJSONSeq for tippecanoe, with the minimum zoom per voltage: 345 kV and more from
zoom 0, 200 kV from zoom 3, 100 kV from zoom 5. .github/workflows/us-grid.yml cuts it into
vector tiles and uploads grid/us-lines.pmtiles to R2.

    env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY uv run --with duckdb python scripts/fetch_us_lines.py --out data/us/us-lines.geojsons

(The cloud session sets AWS keys for its proxy; Overture's bucket wants anonymous access.)
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import duckdb
import httpx
import shapely
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / "frontend" / "public" / "data" / "us" / "states.json"
BUCKET = "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com"
# (west, south, east, north); the Aleutians west of 180° are left out (no lines from 100 kV there)
BOXES = {
    "lower 48": (-125.0, 24.0, -66.5, 49.5),
    "Alaska": (-170.0, 51.0, -129.0, 71.5),
    "Hawaii": (-161.0, 18.5, -154.5, 22.5),
}
KV = "list_max(list_transform(regexp_extract_all(source_tags['voltage'], '[0-9]+'), x -> TRY_CAST(x AS BIGINT))) // 1000"


def newest_release() -> str:
    xml = httpx.get(
        BUCKET, params={"list-type": "2", "prefix": "release/", "delimiter": "/"}, timeout=60
    ).text
    releases = sorted(re.findall(r"<Prefix>release/([^<]+)/</Prefix>", xml))
    if not releases:
        raise SystemExit("Overture: no release listed")
    return releases[-1]


def minzoom(kv: int) -> int:
    return 0 if kv >= 345 else 3 if kv >= 200 else 5


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", help="Overture release (default: the newest)")
    parser.add_argument("--min-kv", type=int, default=100)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    release = args.release or newest_release()
    path = f"s3://overturemaps-us-west-2/release/{release}/theme=base/type=infrastructure/*"
    print(f"Overture {release}")
    states = json.loads(STATES.read_text(encoding="utf-8"))["states"]
    polys = []
    for s in states:
        for rings in s["polygons"]:
            pairs = [list(zip(r[0::2], r[1::2], strict=True)) for r in rings]
            polys.append(Polygon(pairs[0], pairs[1:]))
    tree = shapely.STRtree(polys)
    con = duckdb.connect()
    con.execute(
        "INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';"
    )
    seen: set[str] = set()
    bands: Counter[str] = Counter()
    left_out = Counter()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for name, (w, s, e, n) in BOXES.items():
            t = time.time()
            rows = con.execute(
                f"""
                SELECT id, {KV} AS kv, class = 'cable' AS cable,
                       coalesce(list_contains(string_split(source_tags['frequency'], ';'), '0'), false) AS dc,
                       names.primary AS name, ST_AsWKB(geometry) AS wkb
                FROM read_parquet('{path}', hive_partitioning=1)
                WHERE bbox.xmin >= {w} AND bbox.xmax <= {e} AND bbox.ymin >= {s} AND bbox.ymax <= {n}
                  AND subtype = 'power' AND class IN ('power_line', 'cable')
                """
            ).fetchall()
            keep = [
                r for r in rows if r[1] is not None and r[1] >= args.min_kv and r[0] not in seen
            ]
            left_out["no voltage tag"] += sum(r[1] is None for r in rows)
            left_out[f"below {args.min_kv} kV"] += sum(
                r[1] is not None and r[1] < args.min_kv for r in rows
            )
            geoms = shapely.from_wkb([bytes(r[5]) for r in keep])
            hit = set(tree.query(geoms, predicate="intersects")[0].tolist())
            left_out["outside the US"] += len(keep) - len(hit)
            geoms = shapely.set_precision(geoms, 0.0001)
            for i, r in enumerate(keep):
                if i not in hit:
                    continue
                if geoms[i].is_empty:
                    left_out["shorter than the 0.0001° rounding"] += 1
                    continue
                seen.add(r[0])
                kv = int(r[1])
                feature = {
                    "type": "Feature",
                    "tippecanoe": {"minzoom": minzoom(kv)},
                    "properties": {
                        "kv": kv,
                        "name": r[4],
                        "dc": 1 if r[3] else None,
                        "cable": 1 if r[2] else None,
                    },
                    "geometry": json.loads(shapely.to_geojson(geoms[i])),
                }
                f.write(json.dumps(feature, separators=(",", ":"), ensure_ascii=False) + "\n")
                bands[
                    "345 kV and more"
                    if kv >= 345
                    else "200-344 kV"
                    if kv >= 200
                    else f"{args.min_kv}-199 kV"
                ] += 1
            print(
                f"{name}: {len(rows):,} lines and cables read, {len(hit):,} in the US ({time.time() - t:.0f} s)",
                flush=True,
            )
    print(
        f"{args.out}: {sum(bands.values()):,} lines {dict(bands)}, {args.out.stat().st_size / 1e6:.0f} MB"
    )
    print(f"left out: {dict(left_out)}")


if __name__ == "__main__":
    main()
