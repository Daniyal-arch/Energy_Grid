"""The world's power lines of 220 kV and more from OpenStreetMap, read through Overture Maps.

Overpass timed out for North America, Asia, Africa, South America and the north
(scripts/fetch_world_hv.py). Overture Maps (base theme, type infrastructure; the same reader
as scripts/fetch_us_lines.py) carries OSM's power lines and cables with their OSM tags in
`source_tags`, as GeoParquet on Overture's public S3 bucket (newest release, found by listing
the bucket), read with DuckDB.

The world is cut into longitude bands (BANDS); a line belongs to the band holding the west
edge of its bounding box, so each line is read once without a merge step. Kept: lines and
cables whose voltage tag's highest value is 220 kV or more, with that voltage (`kv`), the OSM
name, HVDC (frequency=0) and cable flags; coordinates rounded to 0.0001°. The layer name
(`hv`) and property (`kv`) are the ones frontend/src/map/style.ts reads.

Writes GeoJSONSeq for tippecanoe with the minimum zoom per voltage (500 kV and more from
zoom 0, 300 kV from 1, the rest from 3), and a summary JSON (lines and km per region of the
first point, km by the haversine formula on the rounded coordinates).

    uv run --with duckdb python scripts/fetch_world_hv_overture.py --band 0 --out hv-0.geojsons
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from collections import Counter
from pathlib import Path

import duckdb
import httpx
import shapely

BUCKET = "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com"
# (west, east) in degrees; together they cover -180..180
BANDS = [(-180, -120), (-120, -90), (-90, -60), (-60, 0), (0, 30), (30, 60), (60, 100), (100, 180)]
KV = "list_max(list_transform(regexp_extract_all(source_tags['voltage'], '[0-9]+'), x -> TRY_CAST(x AS BIGINT))) // 1000"
# coarse regions for the summary, by the line's first point: (name, west, south, east, north)
REGIONS = [
    ("North America", -170, 7, -50, 84),
    ("South America", -92, -56, -30, 7),
    ("Europe", -25, 35, 45, 72),
    ("Africa", -20, -36, 52, 35),
    ("Middle East", 34, 12, 63, 42),
    ("Russia and Central Asia", 45, 35, 180, 82),
    ("South Asia", 60, 5, 98, 35),
    ("East Asia", 98, 18, 150, 54),
    ("Southeast Asia", 92, -11, 141, 18),
    ("Oceania", 110, -50, 180, -11),
]


def newest_release() -> str:
    xml = httpx.get(
        BUCKET, params={"list-type": "2", "prefix": "release/", "delimiter": "/"}, timeout=60
    ).text
    releases = sorted(re.findall(r"<Prefix>release/([^<]+)/</Prefix>", xml))
    if not releases:
        raise SystemExit("Overture: no release listed")
    return releases[-1]


def minzoom(kv: int) -> int:
    return 0 if kv >= 500 else 1 if kv >= 300 else 3


def km(coords: list) -> float:
    """Length along the coordinates (haversine, mean Earth radius 6,371 km)."""
    total = 0.0
    for (x0, y0), (x1, y1) in zip(coords, coords[1:], strict=False):
        p0, p1 = math.radians(y0), math.radians(y1)
        a = (
            math.sin((p1 - p0) / 2) ** 2
            + math.cos(p0) * math.cos(p1) * math.sin(math.radians(x1 - x0) / 2) ** 2
        )
        total += 2 * 6371 * math.asin(math.sqrt(min(1.0, a)))
    return total


def region_of(x: float, y: float) -> str:
    for name, w, s, e, n in REGIONS:
        if w <= x <= e and s <= y <= n:
            return name
    return "other"


def lines_of(geom: shapely.Geometry) -> list:
    """The line's parts with at least two points (rounding can leave empty parts)."""
    if geom.is_empty:
        return []
    parts = [geom] if geom.geom_type == "LineString" else list(getattr(geom, "geoms", []))
    return [list(g.coords) for g in parts if g.geom_type == "LineString" and len(g.coords) >= 2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--band", type=int, required=True, help=f"0..{len(BANDS) - 1}")
    parser.add_argument("--release", help="Overture release (default: the newest)")
    parser.add_argument("--min-kv", type=int, default=220)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    release = args.release or newest_release()
    w, e = BANDS[args.band]
    path = f"s3://overturemaps-us-west-2/release/{release}/theme=base/type=infrastructure/*"
    con = duckdb.connect()
    con.execute(
        "INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';"
    )
    t = time.time()
    rows = con.execute(
        f"""
        SELECT id, {KV} AS kv, class = 'cable' AS cable,
               coalesce(list_contains(string_split(source_tags['frequency'], ';'), '0'), false) AS dc,
               names.primary AS name, ST_AsWKB(geometry) AS wkb
        FROM read_parquet('{path}', hive_partitioning=1)
        WHERE bbox.xmin >= {w} AND bbox.xmin < {e}
          AND subtype = 'power' AND class IN ('power_line', 'cable')
        """
    ).fetchall()
    left_out: Counter[str] = Counter()
    left_out["no voltage tag"] = sum(r[1] is None for r in rows)
    left_out[f"below {args.min_kv} kV"] = sum(r[1] is not None and r[1] < args.min_kv for r in rows)
    keep = [r for r in rows if r[1] is not None and r[1] >= args.min_kv]
    geoms = shapely.set_precision(shapely.from_wkb([bytes(r[5]) for r in keep]), 0.0001)
    n_by: Counter[str] = Counter()
    km_by: Counter[str] = Counter()
    bands: Counter[str] = Counter()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for r, g in zip(keep, geoms, strict=True):
            parts = lines_of(g)
            if not parts:
                left_out["shorter than the 0.0001° rounding"] += 1
                continue
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
                "geometry": json.loads(shapely.to_geojson(g)),
            }
            f.write(json.dumps(feature, separators=(",", ":"), ensure_ascii=False) + "\n")
            region = region_of(*parts[0][0])
            n_by[region] += 1
            km_by[region] += sum(km(p) for p in parts)
            bands[
                "500 kV and more" if kv >= 500 else "300-499 kV" if kv >= 300 else "220-299 kV"
            ] += 1
    summary = {
        "release": release,
        "band": [w, e],
        "seconds": round(time.time() - t),
        "read": len(rows),
        "lines": dict(n_by),
        "km": {k: round(v) for k, v in km_by.items()},
        "by_voltage": dict(bands),
        "left_out": dict(left_out),
    }
    args.out.with_suffix(".summary.json").write_text(
        json.dumps(summary, indent=1), encoding="utf-8"
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
