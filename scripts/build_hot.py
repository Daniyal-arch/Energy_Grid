"""Tier 1 of brief 32: `hot.duckdb`, a native DuckDB file with the tables the agent and the app
query most, read from local disk instead of R2.

    python scripts/build_hot.py [--max-mb 50] [--out hot.duckdb] [--upload]

It holds, as plain tables with the same schemas and rows as their lake views:

- lake tables of at most `--max-mb` MB compressed and `--max-rows` rows, smallest first, until
  the file reaches 90 % of `--budget-mb` (the Lambda's /tmp is 2,048 MB); the rest stay in the
  lake and are listed in the log;
- every rollup (`rollups.*`), shape set (`shapes.*`) and the prepared answers
  (`prepared.answers`, Tier 0), whatever their size;
- the outline name index (`outlines.names`, `outlines.aliases`);

Tables are sorted by their position (lon, lat), id or name so DuckDB's zone maps skip blocks,
and get ART indexes on id columns other than the sort column. A table `_hot.tables` lists each table with its
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
    # the always-kept sets first, then the smallest tables: the most tables per MB of /tmp
    chosen.sort(
        key=lambda c: (
            not (c[0] in ALWAYS or f"{c[0]}.{c[1]}" in NAME_INDEX),
            c[2].get("rows") or 0,
        )
    )
    stop_mb = a.budget_mb * 0.9  # the next table may add up to ~100 MB (1 M rows at most)
    left: list[str] = []
    for ds, t, info in chosen:
        must = ds in ALWAYS or f"{ds}.{t}" in NAME_INDEX
        if not must and (left or a.out.stat().st_size > stop_mb * 1e6):
            left.append(f"{ds}.{t}")  # stays in the lake (Tier 2)
            continue
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
            # ART indexes on id columns only, and not on the sort column (zone maps cover it):
            # an index on 3.4 M names costs hundreds of MB the sorted table does not need
            for k in ID_COLS:
                if (
                    k in low
                    and q(low[k]) != order
                    and not cols[low[k]]
                    .upper()
                    .startswith(("STRUCT", "LIST", "MAP", "GEOMETRY", "BLOB"))
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
            src.execute("CHECKPOINT hot")
            print(
                f"  {ds}.{t}: {rows:,} rows (file {a.out.stat().st_size / 1e6:,.0f} MB)", flush=True
            )
        except duckdb.Error as e:
            print(f"  {ds}.{t}: skipped ({type(e).__name__}: {str(e)[:160]})", flush=True)
    if left:
        print(f"{len(left)} tables left in the lake (budget {a.budget_mb:,.0f} MB): {', '.join(left[:40])}"
              + (" ..." if len(left) > 40 else ""))  # fmt: skip
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
