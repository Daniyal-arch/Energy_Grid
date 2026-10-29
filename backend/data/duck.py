"""One DuckDB connection per container over the lake and the app's map files.

The lake (docs/DATA_LAKE.md): `lake.duckdb` holds one schema per dataset with a view per table
over its R2 path; it is attached read-only as catalog `lake` and made the default, so the
catalogue's names work as written (`registers.gb`, `eaglei.outages`). Without R2 (tests, local
runs) a directory of Parquet files (`<dataset>/<table>.parquet` or `<dataset>/<table>/` with
Hive partitions) becomes the same schemas and views. The app's map files that hold rows (plants,
substations, prices per zone) are tables in catalog `app` (`app.eu_plants`, ...).

Locked down after setup: extensions only from the image, no persistent secrets, external
access only to the allowed directories, configuration locked. Each query runs on its own cursor
with a timeout (interrupt).
"""

from __future__ import annotations

import csv
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from app.settings import Settings
from data.guard import check
from obs.tracing import span

log = logging.getLogger(__name__)
CA_CANDIDATES = [
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/ssl/cert.pem",
]


@dataclass
class Source:
    dataset: str
    table: str
    licence: str
    retrieved: str

    def as_dict(self) -> dict[str, str]:
        return {
            "dataset": self.dataset,
            "table": self.table,
            "licence": self.licence,
            "retrieved": self.retrieved,
        }


@dataclass
class QueryResult:
    sql: str
    columns: list[str]
    types: list[str]
    rows: list[list[Any]]
    ms: float
    truncated: bool
    tables: list[str] = field(default_factory=list)


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, bool | int | str):
        return v
    if isinstance(v, float):
        return v if v == v and v not in (float("inf"), float("-inf")) else None
    if isinstance(v, Decimal):
        return float(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, list | tuple):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    return str(v)


class Lake:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.sources: dict[str, Source] = {}  # table name -> source
        self.lake_mode = "none"
        self.catalog_date: str | None = None
        self.allowed: list[str] = []
        self.con = self._open()

    # ------------------------------------------------------------------ setup
    def _open(self) -> duckdb.DuckDBPyConnection:
        s = self.settings
        config: dict[str, Any] = {"autoinstall_known_extensions": False}
        if s.duckdb_extension_dir:
            config["extension_directory"] = str(s.duckdb_extension_dir)
        con = duckdb.connect(":memory:", config=config)
        for ext in ("httpfs", "spatial"):
            try:
                con.load_extension(ext)
            except duckdb.Error:
                log.warning("duckdb extension not loaded", extra={"extension": ext})
        Path("/tmp/duckdb").mkdir(parents=True, exist_ok=True)
        con.execute(f"SET memory_limit = '{s.duckdb_memory_limit}'")
        con.execute("SET temp_directory = '/tmp/duckdb'")
        con.execute("SET allow_persistent_secrets = false")
        if s.r2_configured:
            con.execute(
                "CREATE SECRET r2 (TYPE r2, KEY_ID ?, SECRET ?, ACCOUNT_ID ?)",
                [s.r2_access_key_id, s.r2_secret_access_key, s.r2_account_id],
            )
        con.execute("ATTACH ':memory:' AS app")
        self._attach_lake(con)
        self._load_app_tables(con)
        self._lock(con)
        return con

    def _attach_lake(self, con: duckdb.DuckDBPyConnection) -> None:
        s = self.settings
        if s.lake_dir and Path(s.lake_dir).is_dir():
            con.execute("ATTACH ':memory:' AS lake")
            root = Path(s.lake_dir)
            for ds in sorted(p for p in root.iterdir() if p.is_dir()):
                con.execute(f'CREATE SCHEMA IF NOT EXISTS lake."{ds.name}"')
                for t in sorted(ds.iterdir()):
                    if t.suffix == ".parquet":
                        name, glob = t.stem, str(t)
                    elif t.is_dir():
                        name, glob = t.name, str(t / "**" / "*.parquet")
                    else:
                        continue
                    con.execute(
                        f'CREATE VIEW lake."{ds.name}"."{name}" AS SELECT * FROM '
                        f"read_parquet('{glob}', hive_partitioning = true)"
                    )
            con.execute("USE lake")
            self.lake_mode = f"local:{root}"
            cat = root / "_catalog.json"
            if cat.exists():
                self.catalog_date = json.loads(cat.read_text(encoding="utf-8")).get("updated")
            return
        if s.lake_db and s.r2_configured:
            local = s.lake_db
            if s.lake_db.startswith("r2://"):
                local = "/tmp/lake.duckdb"
                if not Path(local).exists():
                    _download_r2(s, s.lake_db, local)
                cat = "/tmp/lake_catalog.json"
                try:
                    _download_r2(s, s.lake_db.rsplit("/", 1)[0] + "/_catalog.json", cat)
                    self.catalog_date = json.loads(Path(cat).read_text(encoding="utf-8")).get(
                        "updated"
                    )
                except Exception:
                    log.warning("lake catalogue not read")
            con.execute(f"ATTACH '{local}' AS lake (READ_ONLY)")
            con.execute("USE lake")
            self.lake_mode = f"r2:{s.lake_db}"
            return
        con.execute("ATTACH ':memory:' AS lake")
        con.execute("USE lake")
        log.warning("lake not configured: only the app tables are queryable")

    def _load_app_tables(self, con: duckdb.DuckDBPyConnection) -> None:
        """Rows of the app's own map files as tables in catalog `app` (via CSV in /tmp)."""
        pub = self.settings.public_dir
        tmp = Path("/tmp/atlas-app")
        tmp.mkdir(parents=True, exist_ok=True)

        def table(
            name: str,
            cols: list[tuple[str, str]],
            rows: list[list[Any]],
            src: Source,
        ) -> None:
            path = tmp / f"{name}.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows(rows)
            spec = ", ".join(f"'{c}': '{t}'" for c, t in cols)
            con.execute(
                f"CREATE TABLE app.{name} AS SELECT * FROM read_csv('{path}', header = false, "
                f"columns = {{{spec}}}, nullstr = '')"
            )
            self.sources[f"app.{name}"] = src

        def load(rel: str) -> dict | None:
            p = pub / rel
            if not p.exists():
                log.warning("map file missing", extra={"file": str(p)})
                return None
            return json.loads(p.read_text(encoding="utf-8"))

        plants = load("eu/plants.json")
        if plants:
            g = plants["groups"]
            table(
                "eu_plants",
                [
                    ("fuel", "VARCHAR"),
                    ("mw", "DOUBLE"),
                    ("lon", "DOUBLE"),
                    ("lat", "DOUBLE"),
                    ("country", "VARCHAR"),
                    ("name", "VARCHAR"),
                    ("year", "INTEGER"),
                ],
                [[g[p[0]], *p[1:7]] for p in plants["plants"]],
                Source(
                    "plants", "frontend/public/data/eu/plants.json", "CC BY 4.0", plants["source"]
                ),
            )
        grid = load("eu/grid.json")
        if grid:
            table(
                "eu_substations",
                [("kv", "INTEGER"), ("lon", "DOUBLE"), ("lat", "DOUBLE"), ("country", "VARCHAR")],
                [s[:4] for s in grid["substations"]],
                Source("grid", "frontend/public/data/eu/grid.json", "ODbL", grid["source"]),
            )
        prices = load("eu/prices.json")
        if prices:
            p0, p1 = prices["period"]
            table(
                "eu_prices",
                [
                    ("zone", "VARCHAR"),
                    ("country", "VARCHAR"),
                    ("mean_eur_mwh", "DOUBLE"),
                    ("negative_hours", "DOUBLE"),
                    ("min_eur_mwh", "DOUBLE"),
                    ("min_at_utc", "TIMESTAMP"),
                    ("max_eur_mwh", "DOUBLE"),
                    ("max_at_utc", "TIMESTAMP"),
                    ("period_start", "DATE"),
                    ("period_end", "DATE"),
                ],
                [
                    [
                        z,
                        v["country"],
                        v.get("mean"),
                        v.get("negative_hours"),
                        *_extreme(v.get("min")),
                        *_extreme(v.get("max")),
                        p0,
                        p1,
                    ]
                    for z, v in prices["zones"].items()
                ],
                Source(
                    "prices",
                    "frontend/public/data/eu/prices.json",
                    "ENTSO-E Transparency Platform terms",
                    f"{prices['source']} (fetched {prices.get('fetched', '')[:10]})",
                ),
            )
        world = load("eu/world_plants.json")
        if world:
            ty, st = world["types"], world["statuses"]
            table(
                "world_plants",
                [
                    ("type", "VARCHAR"),
                    ("status", "VARCHAR"),
                    ("mw", "DOUBLE"),
                    ("lon", "DOUBLE"),
                    ("lat", "DOUBLE"),
                    ("year", "INTEGER"),
                ],
                [
                    [ty[p[2]], st[p[3]], p[4], p[0], p[1], p[5] if len(p) > 5 else None]
                    for p in world["points"]
                ],
                Source(
                    "world_plants",
                    "frontend/public/data/eu/world_plants.json",
                    "CC BY 4.0 (Global Energy Monitor)",
                    f"{world['source']} (fetched {world.get('fetched', '')[:10]})",
                ),
            )
        us = load("us/plants.json")
        if us:
            ty, st, names = us["types"], us["statuses"], us["plants"]
            table(
                "us_plants",
                [
                    ("name", "VARCHAR"),
                    ("state", "VARCHAR"),
                    ("type", "VARCHAR"),
                    ("status", "VARCHAR"),
                    ("mw", "DOUBLE"),
                    ("year", "INTEGER"),
                    ("lon", "DOUBLE"),
                    ("lat", "DOUBLE"),
                ],
                [
                    [
                        names[p[6]][0] if len(p) > 6 and p[6] < len(names) else None,
                        names[p[6]][1] if len(p) > 6 and p[6] < len(names) else None,
                        ty[p[2]],
                        st[p[3]],
                        p[4],
                        p[5],
                        p[0],
                        p[1],
                    ]
                    for p in us["points"]
                ],
                Source(
                    "us_plants",
                    "frontend/public/data/us/plants.json",
                    "public domain (EIA)",
                    f"{us['source']} ({us.get('release', '')})",
                ),
            )

    def _lock(self, con: duckdb.DuckDBPyConnection) -> None:
        s = self.settings
        allowed = [str(s.public_dir) + "/", s.public_data_remote, s.snapshot_remote]
        if s.lake_dir:
            allowed.append(str(Path(s.lake_dir)) + "/")
        if s.r2_configured:
            allowed.append(f"r2://{s.r2_lake_bucket}/lake/")
        self.allowed = allowed
        dirs = ", ".join(f"'{a}'" for a in allowed)
        con.execute(f"SET allowed_directories = [{dirs}]")
        ca = os.environ.get("SSL_CERT_FILE") or next(
            (c for c in CA_CANDIDATES if Path(c).exists()), None
        )
        if ca:
            con.execute(f"SET ca_cert_file = '{ca}'")
            con.execute(f"SET allowed_paths = ['{ca}']")
        con.execute("SET enable_external_access = false")
        con.execute("SET lock_configuration = true")

    # ------------------------------------------------------------------ queries
    def cursor(self) -> duckdb.DuckDBPyConnection:
        """A cursor (own connection to the same database) with the lake as default catalog."""
        cur = self.con.cursor()
        cur.execute("USE lake")
        return cur

    def tables(self) -> list[str]:
        rows = (
            self.con.cursor()
            .execute(
                "SELECT table_catalog, table_schema, table_name FROM information_schema.tables "
                "WHERE table_catalog IN ('lake', 'app') ORDER BY 1, 2, 3"
            )
            .fetchall()
        )
        return [f"{c}.{t}" if c == "app" else f"{s}.{t}" for c, s, t in rows]

    def run(self, sql: str, *, timeout_s: float | None = None, guard: bool = True) -> QueryResult:
        """Check (unless an internal query), run with a timeout, keep up to sql_rows_kept rows."""
        s = self.settings
        tables: list[str] = []
        if guard:
            checked = check(sql, allowed_paths=self.allowed, max_rows=s.sql_rows_kept + 1)
            sql, tables = checked.sql, checked.tables
        cur = self.cursor()
        timer = threading.Timer(timeout_s or s.sql_timeout_s, cur.interrupt)
        t0 = time.perf_counter()
        with span("sql.query", {"db.system": "duckdb", "db.statement.hash": _hash(sql)}) as sp:
            timer.start()
            try:
                cur.execute(sql)
                rows = cur.fetchmany(s.sql_rows_kept + 1)
            except duckdb.InterruptException as e:
                raise TimeoutError(
                    f"query stopped after {timeout_s or s.sql_timeout_s:.0f} s"
                ) from e
            finally:
                timer.cancel()
            cols = [d[0] for d in cur.description or []]
            types = [str(d[1]) for d in cur.description or []]
            ms = (time.perf_counter() - t0) * 1000
            sp.set_attribute("db.rows", len(rows))
            sp.set_attribute("db.ms", round(ms, 1))
        truncated = len(rows) > s.sql_rows_kept
        return QueryResult(
            sql=sql,
            columns=cols,
            types=types,
            rows=[[_jsonable(v) for v in r] for r in rows[: s.sql_rows_kept]],
            ms=ms,
            truncated=truncated,
            tables=tables,
        )

    def source_for(self, table: str, catalog: dict[str, dict] | None = None) -> Source:
        if table in self.sources:
            return self.sources[table]
        ds = table.split(".")[0]
        entry = (catalog or {}).get(ds, {})
        return Source(
            ds,
            table,
            str(entry.get("licence", "see agent/catalog")),
            self.catalog_date or "lake catalogue",
        )


def _extreme(v: list | None) -> list[Any]:
    """[price, '2026-01-07T01:00:00+00:00'] -> [price, naive UTC timestamp]."""
    if not v:
        return [None, None]
    return [v[0], str(v[1])[:19] if v[1] else None]


def _hash(sql: str) -> str:
    import hashlib

    return hashlib.sha256(sql.encode()).hexdigest()[:16]


def _download_r2(s: Settings, url: str, dest: str) -> None:
    from data.r2 import s3_client

    bucket, key = url.removeprefix("r2://").split("/", 1)
    s3_client(s).download_file(bucket, key, dest)


_lake: Lake | None = None
_lock = threading.Lock()


def get_lake(settings: Settings) -> Lake:
    global _lake
    with _lock:
        if _lake is None:
            _lake = Lake(settings)
        return _lake


def reset_lake() -> None:
    global _lake
    _lake = None
