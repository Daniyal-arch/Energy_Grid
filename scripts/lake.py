"""The data lake's writer (docs/DATA_LAKE.md): Parquet files by the lake's standard, each
dataset's `_catalog.json`, and the upload to R2 (private bucket infraatlas-raw, prefix lake/).

Every pipeline that keeps full detail uses this module, so all files share one standard:
DuckDB `COPY`, Parquet v2, zstd level 9, ~1 M-row row groups, rows sorted by the table's
filter columns (one ordered file per partition: DuckDB's partitioned writer does not keep the
order), bloom filters on dictionary-encoded columns (DuckDB writes them), and key-value
metadata naming the source. Files stay under MAX_ROWS_PER_FILE rows (≈ 250 MB; wrangler's
single upload limit is ~300 MB).

    lake = Lake("eaglei", Path("lake-out"), source="EAGLE-I ...", licence="CC BY 4.0",
                script="scripts/build_us_outages.py")
    lake.write(con, "outages", "SELECT fips, ts, customers_out FROM ...",
               sort=["fips", "ts"], bloom=["fips"], partition={"year": "2024"})
    lake.finish()          # writes lake-out/eaglei/_catalog.json
    lake.upload()          # GitHub Actions only: needs CLOUDFLARE_API_TOKEN

Readers: `read_parquet('s3://infraatlas-raw/lake/eaglei/outages/*/*.parquet',
hive_partitioning=true)` with an R2 S3 secret in DuckDB.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import duckdb

BUCKET = "infraatlas-raw"  # private
PREFIX = "lake"
ACCOUNT_ID = (
    "a8ebfc5ad3d6228569de28c66a5f6367"  # the Cloudflare account (not a secret), as fetch_gem.py
)
MAX_ROWS_PER_FILE = 25_000_000
COPY_OPTIONS = "FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 9, ROW_GROUP_SIZE 1000000, PARQUET_VERSION V2"


@dataclass
class TableInfo:
    partitions: list[str]
    sort: list[str]
    bloom: list[str]
    columns: dict[str, str] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)
    rows: int = 0
    bytes: int = 0


def _quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


class Lake:
    """One dataset's tables under `root/<dataset>/`."""

    def __init__(
        self,
        dataset: str,
        root: Path,
        *,
        source: str,
        licence: str,
        script: str,
        source_version: str | None = None,
    ) -> None:
        self.dataset = dataset
        self.root = root
        self.dir = root / dataset
        self.meta = {
            "source": source,
            "licence": licence,
            "script": script,
            "source_version": source_version or "",
            "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        self.tables: dict[str, TableInfo] = {}

    def write(
        self,
        con: duckdb.DuckDBPyConnection,
        table: str,
        query: str,
        *,
        sort: list[str],
        bloom: list[str] | None = None,
        partition: dict[str, str] | None = None,
        stem: str = "part",
    ) -> list[Path]:
        """Write the query's rows, sorted, as one partition of `table` (or the whole table).

        `sort` may hold expressions (e.g. `ST_Hilbert(geometry, ...)` for spatial tables).
        `stem` names the files (`<stem>-0.parquet`): parallel jobs writing into one partition
        each use their own stem. Returns the files written.
        """
        partition = partition or {}
        info = self.tables.setdefault(table, TableInfo(list(partition), sort, bloom or []))
        folder = self.dir / table
        for k, v in partition.items():
            folder = folder / f"{k}={v}"
        folder.mkdir(parents=True, exist_ok=True)
        con.execute(f"CREATE OR REPLACE TEMP TABLE _lake_rows AS {query}")
        n = con.execute("SELECT count(*) FROM _lake_rows").fetchone()[0]  # type: ignore[index]
        if not info.columns:
            info.columns = {r[0]: r[1] for r in con.execute("DESCRIBE _lake_rows").fetchall()}
        kv = ", ".join(f'"{k}": {_quote(str(v))}' for k, v in {**self.meta, "table": table}.items())
        order = ", ".join(sort)
        files: list[Path] = []
        parts = max(1, -(-n // MAX_ROWS_PER_FILE))
        for i in range(parts):
            path = folder / f"{stem}-{i}.parquet"
            window = (
                f"LIMIT {MAX_ROWS_PER_FILE} OFFSET {i * MAX_ROWS_PER_FILE}" if parts > 1 else ""
            )
            con.execute(
                f"COPY (SELECT * FROM _lake_rows ORDER BY {order} {window}) TO {_quote(str(path))} "
                f"({COPY_OPTIONS}, KV_METADATA {{{kv}}})"
            )
            files.append(path)
            info.files.append(path.relative_to(self.dir).as_posix())
            info.bytes += path.stat().st_size
        info.rows += n
        con.execute("DROP TABLE _lake_rows")
        print(
            f"  lake/{self.dataset}/{table} {partition or ''}: {n:,} rows, {parts} file(s)",
            flush=True,
        )
        return files

    def catalog(self) -> dict:
        return {
            "dataset": self.dataset,
            **{k: v for k, v in self.meta.items() if k != "retrieved_at"},
            "updated": self.meta["retrieved_at"],
            "tables": {
                name: {
                    "path": f"{PREFIX}/{self.dataset}/{name}/"
                    + "".join(f"{p}=*/" for p in t.partitions)
                    + "*.parquet",
                    "partitions": t.partitions,
                    "sort": t.sort,
                    "bloom": t.bloom,
                    "rows": t.rows,
                    "bytes": t.bytes,
                    "columns": t.columns,
                    "files": t.files,
                }
                for name, t in self.tables.items()
            },
        }

    def finish(self) -> Path:
        """Write `_catalog.json`; a partial run (one partition) merges into an existing one."""
        path = self.dir / "_catalog.json"
        cat = self.catalog()
        if path.exists():
            old = json.loads(path.read_text(encoding="utf-8"))
            for name, t in old.get("tables", {}).items():
                if name in cat["tables"]:
                    new = cat["tables"][name]
                    kept = [f for f in t["files"] if f not in new["files"]]
                    new["files"] = sorted(kept + new["files"])
                else:
                    cat["tables"][name] = t
        path.write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding="utf-8")
        return path

    def upload(self, *, catalog_only: bool = False, catalog: bool = True) -> None:
        """Upload this run's files, then the catalogue, to r2://infraatlas-raw/lake/<dataset>/.

        Parallel jobs pass `catalog=False` and a last job uploads `merge_catalogs()`'s result.
        """
        files = [] if catalog_only else [f for t in self.tables.values() for f in t.files]
        for rel in [*files, *(["_catalog.json"] if catalog else [])]:
            key = f"{BUCKET}/{PREFIX}/{self.dataset}/{rel}"
            print(f"  r2://{key}", flush=True)
            if not wrangler("r2", "object", "put", key, "--file", str(self.dir / rel), "--remote"):
                raise SystemExit(f"upload of {rel} to R2 failed")


def merge_catalogs(parts: list[dict]) -> dict:
    """One catalogue from parallel jobs' catalogues of the same dataset (rows, bytes, files summed)."""
    out = json.loads(json.dumps(parts[0]))
    for part in parts[1:]:
        out["updated"] = max(out["updated"], part["updated"])
        for name, t in part["tables"].items():
            if name not in out["tables"]:
                out["tables"][name] = t
                continue
            o = out["tables"][name]
            o["rows"] += t["rows"]
            o["bytes"] += t["bytes"]
            o["files"] = sorted(set(o["files"]) | set(t["files"]))
    return out


def wrangler(*args: str) -> bool:
    npx = shutil.which("npx")
    if not npx:
        raise SystemExit("npx (Node.js) is needed for R2")
    env = {**os.environ}
    env.setdefault("CLOUDFLARE_ACCOUNT_ID", ACCOUNT_ID)
    if not env.get("CLOUDFLARE_API_TOKEN"):
        raise SystemExit("CLOUDFLARE_API_TOKEN is not set: uploads run in GitHub Actions")
    env.setdefault("WRANGLER_SEND_METRICS", "false")
    cmd = [npx, "--yes", "--package=wrangler@4", "--", "wrangler", *args]
    return subprocess.run(cmd, env=env, check=False, stdin=subprocess.DEVNULL).returncode == 0
