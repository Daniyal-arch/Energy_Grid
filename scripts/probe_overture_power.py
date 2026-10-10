"""Probe Overture Maps (base theme, infrastructure type) as a faster source of the world's
power lines than Overpass: which power classes exist, whether a voltage survives (in
source_tags), and how long a query for one region takes. Reads GeoParquet from Overture's
public S3 bucket with DuckDB (only the needed columns and row groups travel)."""

from __future__ import annotations

import sys
import time

import duckdb

RELEASE = sys.argv[1] if len(sys.argv) > 1 else "2026-09-23.1"
PATH = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=base/type=infrastructure/*"


def main() -> None:
    con = duckdb.connect()
    con.execute(
        "INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';"
    )
    print(
        "columns:",
        [
            r[0]
            for r in con.execute(
                f"DESCRIBE SELECT * FROM read_parquet('{PATH}', hive_partitioning=1) LIMIT 1"
            ).fetchall()
        ],
    )
    t = time.time()
    # one region: Germany's bounding box
    rows = con.execute(
        f"""
        SELECT subtype, class, count(*) AS n,
               count(source_tags['voltage']) AS with_voltage
        FROM read_parquet('{PATH}', hive_partitioning=1)
        WHERE bbox.xmin > 5.8 AND bbox.xmax < 15.1 AND bbox.ymin > 47.2 AND bbox.ymax < 55.1
          AND subtype = 'power'
        GROUP BY 1, 2 ORDER BY n DESC
        """
    ).fetchall()
    print(f"Germany box, {time.time() - t:.0f} s:")
    for r in rows:
        print("  ", r)
    sample = con.execute(
        f"""
        SELECT class, source_tags['voltage'] AS voltage, names.primary AS name, ST_Length_Spheroid(ST_FlipCoordinates(geometry)) / 1000 AS km
        FROM read_parquet('{PATH}', hive_partitioning=1)
        WHERE bbox.xmin > 5.8 AND bbox.xmax < 15.1 AND bbox.ymin > 47.2 AND bbox.ymax < 55.1
          AND subtype = 'power' AND class = 'power_line'
        LIMIT 5
        """
    ).fetchall()
    print("sample power lines:", sample)


if __name__ == "__main__":
    main()
