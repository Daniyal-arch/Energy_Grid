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

Parallel jobs (one partition each): each job writes and uploads its files
(`upload(catalog=False)`) and keeps its `_catalog.json` as an artifact; a last job calls
`pull_catalog()`, `finish(partials=[...])` and `upload(catalog_only=True)`.

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
    # rows and bytes per file, so partial runs (one partition each) add up in the catalogue
    file_stats: dict[str, list[int]] = field(default_factory=dict)


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
        geometry: str | None = None,
    ) -> list[Path]:
        """Write the query's rows, sorted, as one partition of `table` (or the whole table).

        `sort` may hold expressions (e.g. `ST_Hilbert(geometry, ...)` for spatial tables).
        `geometry` names a GEOMETRY column (EPSG:4326 lon/lat, DuckDB spatial loaded): the file
        becomes GeoParquet 1.1 (WKB) with a `bbox` covering column. Returns the files written.
        """
        partition = partition or {}
        if geometry:
            query = (
                f"SELECT *, struct_pack(xmin := ST_XMin({geometry}), ymin := ST_YMin({geometry}), "
                f"xmax := ST_XMax({geometry}), ymax := ST_YMax({geometry})) AS bbox FROM ({query})"
            )
        info = self.tables.setdefault(table, TableInfo(list(partition), sort, bloom or []))
        folder = self.dir / table
        for k, v in partition.items():
            folder = folder / f"{k}={v}"
        folder.mkdir(parents=True, exist_ok=True)
        con.execute(f"CREATE OR REPLACE TEMP TABLE _lake_rows AS {query}")
        n = con.execute("SELECT count(*) FROM _lake_rows").fetchone()[0]  # type: ignore[index]
        if not info.columns:
            info.columns = {r[0]: r[1] for r in con.execute("DESCRIBE _lake_rows").fetchall()}
        meta = {**self.meta, "table": table}
        geo_option = ""
        if geometry:
            names = {"POINT": "Point", "LINESTRING": "LineString", "POLYGON": "Polygon"}
            names |= {f"MULTI{k}": f"Multi{v}" for k, v in names.items()}
            found = con.execute(
                f"SELECT DISTINCT ST_GeometryType({geometry})::VARCHAR FROM _lake_rows "
                f"WHERE {geometry} IS NOT NULL"
            ).fetchall()
            types = sorted(names.get(r[0], r[0]) for r in found)
            cover = {k: ["bbox", k] for k in ("xmin", "ymin", "xmax", "ymax")}
            meta["geo"] = json.dumps(
                {
                    "version": "1.1.0",
                    "primary_column": geometry,
                    "columns": {
                        geometry: {
                            "encoding": "WKB",
                            "geometry_types": types,
                            "covering": {"bbox": cover},
                        }
                    },
                }
            )
            geo_option = ", GEOPARQUET_VERSION 'NONE'"
        kv = ", ".join(f'"{k}": {_quote(str(v))}' for k, v in meta.items())
        order = ", ".join(sort)
        files: list[Path] = []
        parts = max(1, -(-n // MAX_ROWS_PER_FILE))
        for i in range(parts):
            path = folder / f"part-{i}.parquet"
            window = (
                f"LIMIT {MAX_ROWS_PER_FILE} OFFSET {i * MAX_ROWS_PER_FILE}" if parts > 1 else ""
            )
            con.execute(
                f"COPY (SELECT * FROM _lake_rows ORDER BY {order} {window}) TO {_quote(str(path))} "
                f"({COPY_OPTIONS}{geo_option}, KV_METADATA {{{kv}}})"
            )
            files.append(path)
            rel = path.relative_to(self.dir).as_posix()
            rows = con.execute(f"SELECT count(*) FROM {_quote(str(path))}").fetchone()[0]  # type: ignore[index]
            info.files.append(rel)
            info.file_stats[rel] = [rows, path.stat().st_size]
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
                    + "part-*.parquet",
                    "partitions": t.partitions,
                    "sort": t.sort,
                    "bloom": t.bloom,
                    "rows": t.rows,
                    "bytes": t.bytes,
                    "columns": t.columns,
                    "files": t.files,
                    "file_stats": t.file_stats,
                }
                for name, t in self.tables.items()
            },
        }

    def finish(self, partials: list[Path] | None = None) -> Path:
        """Write `_catalog.json`, merged into an existing one (a partial run writes one
        partition; `pull_catalog()` fetches the uploaded catalogue first) and into the partial
        catalogues of parallel jobs (`partials`). A file named again replaces its old entry;
        rows and bytes per table are the sums over its files."""
        path = self.dir / "_catalog.json"
        cat = self.catalog()
        olds = [json.loads(p.read_text(encoding="utf-8")) for p in partials or []]
        if path.exists():
            olds.insert(0, json.loads(path.read_text(encoding="utf-8")))
        for old in olds:
            cat["updated"] = max(cat["updated"], old.get("updated", ""))
            for name, t in old.get("tables", {}).items():
                new = cat["tables"].setdefault(name, {**t, "files": [], "file_stats": {}})
                if not new["columns"]:
                    new["columns"] = t.get("columns", {})
                stats = t.get("file_stats") or {}
                for f in t.get("files", []):
                    if f not in new["file_stats"] and f not in new["files"]:
                        new["files"].append(f)
                        if f in stats:
                            new["file_stats"][f] = stats[f]
        for t in cat["tables"].values():
            t["files"] = sorted(set(t["files"]))
            if len(t["file_stats"]) == len(t["files"]):
                t["rows"] = sum(v[0] for v in t["file_stats"].values())
                t["bytes"] = sum(v[1] for v in t["file_stats"].values())
        path.write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding="utf-8")
        return path

    def pull_catalog(self) -> bool:
        """Fetch the uploaded `_catalog.json` (GitHub Actions), so `finish()` merges into it."""
        self.dir.mkdir(parents=True, exist_ok=True)
        key = f"{BUCKET}/{PREFIX}/{self.dataset}/_catalog.json"
        path = self.dir / "_catalog.json"
        ok = wrangler("r2", "object", "get", key, "--file", str(path), "--remote")
        if not ok:
            path.unlink(missing_ok=True)
            print(f"  r2://{key}: none yet", flush=True)
        return ok

    def upload(self, *, catalog_only: bool = False, catalog: bool = True) -> None:
        """Upload this run's files, then the catalogue, to r2://infraatlas-raw/lake/<dataset>/.

        Parallel jobs upload their files with `catalog=False` and hand their partial catalogue
        to one last job, which merges them (`finish(partials)`) and uploads the catalogue."""
        files = [] if catalog_only else [f for t in self.tables.values() for f in t.files]
        for rel in [*files, *(["_catalog.json"] if catalog else [])]:
            key = f"{BUCKET}/{PREFIX}/{self.dataset}/{rel}"
            print(f"  r2://{key}", flush=True)
            if not wrangler("r2", "object", "put", key, "--file", str(self.dir / rel), "--remote"):
                raise SystemExit(f"upload of {rel} to R2 failed")


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


def iso_codes(con: duckdb.DuckDBPyConnection) -> None:
    """Table `iso_codes` (iso2, iso3, name) for the standard keys: ISO 3166-1 (pycountry),
    plus Kosovo's user-assigned XK/XKX (ENTSO-E, Eurostat)."""
    import pycountry

    rows = [(c.alpha_2, c.alpha_3, c.name) for c in pycountry.countries]
    rows.append(("XK", "XKX", "Kosovo"))
    con.execute("CREATE OR REPLACE TABLE iso_codes (iso2 VARCHAR, iso3 VARCHAR, name VARCHAR)")
    con.executemany("INSERT INTO iso_codes VALUES (?, ?, ?)", rows)
