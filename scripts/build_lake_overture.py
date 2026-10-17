"""The lake's Overture power extract (docs/DATA_LAKE.md section 6): power lines from 60 kV and
all cables, and power sites (substations, plants, converters...), worldwide, as GeoParquet in
`lake/overture_power/`. Querying Overture live is too slow for the agent (a query by power
class reads part of every file in a region), so the lake keeps this extract.

Source: Overture Maps (base theme, type infrastructure, subtype power; OpenStreetMap data,
ODbL), the newest release on its public S3 bucket, read with DuckDB one longitude band per job
(.github/workflows/lake-overture.yml; the bands of scripts/fetch_world_hv_overture.py, each
feature in the band holding the west edge of its bounding box). Left out: towers, poles,
portals, insulators and single generators (millions of points that carry no capacity).

Columns: Overture's `id`, `class`, `kv` (highest value of the OSM voltage tag, kV), the OSM
tags as published (`voltage`, `circuits`, `cables`, `frequency`, `operator`, all of them in
`tags`), `name`, `dc` (frequency 0), `cable`, `iso3` (the country whose outline, from
frontend/public/data/eu/world.json, holds the feature's centre; null at sea or in the 0.01°
simplified outlines' gaps) and its `iso2`, `geometry` (GeoParquet 1.1, WGS84) with the
writer's `bbox` covering column. Sorted by `iso3`, then
along a Hilbert curve.

    python scripts/build_lake_overture.py --band 3 --out lake-out
    python scripts/build_lake_overture.py --merge lake-out --out lake-out   (after all bands)
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb
from fetch_world_hv_overture import BANDS, KV, newest_release
from lake import Lake, hilbert, iso_codes, merge_catalogs

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "frontend" / "public" / "data" / "eu" / "world.json"
DATASET = "overture_power"
SOURCE = "Overture Maps, base/infrastructure, subtype power (OpenStreetMap contributors, ODbL)"
LINE_CLASSES = ("power_line", "minor_line", "cable")
# classes left out, by pattern (Overture names them e.g. "power_tower"): points by the million
SKIP_RE = "tower|pole|portal|insulator|catenary|mast|generator"
MIN_KV = 60


def band(n: int, out: Path, release: str | None) -> None:
    release = release or newest_release()
    w, e = BANDS[n]
    path = f"s3://overturemaps-us-west-2/release/{release}/theme=base/type=infrastructure/*"
    con = duckdb.connect()
    con.execute(
        "INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';"
    )
    con.execute(
        f"CREATE TABLE countries AS SELECT iso3, ST_SetCRS(geom, 'OGC:CRS84') AS geom FROM ST_Read('{WORLD.as_posix()}')"
    )
    iso_codes(con)
    t = time.time()
    con.execute(
        f"""
        CREATE TABLE feats AS
        SELECT id, class, {KV} AS kv,
               source_tags['voltage'] AS voltage, source_tags['circuits'] AS circuits,
               source_tags['cables'] AS cables, source_tags['frequency'] AS frequency,
               source_tags['operator'] AS operator, names.primary AS name,
               coalesce(list_contains(string_split(source_tags['frequency'], ';'), '0'), false) AS dc,
               class = 'cable' AS cable, source_tags AS tags, geometry
        FROM read_parquet('{path}', hive_partitioning=1)
        WHERE bbox.xmin >= {w} AND bbox.xmin < {e} AND subtype = 'power' AND NOT regexp_matches(class, '{SKIP_RE}')
        """
    )
    classes = dict(
        con.execute("SELECT class, count(*) FROM feats GROUP BY 1 ORDER BY 2 DESC").fetchall()
    )
    print(f"band {n} ({w}..{e}), {release}: read in {time.time() - t:.0f} s, {classes}", flush=True)
    # the class counts as a public annotation (job logs need a sign-in)
    print(f"::notice title=band {n} classes::{json.dumps(classes)}", flush=True)
    with_country = """
        SELECT f.*, i.iso2, c.iso3 FROM feats f
        LEFT JOIN countries c ON ST_Intersects(c.geom, ST_Centroid(f.geometry))
        LEFT JOIN iso_codes i ON i.iso3 = c.iso3
        QUALIFY row_number() OVER (PARTITION BY f.id ORDER BY c.iso3) = 1
    """
    lines = ", ".join(f"'{c}'" for c in LINE_CLASSES)
    lake = Lake(
        DATASET,
        out,
        source=SOURCE,
        licence="ODbL 1.0",
        script="scripts/build_lake_overture.py",
        source_version=release,
    )
    common = dict(
        sort=["iso3", hilbert()],
        bloom=["id"],
        geometry="geometry",
        partition={"release": release},
        stem=f"band{n}",
    )
    lake.write(
        con,
        "lines",
        f"SELECT * FROM ({with_country}) WHERE class IN ({lines}) AND (kv >= {MIN_KV} OR cable)",
        **common,
    )
    lake.write(
        con, "sites", f"SELECT * FROM ({with_country}) WHERE class NOT IN ({lines})", **common
    )
    cat = lake.finish()
    cat.rename(cat.with_name(f"_catalog.band{n}.json"))
    (out / DATASET / f"classes.band{n}.json").write_text(
        json.dumps({"band": [w, e], "release": release, "classes": classes}), encoding="utf-8"
    )
    lake.upload(catalog=False)


def merge(out: Path) -> None:
    folder = out / DATASET
    parts = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(folder.glob("_catalog.band*.json"))
    ]
    if len(parts) != len(BANDS):
        raise SystemExit(f"{len(parts)} of {len(BANDS)} bands: not merging")
    cat = merge_catalogs(parts)
    classes: dict[str, int] = {}
    for p in sorted(folder.glob("classes.band*.json")):
        for k, v in json.loads(p.read_text(encoding="utf-8"))["classes"].items():
            classes[k] = classes.get(k, 0) + v
    cat["classes_read"] = classes
    (folder / "_catalog.json").write_text(
        json.dumps(cat, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps({k: {"rows": t["rows"], "bytes": t["bytes"]} for k, t in cat["tables"].items()}),
        classes,
    )
    lake = Lake(
        DATASET, out, source=SOURCE, licence="ODbL 1.0", script="scripts/build_lake_overture.py"
    )
    lake.upload(catalog_only=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--band", type=int)
    parser.add_argument("--merge", action="store_true")
    parser.add_argument("--release")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.merge:
        merge(args.out)
    else:
        band(args.band, args.out, args.release)


if __name__ == "__main__":
    main()
