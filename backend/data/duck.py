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

import contextlib
import csv
import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
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
    # brief 32: where the rows came from ("hot": the local hot.duckdb; "lake": R2 or the app)
    tier: str = "lake"


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
        # brief 32 Tier 1: queries go to the catalog `fast` (hot.duckdb first, the lake for the
        # rest) once hot.duckdb is attached; until then to the lake
        self.default = "lake"
        self.hot_tables: set[str] = set()
        self._areas_seen: OrderedDict[str, bool] = OrderedDict()  # ids in areamem.areas
        self._areas_lock = threading.Lock()
        self._area_res: dict[str, int] = {}  # areas with H3 cells built: their resolution
        self._cells_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="area-cells")
        self._cells_jobs: dict[str, Future[None]] = {}  # area id -> its cell build
        self.hot_state: dict[str, Any] = {"ready": False}
        self._hot_done = threading.Event()
        self.con = self._open()
        self._start_hot()

    # ------------------------------------------------------------------ setup
    def _open(self) -> duckdb.DuckDBPyConnection:
        s = self.settings
        config: dict[str, Any] = {"autoinstall_known_extensions": False}
        if s.duckdb_extension_dir:
            config["extension_directory"] = str(s.duckdb_extension_dir)
        con = duckdb.connect(":memory:", config=config)
        for ext in ("httpfs", "spatial", "h3"):
            try:
                con.load_extension(ext)
            except duckdb.Error:
                log.warning("duckdb extension not loaded", extra={"extension": ext})
        Path("/tmp/duckdb").mkdir(parents=True, exist_ok=True)
        con.execute(f"SET memory_limit = '{s.duckdb_memory_limit}'")
        con.execute("SET temp_directory = '/tmp/duckdb'")
        con.execute("SET allow_persistent_secrets = false")
        # brief 30: keep Parquet footers and HTTP metadata of R2 objects between queries (the
        # same files are read again and again); each setting is skipped where unsupported
        for opt in ("enable_http_metadata_cache = true", "enable_external_file_cache = true"):
            try:
                con.execute(f"SET GLOBAL {opt}")
            except duckdb.Error:
                log.warning("duckdb setting not available", extra={"setting": opt})
        try:  # lon/lat axis order for geodesic areas and lengths (areas, in_area)
            con.execute("SET GLOBAL geometry_always_xy = true")
        except duckdb.Error:
            log.warning("geometry_always_xy not set (spatial not loaded)")
        if s.r2_configured:
            con.execute(
                "CREATE SECRET r2 (TYPE r2, KEY_ID ?, SECRET ?, ACCOUNT_ID ?)",
                [s.r2_access_key_id, s.r2_secret_access_key, s.r2_account_id],
            )
        con.execute("ATTACH ':memory:' AS app")
        # the areas queries use, parsed once per container and shared by every cursor (brief 32:
        # serialising and parsing a detailed outline cost 60-80 ms on every query)
        con.execute("ATTACH ':memory:' AS areamem")
        con.execute(
            "CREATE TABLE areamem.areas (area_id VARCHAR PRIMARY KEY, name VARCHAR, "
            "level VARCHAR, geometry GEOMETRY, xmin DOUBLE, ymin DOUBLE, xmax DOUBLE, ymax DOUBLE)"
        )
        # per area: the H3 cells wholly inside, and the outline clipped to each edge cell
        con.execute("CREATE TABLE areamem.cells (area_id VARCHAR, cell UBIGINT)")
        con.execute(
            "CREATE TABLE areamem.clips "
            "(area_id VARCHAR, cell UBIGINT, clip GEOMETRY, edge GEOMETRY)"
        )
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
                f"columns = {{{spec}}}, nullstr = '', quote = '\"', escape = '\"')"
            )
            self.sources[f"app.{name}"] = src

        def load(rel: str) -> dict | None:
            p = pub / rel
            if not p.exists():
                log.warning("map file missing", extra={"file": str(p)})
                return None
            return json.loads(p.read_text(encoding="utf-8"))

        # registry waves (9, 10, ...): every map file (scripts/wave9.py) as app.w<N>_<source id>
        wave_dirs = (
            sorted(d for d in (pub / "eu").iterdir() if re.fullmatch(r"w\d+", d.name))
            if (pub / "eu").exists()
            else []
        )
        for f in [f for d in wave_dirs for f in sorted(d.glob("*.json"))]:
            w9 = json.loads(f.read_text(encoding="utf-8"))
            fields, pts = w9.get("fields") or [], w9.get("points") or []
            if not fields or not pts:
                continue

            def kind(i: int, pts: list = pts) -> str:
                v = next((p[i] for p in pts if i < len(p) and p[i] is not None), None)
                return (
                    "DOUBLE"
                    if isinstance(v, int | float) and not isinstance(v, bool)
                    else "VARCHAR"
                )

            names = [
                re.sub(r"[^0-9a-z]+", "_", str(c).lower()).strip("_") or f"c{i}"
                for i, c in enumerate(fields)
            ]
            names = [n if n not in names[:i] else f"{n}_{i}" for i, n in enumerate(names)]
            table(
                f"{f.parent.name}_{f.stem}",
                [(n, kind(i)) for i, n in enumerate(names)],
                [[p[i] if i < len(p) else None for i in range(len(names))] for p in pts],
                Source(
                    f"{f.parent.name} {f.stem}",
                    f"frontend/public/data/eu/{f.parent.name}/{f.name}",
                    "see source",
                    str(w9.get("source", "")),
                ),
            )
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
        if grid:
            # the lines as geometries (km inside an area: km_inside, brief 27 A2)
            path = tmp / "eu_lines.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows(
                    [
                        ln[0],
                        "LINESTRING("
                        + ", ".join(
                            f"{ln[1][i]} {ln[1][i + 1]}" for i in range(0, len(ln[1]) - 1, 2)
                        )
                        + ")",
                    ]
                    for ln in grid["lines"]
                    if len(ln[1]) >= 4
                )
            try:
                con.execute(
                    f"CREATE TABLE app.eu_lines AS SELECT kv, ST_GeomFromText(wkt) AS geometry, "
                    "ST_Length_Spheroid(ST_GeomFromText(wkt)) / 1000 AS km "
                    f"FROM read_csv('{path}', "
                    "header = false, columns = {'kv': 'INTEGER', 'wkt': 'VARCHAR'})"
                )
                self.sources["app.eu_lines"] = Source(
                    "grid", "frontend/public/data/eu/grid.json", "ODbL", grid["source"]
                )
            except duckdb.Error:
                log.warning("app.eu_lines not built (spatial not loaded)")
        dcs = load("eu/datacentres.json")
        if dcs:
            table(
                "data_centres",
                [("lon", "DOUBLE"), ("lat", "DOUBLE"), ("code", "VARCHAR"), ("name", "VARCHAR")],
                [p[:4] for p in dcs["points"]],
                Source(
                    "datacentres",
                    "frontend/public/data/eu/datacentres.json",
                    "ODbL",
                    f"{dcs['source']} (fetched {dcs.get('fetched', '')[:10]})",
                ),
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
        hot = self._hot_local()
        if hot:
            allowed.append(str(Path(hot).parent) + "/")
        self.allowed = allowed
        dirs = ", ".join(f"'{a}'" for a in allowed)
        con.execute(f"SET allowed_directories = [{dirs}]")
        ca = os.environ.get("SSL_CERT_FILE") or next(
            (c for c in CA_CANDIDATES if Path(c).exists()), None
        )
        if not ca:  # no system bundle (Windows, macOS): certifi's, which httpx brings
            try:
                import certifi

                ca = certifi.where()
            except ImportError:
                ca = None
        if ca:
            # GLOBAL: cursors are new connections and would not see a session setting
            con.execute(f"SET GLOBAL ca_cert_file = '{ca}'")
            con.execute(f"SET allowed_paths = ['{ca}']")
        con.execute("SET enable_external_access = false")
        con.execute("SET lock_configuration = true")

    # ------------------------------------------------------------------ queries
    AREAS_KEPT = 300

    def register_areas(self, cur: duckdb.DuckDBPyConnection, areas: list[dict[str, Any]]) -> None:
        """The areas as the view `areas` and the area macros, on this cursor only; each
        outline is parsed once into the shared `areamem.areas` (most recently used kept)."""
        with self._areas_lock:
            new = [a for a in areas if a["area_id"] not in self._areas_seen]
            if new:
                cur.executemany(
                    "INSERT OR REPLACE INTO areamem.areas "
                    "VALUES (?, ?, ?, ST_GeomFromGeoJSON(?), ?, ?, ?, ?)",
                    [[a["area_id"], a["name"], a["level"], json.dumps(a["geometry"]), *a["bbox"]]
                     for a in new],
                )  # fmt: skip
                for a in new:  # in the background: the plain test answers until they are ready
                    self._cells_jobs[a["area_id"]] = self._cells_pool.submit(self._area_cells, a)
            for a in areas:
                self._areas_seen[a["area_id"]] = True
                self._areas_seen.move_to_end(a["area_id"])
            old = []
            while len(self._areas_seen) > max(self.AREAS_KEPT, len(areas)):
                old.append(self._areas_seen.popitem(last=False)[0])
            if old:
                for t in ("areas", "cells", "clips"):
                    cur.execute(
                        f"DELETE FROM areamem.{t} WHERE area_id IN (SELECT unnest(?))", [old]
                    )
                for i in old:
                    self._area_res.pop(i, None)
                    self._cells_jobs.pop(i, None)
        ids = ", ".join("'" + a["area_id"].replace("'", "''") + "'" for a in areas)
        cur.execute(
            f"CREATE TEMP VIEW areas AS SELECT * FROM areamem.areas WHERE area_id IN ({ids})"
        )
        for m in AREA_MACROS:
            cur.execute(m)

    CELLS_MAX_KM2 = 2_000_000.0  # larger areas (continents) keep the plain test
    # a query waits this long for its areas' cells (built in 0.1-2 s; the plain test on a
    # detailed region costs ~0.45 ms a point, 5-14 s for a region's 10,000-30,000 rows)
    CELLS_WAIT_S = 3.0

    def _wait_area_cells(self, areas: list[dict[str, Any]]) -> None:
        deadline = time.monotonic() + self.CELLS_WAIT_S
        for a in areas:
            job = self._cells_jobs.get(a["area_id"])
            if job is None or a["area_id"] in self._area_res:
                continue
            with contextlib.suppress(Exception):  # timeout: the plain test answers
                job.result(timeout=max(0.0, deadline - time.monotonic()))

    def _area_cells(self, a: dict[str, Any]) -> None:
        """(In a background thread.) H3 cells wholly inside the outline (a point there is
        inside) and, for every other cell touching it, the outline clipped to the cell buffered
        by ~1 m (a point there is inside the outline exactly when it is inside the clip, away
        from the clip's own outline where rounding could matter): `in_area` then tests a point
        against a few vertices instead of the whole outline (~0.45 ms a point for a detailed
        region; 20,000 points in a 60,000-vertex outline: 10 s plain, 60 ms with cells)."""
        if a["level"] in ("world", "bbox"):
            return
        from tools.area_sum import MARGIN_DEG, cells, resolution_for

        km2 = float(a.get("area_km2") or 0)
        if not km2:
            x0, y0, x1, y1 = a["bbox"]
            km2 = abs(x1 - x0) * abs(y1 - y0) * 111.0 * 111.0
        if km2 > self.CELLS_MAX_KM2:
            return
        res = resolution_for(km2) + 1  # one finer than the sums: fewer points near the edge
        cur = self.con.cursor()
        try:
            inner, edge = cells(cur, a["geometry"], res)
            aid = a["area_id"]
            if inner:
                cur.execute(
                    "INSERT INTO areamem.cells SELECT ?, unnest(?::UBIGINT[])", [aid, inner]
                )
            if edge:
                self._area_clips(cur, aid, edge, res, MARGIN_DEG)
            with self._areas_lock:
                if aid in self._areas_seen:
                    self._area_res[aid] = res
                else:  # dropped meanwhile
                    for t in ("cells", "clips"):
                        cur.execute(f"DELETE FROM areamem.{t} WHERE area_id = ?", [aid])
        except duckdb.Error as e:  # no h3 here: the plain test answers
            log.warning("area cells not built", extra={"error": str(e)[:200]})

    CLIP_GROUP_RES = 3  # edge cells grouped by their ancestor this many levels up
    CLIP_BATCH = 16  # groups clipped per statement (each row holds a copy of the outline)

    def _area_clips(self, cur: Any, aid: str, edge: list[int], res: int, margin: float) -> None:
        """The outline clipped to each edge cell, in two steps so that no statement copies a
        detailed outline into thousands of rows (a 200,000-vertex outline ran out of memory):
        first a piece per group of edge cells (the outline cut to the box around the group's
        buffered cells, a superset of every cell clip in it), then each cell from its piece."""
        up = max(0, res - self.CLIP_GROUP_RES)
        cur.execute(
            "CREATE OR REPLACE TEMP TABLE _edge AS SELECT c, h3_cell_to_parent(c, ?) AS p, "
            "ST_Buffer(ST_GeomFromText(h3_cell_to_boundary_wkt(c)), ?) AS cb "
            "FROM (SELECT unnest(?::UBIGINT[]) AS c)",
            [up, margin, edge],
        )
        cur.execute(
            "CREATE OR REPLACE TEMP TABLE _box AS SELECT p, ST_MakeEnvelope(min(ST_XMin(cb)), "
            "min(ST_YMin(cb)), max(ST_XMax(cb)), max(ST_YMax(cb))) AS box FROM _edge GROUP BY p"
        )
        cur.execute("CREATE OR REPLACE TEMP TABLE _piece (p UBIGINT, piece GEOMETRY)")
        groups = [r[0] for r in cur.execute("SELECT p FROM _box ORDER BY p").fetchall()]
        for i in range(0, len(groups), self.CLIP_BATCH):
            cur.execute(
                "INSERT INTO _piece SELECT b.p, ST_Intersection(a.geometry, b.box) FROM _box b, "
                "(SELECT geometry FROM areamem.areas WHERE area_id = ?) a "
                "WHERE b.p IN (SELECT unnest(?::UBIGINT[]))",
                [aid, groups[i : i + self.CLIP_BATCH]],
            )
        cur.execute(
            "INSERT INTO areamem.clips SELECT ?, c, clip, ST_Boundary(clip) FROM ("
            "SELECT e.c, ST_Intersection(pc.piece, e.cb) AS clip FROM _edge e JOIN _piece pc "
            "USING (p) WHERE NOT ST_IsEmpty(pc.piece)) WHERE NOT ST_IsEmpty(clip)",
            [aid],
        )
        for t in ("_edge", "_box", "_piece"):
            cur.execute(f"DROP TABLE IF EXISTS {t}")

    def wait_cells(self) -> None:
        """Until the cells of every area registered so far are built (tests, probes)."""
        self._cells_pool.submit(lambda: None).result()

    def cursor(self) -> duckdb.DuckDBPyConnection:
        """A cursor (own connection to the same database) with the lake as default catalog."""
        cur = self.con.cursor()
        cur.execute(f"USE {self.default}")
        return cur

    # ------------------------------------------------------------------ hot.duckdb (brief 32)
    def _hot_local(self) -> str | None:
        """Where hot.duckdb lives on this machine: the setting itself, or /tmp/hot/ for R2."""
        h = self.settings.hot_db
        if not h:
            return None
        if h.startswith("r2://"):
            return "/tmp/hot/hot.duckdb" if self.settings.r2_configured else None
        return h

    def _start_hot(self) -> None:
        if not self._hot_local():
            self._hot_done.set()
            return
        threading.Thread(target=self._load_hot, name="hot-duckdb", daemon=True).start()

    def wait_hot(self, timeout_s: float | None = None) -> bool:
        self._hot_done.wait(timeout_s)
        return bool(self.hot_state.get("ready"))

    def _load_hot(self) -> None:
        """Download (from R2) and attach hot.duckdb read-only, then build the catalog `fast`:
        one view per lake table, over the hot copy when there is one, else over the lake view,
        so every query path reads hot tables with no change to its SQL. The lake keeps
        answering while this runs."""
        t0 = time.perf_counter()
        local = self._hot_local()
        try:
            h = self.settings.hot_db or ""
            if h.startswith("r2://"):
                Path(local).parent.mkdir(parents=True, exist_ok=True)  # type: ignore[arg-type]
                if not Path(local).exists():  # type: ignore[arg-type]
                    _download_r2(self.settings, h, local)  # type: ignore[arg-type]
            t_dl = time.perf_counter() - t0
            cur = self.con.cursor()
            cur.execute(f"ATTACH '{local}' AS hot (READ_ONLY)")
            hot = {
                (sch, t)
                for sch, t in cur.execute(
                    "SELECT schema_name, table_name FROM duckdb_tables() "
                    "WHERE database_name = 'hot' AND schema_name <> '_hot'"
                ).fetchall()
            }
            lake = cur.execute(
                "SELECT schema_name, view_name FROM duckdb_views() "
                "WHERE database_name = 'lake' UNION SELECT schema_name, table_name "
                "FROM duckdb_tables() WHERE database_name = 'lake'"
            ).fetchall()
            cur.execute("ATTACH ':memory:' AS fast")
            schemas: set[str] = set()
            for sch, t in sorted(set(lake) | hot):
                if sch not in schemas:
                    cur.execute(f'CREATE SCHEMA IF NOT EXISTS fast."{sch}"')
                    schemas.add(sch)
                src = "hot" if (sch, t) in hot else "lake"
                cur.execute(f'CREATE VIEW fast."{sch}"."{t}" AS SELECT * FROM {src}."{sch}"."{t}"')
            self.hot_tables = {f"{sch}.{t}" for sch, t in hot}
            self.default = "fast"
            self.hot_state = {
                "ready": True,
                "tables": len(hot),
                "bytes": Path(local).stat().st_size,  # type: ignore[arg-type]
                "download_s": round(t_dl, 2),
                "ready_s": round(time.perf_counter() - t0, 2),
            }
            log.info("hot.duckdb attached", extra=self.hot_state)
        except Exception as e:  # noqa: BLE001 - the lake answers without it
            self.hot_state = {"ready": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
            log.warning("hot.duckdb not attached", extra=self.hot_state)
        finally:
            self._hot_done.set()

    def tables(self) -> list[str]:
        """The lake's and the app's tables (cached: the catalogue does not change while the
        service runs, and a search asked for it several times; brief 30)."""
        if getattr(self, "_tables", None) is None:
            self._tables = self._list_tables()
        return list(self._tables)

    def _list_tables(self) -> list[str]:
        rows = (
            self.con.cursor()
            .execute(
                "SELECT table_catalog, table_schema, table_name FROM information_schema.tables "
                "WHERE table_catalog IN ('lake', 'app') ORDER BY 1, 2, 3"
            )
            .fetchall()
        )
        return [f"{c}.{t}" if c == "app" else f"{s}.{t}" for c, s, t in rows]

    def run(
        self,
        sql: str,
        *,
        timeout_s: float | None = None,
        guard: bool = True,
        areas: list[dict[str, Any]] | None = None,
    ) -> QueryResult:
        """Check (unless an internal query), run with a timeout, keep up to sql_rows_kept rows.

        `areas` (records of data/areas.py) become the read-only view `areas` and the macros
        `in_area`, `area_geom`, `km_inside`, `km2_inside`, `intersects_area` on this query's
        cursor; `in_area(lon, lat, 'a_...')` with a literal id is expanded to a plain bounding
        box test first (so Parquet row groups are skipped) and the exact test after it.
        """
        s = self.settings
        tables: list[str] = []
        if guard:
            checked = check(sql, allowed_paths=self.allowed, max_rows=s.sql_rows_kept + 1)
            sql, tables = checked.sql, checked.tables
        cur = self.cursor()
        if areas:
            self.register_areas(cur, areas)
        if guard:
            if areas:
                if "_area(" in sql:  # in_area / intersects_area: use the cells when ready soon
                    self._wait_area_cells(areas)
                rewritten = expand_in_area(sql, areas, dict(self._area_res))
                if rewritten != sql:
                    sql = check(
                        rewritten, allowed_paths=self.allowed, max_rows=s.sql_rows_kept + 1
                    ).sql
            tables = [t for t in tables if t != "areas"]
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
        tier = (
            "hot"
            if tables and self.default == "fast" and all(t in self.hot_tables for t in tables)
            else "lake"
        )
        return QueryResult(
            sql=sql,
            columns=cols,
            types=types,
            rows=[[_jsonable(v) for v in r] for r in rows[: s.sql_rows_kept]],
            ms=ms,
            truncated=truncated,
            tables=tables,
            tier=tier,
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


AREA_MACROS = [
    "CREATE TEMP MACRO area_geom(aid) AS (SELECT geometry FROM areas WHERE area_id = aid)",
    "CREATE TEMP MACRO in_area(lon, lat, aid) AS ST_Contains(area_geom(aid), ST_Point(lon, lat))",
    "CREATE TEMP MACRO intersects_area(geom, aid, bb := NULL) AS "
    "ST_Intersects(geom, area_geom(aid))",
    # geodesic, on the WGS84 ellipsoid (geometry_always_xy is on)
    "CREATE TEMP MACRO km_inside(geom, aid) AS "
    "ST_Length_Spheroid(ST_Intersection(geom, area_geom(aid))) / 1000",
    "CREATE TEMP MACRO km2_inside(geom, aid) AS "
    "ST_Area_Spheroid(ST_Intersection(geom, area_geom(aid))) / 1e6",
]


def expand_in_area(
    sql: str, areas: list[dict[str, Any]], cells: dict[str, int] | None = None
) -> str:
    """`in_area(x, y, 'a_...')` -> `(x BETWEEN x0 AND x1 AND y BETWEEN y0 AND y1 AND
    ST_Contains(area_geom('a_...'), ST_Point(x, y)))`: literal bounds the Parquet reader can
    prune row groups with. Unknown ids and non-literal ids keep the macro."""
    import sqlglot
    from sqlglot import exp

    if "in_area" not in sql.lower() and "intersects_area" not in sql.lower():
        return sql
    by_id = {a["area_id"]: a for a in areas}
    tree = sqlglot.parse_one(sql, read="duckdb")
    changed = False

    def swap(node: exp.Expression) -> exp.Expression:
        nonlocal changed
        if not isinstance(node, exp.Anonymous):
            return node
        fn = str(node.this).lower()
        if fn == "intersects_area":
            return _swap_intersects(node)
        if fn != "in_area":
            return node
        args = node.expressions
        if len(args) != 3 or not (isinstance(args[2], exp.Literal) and args[2].is_string):
            return node
        a = by_id.get(args[2].this)
        if a is None:
            return node
        x, y = args[0].sql(dialect="duckdb"), args[1].sql(dialect="duckdb")
        if a["level"] == "world":
            text = f"({x} IS NOT NULL AND {y} IS NOT NULL)"
        else:
            x0, y0, x1, y1 = a["bbox"]
            box = f"{x} BETWEEN {x0!r} AND {x1!r} AND {y} BETWEEN {y0!r} AND {y1!r}"
            aid = a["area_id"]
            res = (cells or {}).get(aid)
            if a["level"] == "bbox":
                text = f"({box})"
            elif res is not None:
                # inside a cell wholly inside, or inside the outline clipped to its edge cell
                h = (
                    f"h3_latlng_to_cell(greatest(-90.0, least(90.0, ({y})::DOUBLE)), "
                    f"({x})::DOUBLE, {res})"
                )
                # the clip decides unless the point lies within 1e-9 degrees of the clip's own
                # outline (where clipping's rounding could matter): then the whole outline does
                pt = f"ST_Point({x}, {y})"
                text = (
                    f"({box} AND ({h} IN (SELECT cell FROM areamem.cells WHERE area_id = '{aid}') "
                    f"OR coalesce((SELECT CASE WHEN ST_DWithin(edge, {pt}, 1e-9) "
                    f"THEN ST_Contains(area_geom('{aid}'), {pt}) ELSE ST_Contains(clip, {pt}) END "
                    f"FROM areamem.clips WHERE area_id = '{aid}' AND cell = {h}), false)))"
                )
            else:
                text = f"({box} AND ST_Contains(area_geom('{aid}'), ST_Point({x}, {y})))"
        changed = True
        return sqlglot.parse_one(text, read="duckdb")

    def _swap_intersects(node: exp.Anonymous) -> exp.Expression:
        """intersects_area(geom, 'a_...', bbox): the GeoParquet bbox column's literal bounds
        first, then ST_Intersects."""
        nonlocal changed
        args = node.expressions
        if len(args) != 3 or not (isinstance(args[1], exp.Literal) and args[1].is_string):
            return node
        a = by_id.get(args[1].this)
        if a is None:
            return node
        g, bb = args[0].sql(dialect="duckdb"), args[2].sql(dialect="duckdb")
        x0, y0, x1, y1 = a["bbox"]
        text = (
            f"({bb}.xmin <= {x1!r} AND {bb}.xmax >= {x0!r} AND {bb}.ymin <= {y1!r} AND "
            f"{bb}.ymax >= {y0!r} AND ST_Intersects({g}, area_geom('{a['area_id']}')))"
        )
        changed = True
        return sqlglot.parse_one(text, read="duckdb")

    tree = tree.transform(swap)
    return tree.sql(dialect="duckdb") if changed else sql


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
