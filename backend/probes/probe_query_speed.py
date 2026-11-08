"""Probe: the speed of every dataset query (brief 32, Step 1).

Runs a standard query set on every lake table and app table, in this process (no HTTP), on
the backend's own DuckDB connection, and records per query: cold time (its first run in this
process), warm times (three repeats), rows returned, and the bytes and requests DuckDB sent to
R2 (its HTTP log: GET bodies by Content-Length, HEAD and GET counts).

The query set per table, each where the table has the columns for it:

- `count`: `SELECT count(*)`;
- `lookup`: one row by its id (the first id-like column; the value is read first, untimed);
- `city`, `region`, `country`: the rows inside Berlin, Bavaria and Germany (or the country the
  table is named after: `fr_...` is France), with `in_area(lon, lat, ...)` for points,
  `intersects_area(geometry, ...)` for shapes, or the table's ISO column for the country when it
  has no position;
- `top10`: the 10 largest by its main measure;
- `by_class`: a sum of the measure by fuel, type or class.

Also (shard 0, `--extras`): every data route through the app (in process), every `quick`
template, `resolve_area` for 50 names at every level, `area_stats` for every raster measure.

Run it in the Lambda-sized container (2 vCPU, 3,008 MB) against the real lake:
`.github/workflows/backend-probe.yml` (job `query-speed`, eight shards). Locally without R2 it
measures the app tables only.

    uv run python -m probes.probe_query_speed --shard 0 --shards 8 --extras --json out.json
    uv run python -m probes.probe_query_speed --merge DIR   # shard files -> report and data
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

WARM = 3  # warm repeats per query
COLD_SKIP_S = 20.0  # a query slower than this cold is not repeated warm (recorded as skipped)
QUERY_TIMEOUT_S = 60.0
TABLE_BUDGET_S = 240.0  # a table's queries stop after this (the rest recorded as skipped)

ID_COLS = ("id", "uuid", "gid", "fid", "code", "eic", "unit_id", "plant_id", "site_id", "geo")
ISO3_COLS = ("iso3", "iso_a3", "country_iso3", "adm0_a3")
ISO2_COLS = ("iso2", "iso_a2", "country_code", "country", "cntr_code", "geo")
MEASURES = (
    "capacity_mw", "installed_capacity_mw", "capacity", "mw", "net_mw", "power_mw", "value",
    "obs_value", "population", "people", "area_km2", "volume", "quantity", "emissions",
    "total", "price",
)  # fmt: skip
CLASSES = (
    "fuel", "primary_fuel", "fuel_type", "energy_source", "technology", "type", "class",
    "category", "status", "kind", "source", "psr_type",
)  # fmt: skip
NUMERIC = ("INTEGER", "BIGINT", "DOUBLE", "FLOAT", "DECIMAL", "HUGEINT", "SMALLINT", "REAL")
# tables named after a country (wave 9 ids such as fr_odre_...): their own country
COUNTRY_BY_PREFIX = {
    "at": "Austria", "be": "Belgium", "bg": "Bulgaria", "ch": "Switzerland", "cy": "Cyprus",
    "cz": "Czechia", "dk": "Denmark", "ee": "Estonia", "es": "Spain", "fi": "Finland",
    "fr": "France", "gb": "United Kingdom", "gr": "Greece", "hr": "Croatia", "hu": "Hungary",
    "ie": "Ireland", "it": "Italy", "lt": "Lithuania", "lu": "Luxembourg", "lv": "Latvia",
    "mt": "Malta", "nl": "Netherlands", "no": "Norway", "pl": "Poland", "pt": "Portugal",
    "ro": "Romania", "rs": "Serbia", "se": "Sweden", "si": "Slovenia", "sk": "Slovakia",
    "us": "United States", "uk": "United Kingdom",
}  # fmt: skip

# 50 names at every level (country, region, county, city, neighbourhood, groups, zones)
RESOLVE_NAMES: list[tuple[str, str | None]] = [
    ("Germany", None), ("France", None), ("Poland", None), ("Spain", None), ("Italy", None),
    ("United States", None), ("Nordics", None), ("EU-27", None), ("Bavaria", None),
    ("Lower Saxony", None), ("Catalonia", None), ("Lombardy", None), ("Texas", None),
    ("California", None), ("Scotland", None), ("Brittany", None), ("Masovian Voivodeship", None),
    ("North Rhine-Westphalia", None), ("Andalusia", None), ("Upper Bavaria", None),
    ("Harris County", None), ("Cook County", None), ("Kreis Steinfurt", None),
    ("Greater Manchester", None), ("Cornwall", None), ("Berlin", "city"), ("Paris", "city"),
    ("Madrid", "city"), ("Rome", "city"), ("Warsaw", "city"), ("Toulouse", "city"),
    ("Lyon", "city"), ("Hamburg", "city"), ("Munich", "city"), ("Vienna", "city"),
    ("Amsterdam", "city"), ("Copenhagen", "city"), ("Dublin", "city"), ("Lisbon", "city"),
    ("Houston", "city"), ("Leeds", None), ("Manchester", None), ("Kreuzberg", None),
    ("Schwabing", None), ("Montmartre", None), ("DE-LU", None), ("NO2", None), ("IT-North", None),
    ("Sicily", None), ("Saxony-Anhalt", None),
]  # fmt: skip

ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/api/health", None),
    ("GET", "/api/catalog/search?q=solar%20capacity%20Germany", None),
    ("GET", "/api/catalog/atb", None),
    ("GET", "/api/places?q=Bavaria", None),
    ("GET", "/api/places?q=Lyon", None),
    ("GET", "/api/site?lon=11.58&lat=48.14&radius_km=50", None),
    ("GET", "/api/areas/resolve?q=Bavaria", None),
    ("GET", "/api/areas/resolve?q=Berlin&level=city", None),
    ("GET", "/api/shapes/admin1/DEU", None),
    ("GET", "/api/quick", None),
    ("GET", "/api/quick/profile?area=Germany", None),
    ("GET", "/api/quick/top?area=Bavaria&n=10", None),
    ("GET", "/api/quick/totals?area=Europe", None),
    ("GET", "/api/quick/published?area=France", None),
    ("GET", "/api/quick/prices?area=Germany", None),
    ("GET", "/api/report.json?lon=11.58&lat=48.14&radius_km=25&task=data_centre", None),
    ("GET", "/api/feed/DEU.json", None),
    ("POST", "/api/maps", {"spec": {"title": "probe", "app": {"layers": ["cables"]}}}),
]

QUICK: list[tuple[str, str, dict[str, Any]]] = [
    ("profile", "Germany", {}),
    ("profile", "Bavaria", {}),
    ("profile", "Berlin", {}),
    ("top", "Germany", {"n": 10}),
    ("top", "Bavaria", {"n": 10, "kind": "substations"}),
    ("top", "France", {"n": 10, "kind": "data_centres"}),
    ("totals", "Europe", {}),
    ("totals", "United States", {}),
    ("compare", "France; Germany", {}),
    ("published", "Poland", {}),
    ("prices", "Germany", {}),
]


def pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return xs[max(0, min(len(xs) - 1, round(p / 100 * (len(xs) - 1))))]


def ms(s: float | None) -> float | None:
    return None if s is None else round(s * 1000, 1)


class Http:
    """DuckDB's HTTP log: the bytes and requests a query sent (since a timestamp)."""

    def __init__(self, lake: Any) -> None:
        self.lake = lake
        self.on = True
        try:
            lake.cursor().execute("SELECT count(*) FROM duckdb_logs_parsed('HTTP')").fetchall()
        except Exception:  # noqa: BLE001 - logging not available: bytes are not recorded
            self.on = False

    def mark(self) -> Any:
        if not self.on:
            return None
        return self.lake.cursor().execute("SELECT now()::VARCHAR").fetchone()[0]

    def since(self, t: Any) -> dict[str, int | None]:
        if not self.on or t is None:
            return {"bytes": None, "gets": None, "heads": None}
        r = (
            self.lake.cursor()
            .execute(
                "SELECT coalesce(sum(CASE WHEN request.type = 'GET' THEN "
                "TRY_CAST(response.headers['Content-Length'] AS BIGINT) END), 0), "
                "count(*) FILTER (request.type = 'GET'), count(*) FILTER (request.type = 'HEAD') "
                "FROM duckdb_logs_parsed('HTTP') WHERE timestamp >= ?::TIMESTAMPTZ",
                [t],
            )
            .fetchone()
        )
        return {"bytes": int(r[0]), "gets": int(r[1]), "heads": int(r[2])}


def open_backend() -> tuple[Any, Any]:
    """The tool context and lake, with DuckDB's HTTP log switched on before the lockdown."""
    from app.settings import Settings
    from data import duck
    from tools.context import ToolContext

    original = duck.Lake._lock

    def lock(self: Any, con: Any) -> None:
        try:
            con.execute("CALL enable_logging('HTTP')")
        except Exception as e:  # noqa: BLE001
            print(f"HTTP log not enabled: {e}", file=sys.stderr)
        original(self, con)

    duck.Lake._lock = lock  # type: ignore[method-assign]
    ctx = ToolContext(Settings())
    return ctx, ctx.lake


def columns(lake: Any) -> dict[str, list[tuple[str, str]]]:
    rows = (
        lake.cursor()
        .execute(
            "SELECT table_catalog, table_schema, table_name, column_name, data_type "
            "FROM information_schema.columns WHERE table_catalog IN ('lake', 'app') "
            "ORDER BY 1, 2, 3, ordinal_position"
        )
        .fetchall()
    )
    out: dict[str, list[tuple[str, str]]] = {}
    for cat, sch, tab, col, typ in rows:
        name = f"app.{tab}" if cat == "app" else f"{sch}.{tab}"
        out.setdefault(name, []).append((col, typ))
    return out


def pick(cols: list[tuple[str, str]], names: tuple[str, ...], numeric: bool = False) -> str | None:
    by = {c.lower(): (c, t) for c, t in cols}
    for n in names:
        if n in by and (not numeric or by[n][1].upper().startswith(NUMERIC)):
            return by[n][0]
    return None


def q(c: str) -> str:
    return '"' + c.replace('"', '""') + '"'


def plan(table: str, cols: list[tuple[str, str]], area_ids: dict[str, str]) -> list[dict[str, Any]]:
    """The standard query set this table's columns allow."""
    lower = {c.lower(): c for c, _ in cols}
    types = {c: t.upper() for c, t in cols}
    out: list[dict[str, Any]] = [{"query": "count", "sql": f"SELECT count(*) FROM {table}"}]
    idc = pick(cols, ID_COLS) or next(
        (c for c, _ in cols if c.lower().endswith(("_id", "_code"))), None
    )
    if idc:
        out.append({"query": "lookup", "id": idc, "sql": None})
    lon = lower.get("lon") or lower.get("longitude") or lower.get("x")
    lat = lower.get("lat") or lower.get("latitude") or lower.get("y")
    geom = lower.get("geometry") or lower.get("geom")
    if geom and "GEOMETRY" not in types[geom]:
        geom_expr = f"ST_GeomFromWKB({q(geom)})" if "BLOB" in types[geom] else None
    else:
        geom_expr = q(geom) if geom else None

    # coordinates stored as text are cast (the Tier 2 rewrite types them; see the report)
    def num(c: str) -> str:
        return q(c) if types[c].startswith(NUMERIC) else f"TRY_CAST({q(c)} AS DOUBLE)"

    for level in ("city", "region", "country"):
        aid = area_ids.get(level)
        if not aid:
            continue
        if lon and lat:
            where = f"in_area({num(lon)}, {num(lat)}, '{aid}')"
        elif geom_expr:
            where = f"intersects_area({geom_expr}, '{aid}')"
        else:
            where = None
        if where:
            out.append(
                {
                    "query": level,
                    "sql": f"SELECT count(*) FROM {table} WHERE {where}",
                    "area": aid,
                }
            )
        elif level == "country":
            iso3, iso2 = pick(cols, ISO3_COLS), pick(cols, ISO2_COLS)
            code3, code2 = area_ids.get("country_iso3"), area_ids.get("country_iso2")
            if iso3 and code3:
                out.append(
                    {
                        "query": level,
                        "sql": f"SELECT count(*) FROM {table} WHERE {q(iso3)} = '{code3}'",
                    }
                )
            elif iso2 and code2:
                out.append(
                    {
                        "query": level,
                        "sql": f"SELECT count(*) FROM {table} WHERE {q(iso2)} = '{code2}'",
                    }
                )
    m = pick(cols, MEASURES, numeric=True) or next(
        (
            c
            for c, t in cols
            if t.upper().startswith(NUMERIC)
            and c != idc
            and c.lower() not in ("lon", "lat", "x", "y", "year")
        ),
        None,
    )
    if m:
        out.append(
            {
                "query": "top10",
                "sql": f"SELECT * FROM {table} ORDER BY {q(m)} DESC NULLS LAST LIMIT 10",
            }
        )
        k = pick(cols, CLASSES)
        if k:
            out.append(
                {
                    "query": "by_class",
                    "sql": f"SELECT {q(k)}, sum({q(m)}) FROM {table} GROUP BY 1 ORDER BY 2 DESC NULLS LAST",
                }
            )
    return out


def timed(lake: Any, http: Http, sql: str, areas: list[dict[str, Any]] | None) -> dict[str, Any]:
    t = http.mark()
    t0 = time.perf_counter()
    try:
        r = lake.run(sql, timeout_s=QUERY_TIMEOUT_S, areas=areas or None)
        rows: int | None = len(r.rows)
        if r.columns == ["count_star()"] or (len(r.rows) == 1 and len(r.rows[0]) == 1):
            rows = r.rows[0][0] if r.rows and isinstance(r.rows[0][0], int) else rows
        err = ""
    except Exception as e:  # noqa: BLE001 - the probe records every failure
        rows, err = None, f"{type(e).__name__}: {e}"[:200]
    s = time.perf_counter() - t0
    return {"s": s, "rows": rows, "error": err, **http.since(t)}


def probe_table(
    ctx: Any, http: Http, table: str, cols: list[tuple[str, str]], areas: dict[str, Any]
) -> dict[str, Any]:
    from tools.sql import query_areas

    own = COUNTRY_BY_PREFIX.get(table.split(".")[-1].split("_")[0])
    ids = dict(areas["default"])
    if own and own in areas["countries"]:
        ids.update(areas["countries"][own])
    t_start = time.perf_counter()
    rec: dict[str, Any] = {"table": table, "columns": len(cols), "queries": []}
    pos = {
        c.lower(): t.upper()
        for c, t in cols
        if c.lower() in ("lon", "lat", "longitude", "latitude")
    }
    rec["text_coordinates"] = any(t.startswith("VARCHAR") for t in pos.values())
    for item in plan(table, cols, ids):
        if time.perf_counter() - t_start > TABLE_BUDGET_S:
            rec["queries"].append({"query": item["query"], "skipped": "table time budget"})
            continue
        sql = item["sql"]
        if item["query"] == "lookup":
            try:
                v = ctx.lake.run(
                    f"SELECT {q(item['id'])} FROM {table} WHERE {q(item['id'])} IS NOT NULL LIMIT 1",
                    timeout_s=QUERY_TIMEOUT_S,
                ).rows
            except Exception as e:  # noqa: BLE001
                rec["queries"].append({"query": "lookup", "error": str(e)[:200]})
                continue
            if not v:
                continue
            val = v[0][0]
            lit = (
                str(val)
                if isinstance(val, int | float)
                else "'" + str(val).replace("'", "''") + "'"
            )
            sql = f"SELECT * FROM {table} WHERE {q(item['id'])} = {lit}"
        area_recs = query_areas(ctx, sql) if "area" in item else None
        cold = timed(ctx.lake, http, sql, area_recs)
        warm: list[dict[str, Any]] = []
        if not cold["error"] and cold["s"] <= COLD_SKIP_S:
            warm = [timed(ctx.lake, http, sql, area_recs) for _ in range(WARM)]
        rec["queries"].append(
            {
                "query": item["query"],
                "sql": sql,
                "cold_ms": ms(cold["s"]),
                "warm_ms": [ms(w["s"]) for w in warm],
                "rows": cold["rows"],
                "bytes_cold": cold["bytes"],
                "gets_cold": cold["gets"],
                "heads_cold": cold["heads"],
                "bytes_warm": warm[-1]["bytes"] if warm else None,
                "gets_warm": warm[-1]["gets"] if warm else None,
                "error": cold["error"],
                **(
                    {"warm_skipped": f"cold over {COLD_SKIP_S:.0f} s"}
                    if cold["s"] > COLD_SKIP_S
                    else {}
                ),
            }
        )
    return summarise(rec)


def summarise(rec: dict[str, Any]) -> dict[str, Any]:
    for x in rec["queries"]:  # the licence guard refusing row-level reads is expected
        if "is licensed" in (x.get("error") or ""):
            x["refused"], x["error"] = x["error"][:160], ""
            x["cold_ms"] = None
    qs = [x for x in rec["queries"] if x.get("cold_ms") is not None and not x.get("error")]
    cold = [x["cold_ms"] for x in qs]
    warm = [statistics.median(x["warm_ms"]) for x in qs if x.get("warm_ms")]
    rec.update(
        {
            "cold_p50_ms": pct(cold, 50),
            "cold_p95_ms": pct(cold, 95),
            "warm_p50_ms": pct(warm, 50),
            "warm_p95_ms": pct(warm, 95),
            "bytes_cold": sum(x.get("bytes_cold") or 0 for x in qs),
            "gets_cold": sum(x.get("gets_cold") or 0 for x in qs),
            "errors": [x["query"] + ": " + x["error"] for x in rec["queries"] if x.get("error")],
            "refused": [x["query"] for x in rec["queries"] if x.get("refused")],
        }
    )
    return rec


def areas_for_probe(ctx: Any) -> dict[str, Any]:
    from tools.areas import resolve_area

    def one(name: str, level: str | None = None) -> dict[str, str]:
        d = resolve_area(ctx, names=[name], level=level)["data"]
        a = d.get("area") or {}
        iso3 = (a.get("iso3") or [None])[0]
        return {"id": a.get("area_id") or "", "iso3": iso3 or ""}

    city, region, de = one("Berlin", "city"), one("Bavaria"), one("Germany")
    countries: dict[str, dict[str, str]] = {}
    for name in sorted(set(COUNTRY_BY_PREFIX.values())):
        c = one(name)
        if c["id"]:
            countries[name] = {"country": c["id"], "country_iso3": c["iso3"], "country_iso2": ""}
    return {
        "default": {
            "city": city["id"],
            "region": region["id"],
            "country": de["id"],
            "country_iso3": "DEU",
            "country_iso2": "DE",
        },
        "countries": countries,
    }


def drawn_polygons(ctx: Any, n: int, rng: Any) -> list[str]:
    """Random drawn polygons (five to eight corners around a European point, 2-60 km across),
    stored as area records the way a drawing on the map is."""
    import math

    from data.areas import Area

    out = []
    cur = ctx.lake.cursor()
    for i in range(n):
        cx, cy = rng.uniform(-8, 26), rng.uniform(38, 58)
        r = rng.uniform(0.02, 0.5)
        k = rng.randint(5, 8)
        pts = [
            (
                cx + r * rng.uniform(0.5, 1) * math.cos(2 * math.pi * j / k),
                cy + r * rng.uniform(0.5, 1) * math.sin(2 * math.pi * j / k),
            )
            for j in range(k)
        ]
        wkt = "POLYGON((" + ", ".join(f"{x:.5f} {y:.5f}" for x, y in [*pts, pts[0]]) + "))"
        gj, x0, y0, x1, y1, km2 = cur.execute(
            "SELECT ST_AsGeoJSON(g), ST_XMin(g), ST_YMin(g), ST_XMax(g), ST_YMax(g), ST_Area_Spheroid(g) / 1e6 "
            "FROM (SELECT ST_GeomFromText(?) AS g)",
            [wkt],
        ).fetchone()
        aid = "a_" + hashlib.md5(wkt.encode()).hexdigest()[:12]  # noqa: S324 - an id
        ctx.area_store.put(
            Area(area_id=aid, name=f"drawn {i}", level="drawn", iso3=[], parents=[], geometry=json.loads(gj),
                 bbox=[x0, y0, x1, y1], area_km2=float(km2), source={"dataset": "drawn polygon (probe)", "licence": "none"})
        )  # fmt: skip
        out.append(aid)
    return out


def unseen_queries(
    ctx: Any, cols: dict[str, list[tuple[str, str]]], names: list[str], n: int
) -> list[dict[str, Any]]:
    """`n` generated queries that match no template (brief 32): random tables, random areas
    (named places, circles, drawn polygons), random filters and aggregations. Seeded, so every
    shard and every run generates the same list."""
    import random

    from tools.areas import resolve_area

    rng = random.Random(32)
    places = []
    for nm, lv in (
        ("Berlin", "city"),
        ("Bavaria", None),
        ("Germany", None),
        ("Lyon", "city"),
        ("Catalonia", None),
        ("Poland", None),
    ):
        a = (resolve_area(ctx, names=[nm], level=lv)["data"].get("area") or {}).get("area_id")
        if a:
            places.append(a)
    for lon, lat, km in ((13.4, 52.5, 30), (2.35, 48.86, 50), (11.6, 48.1, 80), (4.9, 52.37, 20)):
        a = (resolve_area(ctx, point=(lon, lat), radius_km=km)["data"].get("area") or {}).get(
            "area_id"
        )
        if a:
            places.append(a)
    places += drawn_polygons(ctx, 12, rng)
    out = []
    for i in range(n):
        t = rng.choice(names)
        c = cols[t]
        lower = {x.lower(): x for x, _ in c}
        lon = lower.get("lon") or lower.get("longitude")
        lat = lower.get("lat") or lower.get("latitude")
        geom = lower.get("geometry")
        nums = [
            x
            for x, typ in c
            if typ.upper().startswith(NUMERIC)
            and x.lower() not in ("lon", "lat", "longitude", "latitude", "x", "y")
        ]
        texts = [x for x, typ in c if typ.upper().startswith("VARCHAR")]
        where = []
        if (lon and lat) or geom:
            aid = rng.choice(places)
            where.append(
                f"in_area({q(lon)}, {q(lat)}, '{aid}')"
                if lon and lat
                else f"intersects_area({q(geom)}, '{aid}')"
            )
        kind = rng.choice(["count", "sum", "avg", "top", "group"])
        if nums and rng.random() < 0.4:
            where.append(f"{q(rng.choice(nums))} > 0")
        if texts and rng.random() < 0.3:
            where.append(f"{q(rng.choice(texts))} IS NOT NULL")
        w = (" WHERE " + " AND ".join(where)) if where else ""
        m = rng.choice(nums) if nums else None
        if kind == "sum" and m:
            sql = f"SELECT sum({q(m)}) FROM {t}{w}"
        elif kind == "avg" and m:
            sql = f"SELECT avg({q(m)}) FROM {t}{w}"
        elif kind == "top" and m:
            sql = f"SELECT * FROM {t}{w} ORDER BY {q(m)} DESC NULLS LAST LIMIT 10"
        elif kind == "group" and texts:
            g = rng.choice(texts)
            agg = f"sum({q(m)})" if m else "count(*)"
            sql = f"SELECT {q(g)}, {agg} FROM {t}{w} GROUP BY 1 ORDER BY 2 DESC NULLS LAST LIMIT 50"
        else:
            sql = f"SELECT count(*) FROM {t}{w}"
        out.append({"i": i, "table": t, "kind": kind, "sql": sql})
    return out


def run_unseen(ctx: Any, http: Http, queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from tools.sql import query_areas

    out = []
    for qd in queries:
        r = timed(ctx.lake, http, qd["sql"], query_areas(ctx, qd["sql"]) or None)
        out.append(
            {
                **qd,
                "ms": ms(r["s"]),
                "rows": r["rows"],
                "bytes": r["bytes"],
                "gets": r["gets"],
                "error": r["error"],
            }
        )
    return out


def run_extras(ctx: Any) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from app.main import app
    from tools.area_stats import area_stats
    from tools.areas import resolve_area
    from tools.quick import quick

    out: dict[str, Any] = {"routes": [], "quick": [], "resolve": [], "area_stats": []}
    with TestClient(app, raise_server_exceptions=False) as c:
        for method, path, body in ROUTES:
            times, status = [], 0
            for _ in range(1 + WARM):
                t0 = time.perf_counter()
                r = c.request(method, path, json=body)
                times.append(time.perf_counter() - t0)
                status = r.status_code
            out["routes"].append(
                {
                    "route": f"{method} {path}",
                    "status": status,
                    "cold_ms": ms(times[0]),
                    "warm_ms": [ms(x) for x in times[1:]],
                }
            )
    for tpl, area, kw in QUICK:
        times, err = [], ""
        for _ in range(1 + WARM):
            t0 = time.perf_counter()
            r = quick(ctx, tpl, area, **kw)
            times.append(time.perf_counter() - t0)
            err = (r.get("data") or {}).get("error", "") if isinstance(r.get("data"), dict) else ""
        out["quick"].append(
            {
                "template": tpl,
                "area": area,
                "cold_ms": ms(times[0]),
                "warm_ms": [ms(x) for x in times[1:]],
                "error": err,
            }
        )
    from tools import areas as areas_mod

    for name, level in RESOLVE_NAMES:
        cache = getattr(areas_mod, "_RESOLVED", None)
        t0 = time.perf_counter()
        d = resolve_area(ctx, names=[name], level=level)["data"]
        cold = time.perf_counter() - t0
        warm = []
        for _ in range(WARM):  # without the name cache: the work itself, warm
            if isinstance(cache, dict):
                cache.clear()
            t0 = time.perf_counter()
            resolve_area(ctx, names=[name], level=level)
            warm.append(time.perf_counter() - t0)
        a = d.get("area") or {}
        out["resolve"].append(
            {
                "name": name,
                "level": a.get("level"),
                "ok": bool(a.get("area_id")),
                "cold_ms": ms(cold),
                "warm_ms": [ms(x) for x in warm],
            }
        )
    import yaml

    measures: list[str] = []
    for f in ("rasters.yaml", "rasters_waves.yaml"):
        p = ROOT / "agent" / f
        if p.exists():
            measures += list(
                (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("measures", {})
            )
    region = (resolve_area(ctx, names=["Bavaria"])["data"].get("area") or {}).get("area_id")
    city = (resolve_area(ctx, names=["Berlin"], level="city")["data"].get("area") or {}).get(
        "area_id"
    )
    for m in measures:
        for label, aid in (("city", city), ("region", region)):
            if not aid:
                continue
            times, err = [], ""
            for _ in range(2):
                t0 = time.perf_counter()
                r = area_stats(ctx, aid, [m])
                times.append(time.perf_counter() - t0)
                fig = ((r.get("data") or {}).get("figures") or {}).get(m) or {}
                err = str(fig.get("error") or "")[:160]
            out["area_stats"].append(
                {
                    "measure": m,
                    "area": label,
                    "cold_ms": ms(times[0]),
                    "warm_ms": [ms(times[1])],
                    "error": err,
                }
            )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--extras", action="store_true")
    ap.add_argument("--only", default="", help="regex: the tables to probe")
    ap.add_argument("--json", default="/tmp/query-speed.json")
    ap.add_argument("--merge", default="", help="a directory of shard files: write the report")
    ap.add_argument("--unseen", type=int, default=200, help="generated queries in all (0 = none)")
    a = ap.parse_args()
    if a.merge:
        merge(Path(a.merge))
        return
    t0 = time.perf_counter()
    ctx, lake = open_backend()
    http = Http(lake)
    cols = columns(lake)
    names = sorted(t for t in cols if not a.only or re.search(a.only, t))
    mine = names[a.shard :: a.shards]
    areas = areas_for_probe(ctx)
    rec: dict[str, Any] = {
        "probed": datetime.now(UTC).isoformat(timespec="seconds"),
        "lake_mode": getattr(lake, "lake_mode", ""),
        "http_log": http.on,
        "shard": a.shard,
        "shards": a.shards,
        "tables_total": len(names),
        "tables": [],
    }
    out = Path(a.json)
    for i, t in enumerate(mine, 1):
        r = probe_table(ctx, http, t, cols[t], areas)
        rec["tables"].append(r)
        print(
            f"{i}/{len(mine)} {t}: cold p50 {r['cold_p50_ms']} ms, warm p50 {r['warm_p50_ms']} ms",
            flush=True,
        )
        out.write_text(json.dumps(rec), encoding="utf-8")  # partial results survive a timeout
    if a.unseen:
        allq = unseen_queries(ctx, cols, names, a.unseen)
        rec["unseen"] = run_unseen(ctx, http, allq[a.shard :: a.shards])
        done = [x["ms"] for x in rec["unseen"] if not x["error"]]
        print(
            f"unseen: {len(done)} of {len(rec['unseen'])} answered, p50 {pct(done, 50)} ms, p95 {pct(done, 95)} ms",
            flush=True,
        )
        out.write_text(json.dumps(rec), encoding="utf-8")
    if a.extras:
        rec["extras"] = run_extras(ctx)
    rec["seconds"] = round(time.perf_counter() - t0)
    out.write_text(json.dumps(rec), encoding="utf-8")


def fmt(v: float | None) -> str:
    return "–" if v is None else (f"{v:,.0f}" if v >= 100 else f"{v:,.1f}")


def mb(b: int | None) -> str:
    return "–" if b is None else f"{b / 1e6:,.2f}"


def merge(d: Path) -> None:
    """Shard files -> `data/query_speed.json` and `docs/research/query-speed.md` (the
    measured section, between markers; the rest of the document is kept)."""
    shards = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.rglob("*.json"))]
    tables = sorted((t for s in shards for t in s.get("tables", [])), key=lambda t: t["table"])
    extras = next((s["extras"] for s in shards if s.get("extras")), {})
    head = shards[0] if shards else {}
    data = {
        "probed": head.get("probed"),
        "lake_mode": head.get("lake_mode"),
        "tables": {
            t["table"]: {
                k: t[k]
                for k in (
                    "cold_p50_ms",
                    "cold_p95_ms",
                    "warm_p50_ms",
                    "warm_p95_ms",
                    "bytes_cold",
                    "gets_cold",
                )
            }
            for t in tables
        },
        "routes": {
            r["route"]: {"warm_p95_ms": pct(r["warm_ms"], 95)} for r in extras.get("routes", [])
        },
        "quick": {
            f"{r['template']}:{r['area']}": {"warm_p95_ms": pct(r["warm_ms"], 95)}
            for r in extras.get("quick", [])
        },
        "resolve": {
            r["name"]: {"warm_p95_ms": pct(r["warm_ms"], 95)} for r in extras.get("resolve", [])
        },
    }
    (ROOT / "data" / "query_speed.json").write_text(
        json.dumps(data, indent=1) + "\n", encoding="utf-8"
    )

    def stat(xs: list[float]) -> str:
        return f"{fmt(pct(xs, 50))} / {fmt(pct(xs, 95))}"

    lines = [
        f"Probed {head.get('probed')} in the Lambda-sized container (2 vCPU, 3,008 MB) against "
        f"`{head.get('lake_mode')}`; {len(tables)} tables in {len(shards)} shards. Times in ms "
        f"(cold = the first run of each query in the process; warm = the median of {WARM} repeats); "
        "MB and GET requests read from R2 by the cold runs of the table's query set.",
        "",
    ]
    cold_all = [
        x["cold_ms"]
        for t in tables
        for x in t["queries"]
        if x.get("cold_ms") is not None and not x.get("error")
    ]
    warm_all = [
        statistics.median(x["warm_ms"])
        for t in tables
        for x in t["queries"]
        if x.get("warm_ms") and not x.get("error")
    ]
    unseen = [x for s in shards for x in s.get("unseen", [])]
    ok = [x["ms"] for x in unseen if not x.get("error")]
    data["unseen"] = {
        "queries": len(unseen),
        "answered": len(ok),
        "p50_ms": pct(ok, 50),
        "p95_ms": pct(ok, 95),
    }
    (ROOT / "data" / "query_speed.json").write_text(
        json.dumps(data, indent=1) + "\n", encoding="utf-8"
    )
    lines += [
        f"### Unseen queries (generated, no template, result cache off): {len(ok)} of {len(unseen)} answered, "
        f"p50 {fmt(pct(ok, 50))} ms, p95 {fmt(pct(ok, 95))} ms, max {fmt(max(ok) if ok else None)} ms",
        "",
        "| # | table | kind | ms | rows | MB | error |",
        "|---:|---|---|---:|---:|---:|---|",
    ]
    lines += [
        f"| {x['i']} | `{x['table']}` | {x['kind']} | {fmt(x.get('ms'))} | {x.get('rows')} | {mb(x.get('bytes'))} | {(x.get('error') or '')[:80].replace('|', '/')} |"
        for x in sorted(unseen, key=lambda x: x["i"])
    ]
    lines.append("")
    lines += [
        "### All dataset queries",
        "",
        "| | queries | p50 | p95 | max |",
        "|---|---:|---:|---:|---:|",
        f"| cold | {len(cold_all)} | {fmt(pct(cold_all, 50))} | {fmt(pct(cold_all, 95))} | {fmt(max(cold_all) if cold_all else None)} |",
        f"| warm | {len(warm_all)} | {fmt(pct(warm_all, 50))} | {fmt(pct(warm_all, 95))} | {fmt(max(warm_all) if warm_all else None)} |",
        "",
    ]
    for key, title in (
        ("routes", "Data routes"),
        ("quick", "quick templates"),
        ("resolve", "resolve_area"),
        ("area_stats", "area_stats"),
    ):
        rows = extras.get(key, [])
        if not rows:
            continue
        cold = [r["cold_ms"] for r in rows if r.get("cold_ms") is not None]
        warm = [x for r in rows for x in r.get("warm_ms", []) if x is not None]
        lines += [
            f"### {title}: cold p50/p95 {stat(cold)}, warm p50/p95 {stat(warm)}",
            "",
            "| | cold | warm p50 | note |",
            "|---|---:|---:|---|",
        ]
        for r in rows:
            label = r.get("route") or (
                f"{r.get('template')} {r.get('area')}"
                if key == "quick"
                else r.get("name") or f"{r.get('measure')} ({r.get('area')})"
            )
            note = (
                r.get("error")
                or (f"status {r['status']}" if key == "routes" else "")
                or ("" if r.get("ok", True) else "not resolved")
            )
            lines.append(
                f"| {label} | {fmt(r.get('cold_ms'))} | {fmt(pct(r.get('warm_ms', []), 50))} | {note} |"
            )
        lines.append("")
    slow = sorted(tables, key=lambda t: -(t.get("cold_p95_ms") or 0))
    lines += [
        "### Every table (slowest cold p95 first)",
        "",
        "| table | cold p50 | cold p95 | warm p50 | warm p95 | MB cold | GETs | notes |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for t in slow:
        notes = "; ".join(t.get("errors", []))[:160].replace("|", "/")
        lines.append(
            f"| `{t['table']}` | {fmt(t.get('cold_p50_ms'))} | {fmt(t.get('cold_p95_ms'))} | {fmt(t.get('warm_p50_ms'))} | "
            f"{fmt(t.get('warm_p95_ms'))} | {mb(t.get('bytes_cold'))} | {t.get('gets_cold') or 0} | {notes} |"
        )
    doc = ROOT / "docs" / "research" / "query-speed.md"
    start, end = "<!-- measured:start -->", "<!-- measured:end -->"
    text = doc.read_text(encoding="utf-8") if doc.exists() else f"# Query speed\n\n{start}\n{end}\n"
    body = "\n".join(lines)
    text = re.sub(
        re.escape(start) + r".*?" + re.escape(end),
        lambda _: f"{start}\n{body}\n{end}",
        text,
        flags=re.S,
    )
    doc.write_text(text, encoding="utf-8")
    print(f"{len(tables)} tables merged into {doc} and data/query_speed.json")


if __name__ == "__main__":
    main()
