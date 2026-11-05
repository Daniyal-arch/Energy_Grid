"""Rollups of the lake's large point tables on the H3 grid (brief 30 Track 4.1) -> lake
`rollups/<dataset>__<table>_r<res>`.

For every table in the lake catalogue (`lake/_catalog.json` on R2) with at least `--min-rows`
rows and a position (lon/lat columns or a geometry), one table per H3 resolution (5, 6, 7:
about 250, 36 and 5 km² a cell) with, per cell and per value of up to three low-cardinality text
columns (status, fuel, technology...): the count of rows and the sum of each capacity-like
numeric column (kw, mw, capacity, power, area in the name), plus the cell's centre.

The backend reads a rollup for a large area (a country, a region) instead of millions of rows:
the sum over the cells whose centre lies inside the area, which is a different rule from the
row-level `in_area` (a row near the border counts with its cell). The answer says which rule it
used (agent/catalog/rollups.yaml). Nothing is estimated: counts and sums of published values.

Reads each source table from R2 once (MaStR and Overture power are the largest, a few GB in
all); writes a few hundred MB. Runs in Actions (`wave8.yml` group U).

    python scripts/build_rollups.py [--min-rows 1000000] [--only mastr.units_solar] --lake lake-out --upload
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wave5_common as w  # noqa: E402

SCRIPT = "scripts/build_rollups.py"
RES = (5, 6, 7)
MEASURE = re.compile(r"(kw|mw|capacity|power|area|_km2)", re.I)


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for ext in ("httpfs", "spatial"):
        con.execute(f"INSTALL {ext}; LOAD {ext}")
    con.execute("INSTALL h3 FROM community; LOAD h3")
    key, secret = os.environ["AWS_ACCESS_KEY_ID"], os.environ["AWS_SECRET_ACCESS_KEY"]
    acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    con.execute(
        f"CREATE SECRET lake (TYPE r2, KEY_ID '{key}', SECRET '{secret}', ACCOUNT_ID '{acct}')"
    )
    return con


def plan(con: duckdb.DuckDBPyConnection, min_rows: int, only: list[str]) -> list[dict]:
    cat = json.loads(
        con.execute(
            "SELECT content FROM read_text('r2://infraatlas-raw/lake/_catalog.json')"
        ).fetchone()[0]
    )
    out = []
    for name, ds in (cat.get("datasets") or {}).items():
        for t, info in (ds.get("tables") or {}).items():
            full = f"{name}.{t}"
            if name in ("rollups", "outlines") or (only and full not in only):
                continue
            if (info.get("rows") or 0) < min_rows and not only:
                continue
            cols = info.get("columns") or {}
            low = {c.lower(): c for c in cols}
            if "lon" in low and "lat" in low:
                pos = (f'"{low["lon"]}"', f'"{low["lat"]}"')
            elif "geometry" in low:
                pos = ("ST_X(ST_Centroid(geometry))", "ST_Y(ST_Centroid(geometry))")
            else:
                continue
            nums = [
                c
                for c, typ in cols.items()
                if MEASURE.search(c)
                and re.match(r"(DOUBLE|FLOAT|INT|BIGINT|DECIMAL|HUGEINT|REAL)", str(typ))
            ]
            texts = [c for c, typ in cols.items() if str(typ).startswith("VARCHAR")]
            out.append({"table": full, "path": f"r2://infraatlas-raw/{info['path']}", "pos": pos,
                        "nums": nums[:6], "texts": texts, "rows": info.get("rows")})  # fmt: skip
    return out


def dims_of(con: duckdb.DuckDBPyConnection, src: str, texts: list[str]) -> list[str]:
    """Up to three text columns with 2-30 values (status, fuel...), from a sample."""
    if not texts:
        return []
    q = ", ".join(f'approx_count_distinct("{c}")' for c in texts)
    counts = con.execute(f"SELECT {q} FROM (SELECT * FROM {src} USING SAMPLE 200000)").fetchone()
    return [c for c, n in zip(texts, counts, strict=True) if 2 <= (n or 0) <= 30][:3]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rows", type=int, default=1_000_000)
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    a = ap.parse_args()
    con = connect()
    todo = plan(con, a.min_rows, a.only)
    print(f"{len(todo)} tables: {', '.join(t['table'] for t in todo)}", flush=True)
    lk = w.lake_for(
        "rollups",
        a.lake,
        "H3 rollups of the lake's large point tables",
        "as each source table",
        SCRIPT,
    )
    for t in todo:
        t0 = time.time()
        src = f"read_parquet('{t['path']}', hive_partitioning = true)"
        try:
            dims = dims_of(con, src, t["texts"])
            lon, lat = t["pos"]
            con.execute(
                f"CREATE OR REPLACE TEMP TABLE base AS SELECT {lon} AS lon, {lat} AS lat"
                + "".join(f', "{d}"' for d in dims)
                + "".join(f', "{n}"' for n in t["nums"])
                + f" FROM {src} WHERE {lon} BETWEEN -180 AND 180 AND {lat} BETWEEN -90 AND 90"
            )
            for res in RES:
                d = "".join(f', "{x}"' for x in dims)
                sums = "".join(f', sum("{n}") AS "{n}_sum"' for n in t["nums"])
                q = (
                    f"SELECT h3, h3_cell_to_lng(h3) AS lon, h3_cell_to_lat(h3) AS lat{d}, count(*) AS n{sums} "
                    f"FROM (SELECT *, h3_latlng_to_cell(lat, lon, {res}) AS h3 FROM base) GROUP BY ALL"
                )
                name = f"{t['table'].replace('.', '__')}_r{res}"
                lk.write(con, name, q, sort=["h3"], meta={
                    "source_table": t["table"], "h3_res": str(res), "dims": ",".join(dims),
                    "rule": "the sum over the cells whose centre lies inside an area (rows near its border count with their cell)",
                })  # fmt: skip
            print(
                f"  {t['table']}: {t['rows']:,} rows, dims {dims}, sums {t['nums']} in {time.time() - t0:.0f} s",
                flush=True,
            )
        except duckdb.Error as e:
            print(f"  {t['table']}: failed ({type(e).__name__}: {str(e)[:200]})", flush=True)
    w.lake_done(lk, a.upload)


if __name__ == "__main__":
    main()
