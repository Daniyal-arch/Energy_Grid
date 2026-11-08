# ruff: noqa: E501 - the SQL reads best on one line each
"""Six more agent tools (brief 30 Track 4.6): nearest, along, compare_areas, trend, export and
explain_coverage. Each runs its queries through run_sql (the guard, the lockdown, the sources)
and names how a computed figure is computed.
"""

from __future__ import annotations

import csv
import io
import json
import re
import secrets
from typing import Any, Literal

from pydantic import BaseModel, Field

from tools.context import ToolContext, result
from tools.quick import ISO3_TO_ISO2, QuickError, _area, _coverage, _region, profile
from tools.sql import run_sql

# point datasets the tools take by name: the app tables with lon/lat
POINTS = {
    "plants_eu": ("app.eu_plants", "name, country, fuel, mw, year"),
    "plants_us": ("app.us_plants", "name, state, type, status, mw, year"),
    "plants_world": ("app.world_plants", "name, type, mw, year"),
    "substations": ("app.eu_substations", "kv, country"),
    "data_centres": ("app.data_centres", "name, code"),
}
Dataset = Literal["plants_eu", "plants_us", "plants_world", "substations", "data_centres"]
DIST = "great-circle distance on a sphere of radius 6,371 km (haversine), computed"


def _rows(ctx: ToolContext, sql: str) -> dict[str, Any]:
    r = run_sql(ctx, sql)
    if "error" in r["data"]:
        raise QuickError(r["data"]["error"])
    return r


# ---------------------------------------------------------------------- nearest
class NearestArgs(BaseModel):
    dataset: Dataset
    lon: float | None = Field(default=None, ge=-180, le=180)
    lat: float | None = Field(default=None, ge=-90, le=90)
    area: str | None = Field(default=None, description="instead of a point: the area's centre")
    k: int = Field(default=10, ge=1, le=100)


def nearest(ctx: ToolContext, dataset: str, lon: float | None = None, lat: float | None = None,
            area: str | None = None, k: int = 10) -> dict[str, Any]:  # fmt: skip
    try:
        how = "the point given"
        if lon is None or lat is None:
            if not area:
                raise QuickError("give lon and lat, or an area")
            a = _area(ctx, area)
            b = a["bbox"]
            lon, lat = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            how = f"the middle of {a['name']}'s bounding box"
        table, cols = POINTS[dataset]
        sql = (f"SELECT {cols}, lon, lat, round(6371 * 2 * asin(sqrt(pow(sin(radians(lat - {lat}) / 2), 2) + "
               f"cos(radians({lat})) * cos(radians(lat)) * pow(sin(radians(lon - {lon}) / 2), 2))), 2) AS km "
               f"FROM {table} WHERE lon IS NOT NULL ORDER BY km LIMIT {k}")  # fmt: skip
        r = _rows(ctx, sql)
    except (QuickError, KeyError) as e:
        return result({"error": str(e)}, [])
    data = {**r["data"], "from": [round(lon, 5), round(lat, 5)], "from_how": how, "km_how": DIST}
    return result(data, r["sources"], r.get("result_id"))


# ---------------------------------------------------------------------- along
class AlongArgs(BaseModel):
    dataset: Dataset
    line: list[list[float]] = Field(
        min_length=2, max_length=500, description="[[lon, lat], ...] of the route"
    )
    buffer_km: float = Field(gt=0, le=200)
    name: str = Field(default="route", max_length=80)


def along(
    ctx: ToolContext, dataset: str, line: list[list[float]], buffer_km: float, name: str = "route"
) -> dict[str, Any]:
    try:
        A = ctx.areas
        gj = json.dumps(
            {"type": "LineString", "coordinates": [[float(x), float(y)] for x, y in line]}
        )
        corridor = A.make(
            A.buffer(gj, buffer_km), name=f"{buffer_km:g} km either side of {name}", level="polygon",
            iso3=[], parents=[], source={"dataset": "a route given in the question", "licence": "none"},
            how=f"the line grown by {buffer_km:g} km (azimuthal equidistant projection centred on the line)",
        )  # fmt: skip
        ctx.turn_areas.append(corridor.area_id)
        table, cols = POINTS[dataset]
        r = _rows(
            ctx,
            f"SELECT {cols}, lon, lat FROM {table} WHERE in_area(lon, lat, '{corridor.area_id}')",
        )
    except (QuickError, KeyError, ValueError) as e:
        return result({"error": str(e)}, [])
    data = {**r["data"], "corridor": corridor.summary()}
    return result(data, r["sources"], r.get("result_id"))


# ---------------------------------------------------------------------- compare_areas
class CompareArgs(BaseModel):
    areas: list[str] = Field(min_length=2, max_length=6)
    measures: list[Literal["plants", "substations", "lines", "data_centres"]] = Field(
        default_factory=lambda: ["plants", "substations", "lines", "data_centres"]
    )


def compare_areas(
    ctx: ToolContext, areas: list[str], measures: list[str] | None = None
) -> dict[str, Any]:
    want = set(measures or ["plants", "substations", "lines", "data_centres"])
    words = {"plants": ("plants", "generators"), "substations": ("substations",),
             "lines": ("line length",), "data_centres": ("data centres",)}  # fmt: skip
    out, sources = [], []
    try:
        for name in areas:
            a = _area(ctx, name)
            for t in profile(ctx, a):
                if any(w in t["title"].lower() for m in want for w in words[m]):
                    sources += [s for s in t.pop("sources") if s not in sources]
                    out.append({"area": a["name"], "area_id": a["area_id"], **t})
    except QuickError as e:
        return result({"error": str(e)}, [])
    return result(
        {
            "tables": out,
            "note": "the same queries for every area; a whole country or group is filtered by its country codes, smaller areas by their outline",
        },
        sources,
    )


# ---------------------------------------------------------------------- trend
class TrendArgs(BaseModel):
    area: str
    measure: Literal["capacity_by_year"] = "capacity_by_year"
    years: list[int] = Field(default_factory=list, max_length=60, description="empty: every year")


def trend(
    ctx: ToolContext, area: str, measure: str = "capacity_by_year", years: list[int] | None = None
) -> dict[str, Any]:
    """Capacity of today's plants by the year they started, per fuel: the plants' own
    commissioning years (a history of the present fleet; plants retired since are not in it)."""
    try:
        a = _area(ctx, area)
        reg = _region(a)
        yr = f" AND year IN ({', '.join(str(int(y)) for y in years)})" if years else ""
        if reg == "eu":
            from tools.quick import _where

            sql = f"SELECT year, fuel, count(*) AS plants, round(sum(mw), 1) AS mw FROM app.eu_plants WHERE {_where(a)} AND year IS NOT NULL{yr} GROUP BY year, fuel ORDER BY year, fuel"
        elif reg == "us":
            cond = "true" if a["level"] == "country" else f"in_area(lon, lat, '{a['area_id']}')"
            sql = f"SELECT year, type, count(*) AS plants, round(sum(mw), 1) AS mw FROM app.us_plants WHERE status = 'operating' AND {cond} AND year IS NOT NULL{yr} GROUP BY year, type ORDER BY year, type"
        else:
            sql = f"SELECT year, type, count(*) AS plants, round(sum(mw), 1) AS mw FROM app.world_plants WHERE in_area(lon, lat, '{a['area_id']}') AND year IS NOT NULL{yr} GROUP BY year, type ORDER BY year, type"
        r = _rows(ctx, sql)
    except QuickError as e:
        return result({"error": str(e)}, [])
    method = ("MW of today's plants summed by their commissioning year: plants retired since are "
              "not counted, so this is the age profile of the present fleet, not installed capacity per year")  # fmt: skip
    return result(
        {**r["data"], "area": a["name"], "method": method}, r["sources"], r.get("result_id")
    )


# ---------------------------------------------------------------------- export
REFUSE = re.compile(
    r"non[- ]?commercial|all rights reserved|no redistribution|not (?:be )?redistribut|nc-|by-nc",
    re.I,
)
SHARE_ALIKE = re.compile(r"odbl|share[- ]?alike|by-sa", re.I)


class ExportArgs(BaseModel):
    result_id: str = Field(pattern=r"^r_[0-9a-f]{6,32}$")
    format: Literal["csv", "geojson", "parquet"] = "csv"


def export(ctx: ToolContext, result_id: str, format: str = "csv") -> dict[str, Any]:
    rec = ctx.results.get(result_id)
    if rec is None:
        return result({"error": f"no result {result_id}"}, [])
    srcs = rec.get("sources") or []
    lic = "; ".join(sorted({s.get("licence", "") for s in srcs if s.get("licence")}))
    if REFUSE.search(lic):
        return result(
            {"error": f"not exported: a source's licence does not allow redistribution ({lic})"}, []
        )
    cols, rows = rec["columns"], rec["rows"]
    terms = ["Sources: " + "; ".join(f"{s.get('dataset')} ({s.get('licence')})" for s in srcs)]
    if SHARE_ALIKE.search(lic):
        terms.append("Share-alike: this extract is a database derived from ODbL or CC BY-SA data; "
                     "if you publish an adapted version, publish it under the same licence.")  # fmt: skip
    name = f"x_{secrets.token_hex(6)}.{format}"
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        w.writerows(rows)
        body: Any = buf.getvalue()
    elif format == "geojson":
        if not {"lon", "lat"} <= set(cols):
            return result({"error": "geojson needs lon and lat columns"}, [])
        i, j = cols.index("lon"), cols.index("lat")
        body = json.dumps({
            "type": "FeatureCollection", "sources": srcs, "terms": terms,
            "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [r[i], r[j]]},
                          "properties": dict(zip(cols, r, strict=False))} for r in rows if r[i] is not None],
        }, default=str)  # fmt: skip
    else:
        import duckdb

        tmp = ctx.settings.results_dir / name
        con = duckdb.connect()
        con.execute(
            "CREATE TABLE x AS SELECT * FROM read_json_auto(?)", [str(_json_rows(ctx, cols, rows))]
        )
        meta = json.dumps({"sources": srcs, "terms": terms}).replace("'", "''")
        con.execute(f"COPY x TO '{tmp}' (FORMAT parquet, KV_METADATA {{atlas: '{meta}'}})")
        body = None
    if body is not None:
        (ctx.settings.results_dir / name).write_text(body, encoding="utf-8")
    return result(
        {
            "file": name,
            "url": f"/api/exports/{name}",
            "rows": len(rows),
            "licence": lic,
            "terms": terms,
        },
        srcs,
    )


def _json_rows(ctx: ToolContext, cols: list[str], rows: list[list[Any]]) -> Any:
    p = ctx.settings.results_dir / f"rows_{secrets.token_hex(4)}.json"
    p.write_text(
        json.dumps([dict(zip(cols, r, strict=False)) for r in rows], default=str), encoding="utf-8"
    )
    return p


# ---------------------------------------------------------------------- explain_coverage
class CoverageArgs(BaseModel):
    area: str
    family: str = Field(default="", description="a coverage family id or name; empty: all")


def coverage_cells(ctx: ToolContext, iso3: list[str], family: str = "") -> list[dict[str, Any]]:
    """The registry's cells for these countries and a family id or name (all when empty)."""
    cov = _coverage(str(ctx.settings.atlas_root))
    if not cov:
        return []
    fams = {f["id"]: f for f in cov["families"]}
    f0 = family.lower()
    want = [
        k
        for k, f in fams.items()
        if not f0 or f0 in (k, f["name"].lower()) or f0 in f["name"].lower()
    ]
    cells = []
    for i3 in iso3:
        cc = "US" if i3 == "USA" else "GB" if i3 == "GBR" else ISO3_TO_ISO2.get(i3, "")
        for k in want:
            c = (cov["countries"].get(cc) or {}).get(k)
            if c:
                cells.append({"country": cc, "family": fams[k]["name"], "shows": fams[k].get("shows"),
                              **{x: c.get(x) for x in ("status", "source", "note", "url", "dataset", "licence", "checked")}})  # fmt: skip
    return cells


def explain_coverage(ctx: ToolContext, area: str, family: str = "") -> dict[str, Any]:
    cov = _coverage(str(ctx.settings.atlas_root))
    if not cov:
        return result({"error": "the coverage registry is not in this service"}, [])
    try:
        a = _area(ctx, area)
    except QuickError as e:
        return result({"error": str(e)}, [])
    cells = coverage_cells(ctx, a.get("iso3") or [], family)
    src = [
        {
            "dataset": "coverage registry",
            "table": "data/coverage.yaml",
            "licence": "facts",
            "retrieved": cov.get("checked", ""),
        }
    ]
    return result(
        {
            "area": a["name"],
            "cells": cells,
            "how": "one cell per family and country; a dark cell names its reason and the evidence",
        },
        src,
    )
