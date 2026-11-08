"""Tier 1 of brief 32: `hot.duckdb`, a native DuckDB file with the tables the agent and the app
query most, read from local disk instead of R2.

    python scripts/build_hot.py [--max-mb 50] [--out hot.duckdb] [--upload]

It holds, as plain tables with the same schemas and rows as their lake views:

- every lake table whose files are at most `--max-mb` MB compressed (the lake catalogue's bytes);
- every rollup (`rollups.*`), shape set (`shapes.*`) and the prepared answers
  (`prepared.answers`, Tier 0), whatever their size;
- the outline name index (`outlines.names`, `outlines.aliases`);
- per outline set, `outlines_simple.<set>`: id, name, level, iso3, the bounding box and the
  outline simplified with a 0.001° (about 100 m) tolerance, for maps and large areas (answers
  that use it say so; exact answers read the full outline from the lake).

Tables are sorted by their position (lon, lat), id or name so DuckDB's zone maps skip blocks,
and get ART indexes on id and name-key columns. A table `_hot.tables` lists each table with its
source path, rows and the lake catalogue's date; a row count check against the lake view runs
for every table before the file is written. Runs in Actions (`.github/workflows/lake-catalog.yml`,
job `hot`) where R2 is readable, and uploads to `r2://infraatlas-raw/lake/hot.duckdb`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lake  # noqa: E402
from lake_catalog import R2, r2_secret  # noqa: E402

ALWAYS = ("rollups", "shapes", "prepared")
NAME_INDEX = ("outlines.names", "outlines.aliases")
ID_COLS = (
    "id",
    "uuid",
    "gid",
    "fid",
    "unit_id",
    "plant_id",
    "site_id",
    "eic",
    "code",
    "nuts_id",
    "admin1_id",
)
NAME_KEYS = ("name_norm", "alias_norm", "name")
SIMPLIFY_DEG = 0.001


def q(c: str) -> str:
    return '"' + c.replace('"', '""') + '"'


def sort_of(cols: dict[str, str]) -> str:
    low = {c.lower(): c for c in cols}
    if "h3" in low:
        return q(low["h3"])
    if "lon" in low and "lat" in low:
        return f"{q(low['lon'])}, {q(low['lat'])}"
    for k in (*NAME_KEYS, *ID_COLS):
        if k in low:
            return q(low[k])
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-mb", type=float, default=50.0)
    # rows matter more than Parquet bytes: a 20 MB file of 50 M repetitive rows is GBs in DuckDB
    ap.add_argument("--max-rows", type=int, default=1_000_000)
    # the Lambda's /tmp is 2,048 MB (deploy/template.yaml); the file must leave room for the rest
    ap.add_argument("--budget-mb", type=float, default=1_200.0)
    ap.add_argument("--out", type=Path, default=Path("hot.duckdb"))
    ap.add_argument("--upload", action="store_true")
    a = ap.parse_args()
    src = duckdb.connect()
    if not r2_secret(src):
        raise SystemExit("R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY not set: hot.duckdb needs R2")
    src.execute("INSTALL spatial; LOAD spatial")
    cat = json.loads(
        src.execute(
            f"SELECT content FROM read_text('{R2}/{lake.PREFIX}/_catalog.json')"
        ).fetchone()[0]
    )
    chosen: list[tuple[str, str, dict]] = []
    for ds, d in sorted((cat.get("datasets") or {}).items()):
        for t, info in sorted((d.get("tables") or {}).items()):
            full = f"{ds}.{t}"
            small = (info.get("bytes") or 0) <= a.max_mb * 1e6 and (
                info.get("rows") or 0
            ) <= a.max_rows
            if ds in ALWAYS or full in NAME_INDEX or (small and ds != "outlines"):
                chosen.append((ds, t, info))
    a.out.unlink(missing_ok=True)
    src.execute(f"ATTACH '{a.out}' AS hot")
    src.execute("CREATE SCHEMA hot._hot")
    src.execute(
        "CREATE TABLE hot._hot.tables (dataset VARCHAR, tbl VARCHAR, source VARCHAR, rows BIGINT, "
        "lake_bytes BIGINT, catalogue_date VARCHAR, built VARCHAR, kind VARCHAR)"
    )
    built = datetime.now(UTC).isoformat(timespec="seconds")
    t0, n_ok, n_rows = time.time(), 0, 0
    for ds, t, info in chosen:
        path = f"{R2}/{info['path']}"
        hive = "true" if info.get("partitions") else "false"
        view = f"read_parquet('{path}', hive_partitioning = {hive}, union_by_name = true)"
        try:
            cols = {
                r[0]: str(r[1]) for r in src.execute(f"DESCRIBE SELECT * FROM {view}").fetchall()
            }
            order = sort_of(cols)
            src.execute(f"CREATE SCHEMA IF NOT EXISTS hot.{q(ds)}")
            src.execute(
                f"CREATE TABLE hot.{q(ds)}.{q(t)} AS SELECT * FROM {view}"
                + (f" ORDER BY {order}" if order else "")
            )
            rows = src.execute(f"SELECT count(*) FROM hot.{q(ds)}.{q(t)}").fetchone()[0]
            want = src.execute(f"SELECT count(*) FROM {view}").fetchone()[0]
            if rows != want:
                raise SystemExit(f"{ds}.{t}: {rows} rows in hot, {want} in the lake")
            low = {c.lower(): c for c in cols}
            for k in (*ID_COLS, *NAME_KEYS):
                if k in low and not cols[low[k]].upper().startswith(
                    ("STRUCT", "LIST", "MAP", "GEOMETRY", "BLOB")
                ):
                    src.execute(
                        f"CREATE INDEX {q(f'ix_{ds}_{t}_{k}')} ON hot.{q(ds)}.{q(t)} ({q(low[k])})"
                    )
            src.execute(
                "INSERT INTO hot._hot.tables VALUES (?, ?, ?, ?, ?, ?, ?, 'table')",
                [ds, t, path, rows, info.get("bytes"), cat.get("updated"), built],
            )
            n_ok += 1
            n_rows += rows
            print(f"  {ds}.{t}: {rows:,} rows", flush=True)
        except duckdb.Error as e:
            print(f"  {ds}.{t}: skipped ({type(e).__name__}: {str(e)[:160]})", flush=True)
    # simplified outlines per set
    src.execute("CREATE SCHEMA IF NOT EXISTS hot.outlines_simple")
    for t, info in sorted(
        ((cat.get("datasets") or {}).get("outlines") or {}).get("tables", {}).items()
    ):
        if t in ("names", "aliases"):
            continue
        cols = info.get("columns") or {}
        if "geometry" not in cols:
            continue
        pick = [c for c in ("id", "name", "level", "iso3", "parent_name") if c in cols]
        path = f"{R2}/{info['path']}"
        hive = "true" if info.get("partitions") else "false"
        try:
            src.execute(
                f"CREATE TABLE hot.outlines_simple.{q(t)} AS SELECT {', '.join(q(c) for c in pick)}, "
                f"ST_XMin(geometry) AS xmin, ST_YMin(geometry) AS ymin, ST_XMax(geometry) AS xmax, "
                f"ST_YMax(geometry) AS ymax, ST_SimplifyPreserveTopology(geometry, {SIMPLIFY_DEG}) AS geometry "
                f"FROM read_parquet('{path}', hive_partitioning = {hive}, union_by_name = true)"
            )
            rows = src.execute(f"SELECT count(*) FROM hot.outlines_simple.{q(t)}").fetchone()[0]
            if "id" in pick:
                src.execute(
                    f"CREATE INDEX {q(f'ix_simple_{t}_id')} ON hot.outlines_simple.{q(t)} (id)"
                )
            src.execute(
                "INSERT INTO hot._hot.tables VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ["outlines_simple", t, path, rows, info.get("bytes"), cat.get("updated"), built,
                 f"outline simplified with a {SIMPLIFY_DEG} degree tolerance"],
            )  # fmt: skip
            print(f"  outlines_simple.{t}: {rows:,} outlines", flush=True)
        except duckdb.Error as e:
            print(f"  outlines_simple.{t}: skipped ({str(e)[:160]})", flush=True)
    src.execute("DETACH hot")
    size = a.out.stat().st_size
    print(
        f"hot.duckdb: {n_ok} tables, {n_rows:,} rows, {size / 1e6:,.0f} MB in {time.time() - t0:.0f} s"
    )
    if size > a.budget_mb * 1e6:
        raise SystemExit(
            f"hot.duckdb is {size / 1e6:,.0f} MB, above the {a.budget_mb:,.0f} MB budget: not uploaded"
        )
    if a.upload:
        acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or lake.ACCOUNT_ID
        subprocess.run(
            ["aws", "s3", "cp", "--only-show-errors", "--endpoint-url", f"https://{acct}.r2.cloudflarestorage.com",
             str(a.out), f"s3://{lake.BUCKET}/{lake.PREFIX}/hot.duckdb"],
            check=True,
        )  # fmt: skip
        print(f"uploaded to r2://{lake.BUCKET}/{lake.PREFIX}/hot.duckdb")


if __name__ == "__main__":
    main()
