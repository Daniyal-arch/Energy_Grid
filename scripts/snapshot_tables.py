"""History by snapshot (brief 30 Track 3.2): copy the current rows of the lake tables whose
publishers overwrite them (room to connect, connection queues and registers) into
`lake/history/<dataset>__<table>/snapshot=<YYYY-MM-DD>/`, so their past states stay queryable.

A snapshot is written once per date and never overwritten or deleted; each row keeps every
column as published plus `snapshot` (the partition). The US markets' queues already keep their
own weekly partitions (`iso_queues/requests`, scripts/fetch_us_queues.py) and are not copied.

Which tables: every table of the datasets in DATASETS, and every wave 9/10 table whose id names
a queue, register or connection capacity (QUEUE_WORDS). Weekly in Actions (wave8.yml group H),
after the sources' own refreshes.

    python scripts/snapshot_tables.py [--date 2026-11-05] --lake lake-out --upload
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wave5_common as w  # noqa: E402

SCRIPT = "scripts/snapshot_tables.py"
DATASETS = (
    "connect_eu", "connect_harmonised", "capareseau", "econnextion", "eredes_capacity",
    "elia_hosting", "esb_heatmap", "pse_capacity", "registers", "netztransparenz",
)  # fmt: skip
QUEUE_WORDS = re.compile(
    r"queue|tec_register|_tec|register|embedded_capacity|connection|capacity_map|hosting", re.I
)


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial")
    key, secret = os.environ["AWS_ACCESS_KEY_ID"], os.environ["AWS_SECRET_ACCESS_KEY"]
    acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    con.execute(
        f"CREATE SECRET lake (TYPE r2, KEY_ID '{key}', SECRET '{secret}', ACCOUNT_ID '{acct}')"
    )
    return con


def tables(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    cat = json.loads(
        con.execute(
            "SELECT content FROM read_text('r2://infraatlas-raw/lake/_catalog.json')"
        ).fetchone()[0]
    )
    out = []
    for ds, d in (cat.get("datasets") or {}).items():
        for t, info in (d.get("tables") or {}).items():
            if ds in DATASETS or (ds in ("wave9", "wave10") and QUEUE_WORDS.search(t)):
                out.append((f"{ds}.{t}", f"r2://infraatlas-raw/{info['path']}"))
    return out


def done_before(con: duckdb.DuckDBPyConnection, name: str, date: str) -> bool:
    try:
        n = con.execute(
            f"SELECT count(*) FROM glob('r2://infraatlas-raw/lake/history/{name}/snapshot={date}/*.parquet')"
        ).fetchone()[0]
    except duckdb.Error:
        return False
    return bool(n)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(UTC).date().isoformat())
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    a = ap.parse_args()
    con = connect()
    todo = tables(con)
    print(f"{len(todo)} tables to keep: {', '.join(t for t, _ in todo)}", flush=True)
    lk = w.lake_for(
        "history",
        a.lake,
        "snapshots of tables their publishers overwrite",
        "as each source table",
        SCRIPT,
    )
    for full, path in todo:
        name = full.replace(".", "__")
        if done_before(con, name, a.date):
            print(f"  {full}: snapshot {a.date} exists, kept as it is", flush=True)
            continue
        t0 = time.time()
        try:
            cols = [
                r[0]
                for r in con.execute(
                    f"DESCRIBE SELECT * FROM read_parquet('{path}', hive_partitioning = true)"
                ).fetchall()
            ]
            geo = "geometry" in cols
            sel = "* EXCLUDE (bbox)" if "bbox" in cols else "*"
            q = f"SELECT {sel} FROM read_parquet('{path}', hive_partitioning = true)"
            lk.write(con, name, q, sort=[f'"{cols[0]}"'], partition={"snapshot": a.date},
                     geometry="geometry" if geo else None, stem=f"part-{a.date}",
                     meta={"source_table": full, "rule": "one partition per snapshot date, never overwritten"})  # fmt: skip
            print(f"  {full}: kept in {time.time() - t0:.0f} s", flush=True)
        except duckdb.Error as e:
            print(f"  {full}: failed ({type(e).__name__}: {str(e)[:200]})", flush=True)
    w.lake_done(lk, a.upload)


if __name__ == "__main__":
    main()
