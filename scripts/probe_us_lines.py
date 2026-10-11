"""Probe OpenStreetMap power lines in the United States through Overture Maps, the source for
the US lines layer now that HIFLD's layer is no longer public (scripts/probe_hifld.py) and
grid/world-hv.pmtiles holds no North American lines.

Overture's base theme, type infrastructure, subtype power, class power_line: OpenStreetMap
ways (ODbL) with their OSM tags in source_tags, as GeoParquet on Overture's public S3
bucket, read with DuckDB (only the needed columns and row groups travel). Overpass
(overpass-api.de) resets connections from the cloud session, and world-hv.yml's North
America job never finished.

1. Lines in the lower 48, Alaska and Hawaii boxes; how many carry a voltage tag
2. Lines and km by highest voltage (kV) of each way
3. Time per query and the size of a GeoJSONSeq of the lines from 100 kV

  env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY uv run --with duckdb python scripts/probe_us_lines.py [release]

(Anonymous access: the cloud session sets AWS keys for its proxy, which S3 rejects.)
"""

from __future__ import annotations

import sys
import time

import duckdb

RELEASE = sys.argv[1] if len(sys.argv) > 1 else "2026-09-23.1"
PATH = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=base/type=infrastructure/*"
# (west, south, east, north)
BOXES = {
    "lower 48": (-125.0, 24.0, -66.5, 49.5),
    "Alaska": (-170.0, 51.0, -129.0, 71.5),
    "Hawaii": (-161.0, 18.5, -154.5, 22.5),
}
# the highest number in OSM's voltage tag (volts; several circuits are ;-separated), in kV
KV = "list_max(list_transform(regexp_extract_all(source_tags['voltage'], '[0-9]+'), x -> TRY_CAST(x AS BIGINT))) // 1000"


def main() -> None:
    con = duckdb.connect()
    con.execute(
        "INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';"
    )
    for name, (w, s, e, n) in BOXES.items():
        t = time.time()
        con.execute(
            f"""
            CREATE OR REPLACE TABLE lines AS
            SELECT id, {KV} AS kv, names.primary AS name, geometry
            FROM read_parquet('{PATH}', hive_partitioning=1)
            WHERE bbox.xmin >= {w} AND bbox.xmax <= {e} AND bbox.ymin >= {s} AND bbox.ymax <= {n}
              AND subtype = 'power' AND class = 'power_line'
            """
        )
        total, tagged = con.execute("SELECT count(*), count(kv) FROM lines").fetchone()
        print(
            f"\n{name}: {total:,} power lines, {tagged:,} with a voltage ({time.time() - t:.0f} s)"
        )
        rows = con.execute(
            """
            SELECT CASE WHEN kv IS NULL THEN -1 WHEN kv >= 500 THEN kv WHEN kv >= 300 THEN kv
                        WHEN kv >= 200 THEN kv WHEN kv >= 100 THEN 100 WHEN kv >= 50 THEN 50 ELSE 0 END AS band,
                   count(*) AS n, round(sum(ST_Length_Spheroid(ST_FlipCoordinates(geometry))) / 1000) AS km
            FROM lines GROUP BY 1 ORDER BY 1
            """
        ).fetchall()
        for band, k, km in rows:
            label = (
                "no voltage"
                if band == -1
                else "< 50 kV"
                if band == 0
                else "50-99 kV"
                if band == 50
                else "100-199 kV"
                if band == 100
                else f"{band} kV"
            )
            if k >= 20 or band >= 100:
                print(f"  {label:>11}: {k:7,} lines {km:10,.0f} km")
        if name == "lower 48":
            size = con.execute(
                """
                SELECT sum(length(ST_AsGeoJSON(ST_ReducePrecision(geometry, 0.0001)))) FROM lines WHERE kv >= 100
                """
            ).fetchone()[0]
            print(f"  GeoJSON geometry of the lines from 100 kV: {size / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
