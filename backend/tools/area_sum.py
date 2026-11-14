# ruff: noqa: E501 - the SQL reads best on one line each
"""Exact sums inside any area from H3 rollups plus boundary rows (brief 32).

For a lake table with rollups (`rollups.<dataset>__<table>_r<res>`, scripts/build_rollups.py):

1. cover the area with H3 cells at the resolution its size calls for (5, 6 or 7);
2. **interior**: the cells wholly inside it (H3 "full" containment, and the cell's outline, with a
   margin of about 1 m, contained in the area's outline): every row in such a cell is inside the
   area, so the cell's stored count and sums are taken as they are;
3. **boundary**: every other cell that touches the area (H3 "overlap" cells and their neighbours,
   so no row inside the area is missed): only these cells' detail rows are read, each tested
   exactly with the same point-in-outline rule as `in_area`.

The interior's rollup rows plus the boundary's exact rows equal the full row-level sum (tests:
`tests/test_area_sum.py`, many areas, resolutions, filters and groupings). Rows are placed as the
rollups place them: `lon`/`lat`, or the centroid of the geometry. A rollup alone (cells whose
centre lies inside) is a different, labelled rule and is not used here.

When no rollup holds the measures, groupings or filters asked for, the sum is read from the rows
alone (the same exact rule) and the answer says so.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from tools.context import ToolContext, result

# the H3 resolution for an area of this many km² (cells of about 253, 36 and 5 km²)
RES_BY_KM2 = ((50_000.0, 5), (2_000.0, 6), (0.0, 7))
MARGIN_DEG = 1e-5  # about 1 m: a cell counts as interior only with this margin to the outline


class AreaSumError(ValueError):
    pass


class AreaSumArgs(BaseModel):
    table: str = Field(
        max_length=200, description="a lake table, dataset.table (e.g. mastr.units_solar)"
    )
    area_id: str = Field(pattern=r"^a_[0-9a-f]{12}$", description="from resolve_area")
    measures: list[str] = Field(
        default_factory=list, max_length=6, description="numeric columns to sum (empty: count only)"
    )
    by: list[str] = Field(default_factory=list, max_length=3, description="columns to group by")
    where: dict[str, str | int | float] = Field(
        default_factory=dict, description="column = value filters"
    )


def _q(c: str) -> str:
    return '"' + c.replace('"', '""') + '"'


def _lit(v: Any) -> str:
    if isinstance(v, int | float):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def _columns(cur: Any, table: str) -> dict[str, str]:
    try:
        return {r[0]: str(r[1]) for r in cur.execute(f"DESCRIBE {table}").fetchall()}
    except Exception:  # noqa: BLE001 - a missing table is answered by the caller
        return {}


def _position(cols: dict[str, str]) -> tuple[str, str]:
    low = {c.lower(): c for c in cols}
    if "lon" in low and "lat" in low:
        return _q(low["lon"]), _q(low["lat"])
    if "geometry" in low:
        g = _q(low["geometry"])
        if "GEOMETRY" not in cols[low["geometry"]].upper():
            g = f"ST_GeomFromWKB({g})"
        return f"ST_X(ST_Centroid({g}))", f"ST_Y(ST_Centroid({g}))"
    raise AreaSumError("the table has no position (lon/lat or geometry)")


def resolution_for(km2: float) -> int:
    return next(r for k, r in RES_BY_KM2 if km2 >= k)


DETAILED_VERTICES = 5_000  # above this, H3's polygon fill is slow (8 s at 200,000 vertices)


def _rings(geometry: dict[str, Any]) -> list[list[list[float]]]:
    t, c = geometry.get("type"), geometry.get("coordinates") or []
    if t == "Polygon":
        return list(c)
    if t == "MultiPolygon":
        return [r for poly in c for r in poly]
    if t == "GeometryCollection":
        return [r for g in geometry.get("geometries", []) for r in _rings(g)]
    return []


def cells(cur: Any, geometry: dict[str, Any], res: int) -> tuple[list[int], list[int]]:
    """(interior, boundary) H3 cells of an outline at `res`: every interior cell lies inside the
    outline with MARGIN_DEG to spare; every cell the outline touches and is not interior is a
    boundary cell (a superset is allowed: boundary rows are tested exactly)."""
    rings = _rings(geometry)
    if sum(len(r) for r in rings) > DETAILED_VERTICES:
        return _cells_detailed(cur, geometry, rings, res)
    gj = json.dumps(geometry)
    polys = [
        r[0]
        for r in cur.execute(
            "SELECT ST_AsText(unnest(ST_Dump(ST_GeomFromGeoJSON(?))).geom)", [gj]
        ).fetchall()
    ]
    full: set[int] = set()
    touched: set[int] = set()
    for wkt in polys:
        full |= set(
            cur.execute(
                "SELECT h3_polygon_wkt_to_cells_experimental(?, 'full', ?)", [wkt, res]
            ).fetchone()[0]
            or []
        )
        touched |= set(
            cur.execute(
                "SELECT h3_polygon_wkt_to_cells_experimental(?, 'overlap', ?)", [wkt, res]
            ).fetchone()[0]
            or []
        )
    interior: list[int] = []
    if full:
        interior = [
            r[0]
            for r in cur.execute(
                "SELECT c FROM (SELECT unnest(?::UBIGINT[]) AS c) "
                "WHERE ST_Contains(ST_GeomFromGeoJSON(?), "
                "ST_Buffer(ST_GeomFromText(h3_cell_to_boundary_wkt(c)), ?))",
                [sorted(full), gj, MARGIN_DEG],
            ).fetchall()
        ]
    ring: set[int] = set()
    if touched:
        ring = {
            r[0]
            for r in cur.execute(
                "SELECT DISTINCT unnest(h3_grid_disk(c, 1)) FROM (SELECT unnest(?::UBIGINT[]) AS c)",
                [sorted(touched)],
            ).fetchall()
        }
    inner = set(interior)
    return sorted(inner), sorted((ring | touched) - inner)


def _cells_detailed(
    cur: Any, geometry: dict[str, Any], rings: list[list[list[float]]], res: int
) -> tuple[list[int], list[int]]:
    """`cells` for detailed outlines without filling the full outline with H3.

    1. Boundary: the cells of points along every ring, no farther apart than 0.4 of the
       resolution's shortest cell edge, and their neighbours: every cell the outline crosses
       is among them (a crossing cell lies within one cell of a sampled point).
    2. Candidates: H3 cells whose centres lie in the outline simplified by `tol` and buffered by
       2 `tol`, a superset of the outline (Douglas-Peucker moves no point by more than `tol`).
    3. The candidates off the boundary fall into connected groups that the outline does not
       cross, so each group is wholly inside or wholly outside: one exact point test a group.
       A cell off the boundary is at least a cell away from the outline: margin satisfied.
    """
    edge_km = cur.execute(
        "SELECT min(h3_edge_length(e, 'km')) FROM (SELECT unnest(h3_origin_to_directed_edges("
        "c)) AS e FROM (SELECT unnest(h3_get_pentagons(?)) AS c))",
        [res],
    ).fetchone()[0]
    step = float(edge_km) * 0.4 / 111.32  # degrees; a degree of longitude is never longer
    xs: list[float] = []
    ys: list[float] = []
    for ring in rings:
        for (x0, y0), (x1, y1) in zip(ring, ring[1:], strict=False):
            n = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) / step) + 1)
            for k in range(n):
                xs.append(x0 + (x1 - x0) * k / n)
                ys.append(y0 + (y1 - y0) * k / n)
        if ring:
            xs.append(ring[-1][0])
            ys.append(ring[-1][1])
    boundary = {
        r[0]
        for r in cur.execute(
            "SELECT DISTINCT unnest(h3_grid_disk(c, 1)) FROM (SELECT DISTINCT "
            "h3_latlng_to_cell(greatest(-90.0, least(90.0, y)), x, ?) AS c "
            "FROM (SELECT unnest(?::DOUBLE[]) AS x, unnest(?::DOUBLE[]) AS y))",
            [res, xs, ys],
        ).fetchall()
    }
    tol = step * 2
    gj = json.dumps(geometry)
    polys = [
        r[0]
        for r in cur.execute(
            "SELECT ST_AsText(unnest(ST_Dump(ST_Buffer(ST_SimplifyPreserveTopology("
            "ST_MakeValid(ST_GeomFromGeoJSON(?)), ?), ?))).geom)",
            [gj, tol, 2 * tol],
        ).fetchall()
    ]
    cand: set[int] = set()
    for wkt in polys:
        cand |= set(
            cur.execute(
                "SELECT h3_polygon_wkt_to_cells_experimental(?, 'center', ?)", [wkt, res]
            ).fetchone()[0]
            or []
        )
    rest = sorted(cand - boundary)
    if not rest:
        return [], sorted(boundary)
    adj: dict[int, list[int]] = {
        c: list(n or [])
        for c, n in cur.execute(
            "SELECT c, h3_grid_ring(c, 1) FROM (SELECT unnest(?::UBIGINT[]) AS c)", [rest]
        ).fetchall()
    }
    todo = set(rest)
    groups: list[list[int]] = []
    while todo:
        start = todo.pop()
        group, stack = [start], [start]
        while stack:
            for n in adj.get(stack.pop(), []):
                if n in todo:
                    todo.remove(n)
                    group.append(n)
                    stack.append(n)
        groups.append(group)
    reps = [g[0] for g in groups]
    inside = [
        bool(r[0])
        for r in cur.execute(
            "SELECT ST_Contains(g, ST_Point(h3_cell_to_lng(c), h3_cell_to_lat(c))) FROM "
            "(SELECT unnest(?::UBIGINT[]) AS c, generate_subscripts(?::UBIGINT[], 1) AS i), "
            "(SELECT ST_GeomFromGeoJSON(?) AS g) ORDER BY i",
            [reps, reps, gj],
        ).fetchall()
    ]
    interior = sorted(c for g, ok in zip(groups, inside, strict=True) if ok for c in g)
    return interior, sorted(boundary)


def area_sum(
    ctx: ToolContext,
    table: str,
    area_id: str,
    measures: list[str] | None = None,
    by: list[str] | None = None,
    where: dict[str, Any] | None = None,
    res: int | None = None,
) -> dict[str, Any]:
    area = ctx.area_store.get(area_id)
    if area is None:
        return result({"error": f"unknown area {area_id}; resolve_area first"}, [])
    try:
        data = exact_sum(ctx, table, area.as_dict(), measures or [], by or [], where or {}, res)
    except AreaSumError as e:
        return result({"error": str(e)}, [])
    src = ctx.lake.source_for(table).as_dict()
    sources = [src]
    if data.get("rollup"):
        sources.append({**src, "table": data["rollup"]})
    return result(data, sources)


def exact_sum(
    ctx: ToolContext,
    table: str,
    area: dict[str, Any],
    measures: list[str],
    by: list[str],
    where: dict[str, Any],
    res: int | None = None,
) -> dict[str, Any]:
    """Count and sums of `measures` inside the area, grouped by `by`, filtered by `where`
    (column = value), exact (see the module docstring)."""
    cur = ctx.lake.cursor()
    cols = _columns(cur, table)
    if not cols:
        raise AreaSumError(f"no table {table}")
    lon, lat = _position(cols)
    for c in [*measures, *by, *where]:
        if c not in cols:
            raise AreaSumError(f"{table} has no column {c}")
    res = res or resolution_for(float(area.get("area_km2") or 0))
    rollup = f"rollups.{table.replace('.', '__')}_r{res}"
    rcols = _columns(cur, rollup)
    usable = (
        bool(rcols)
        and all(f"{m}_sum" in rcols for m in measures)
        and all(c in rcols for c in [*by, *where])
    )
    gj = json.dumps(area["geometry"])
    x0, y0, x1, y1 = area["bbox"]
    keys = "".join(f", {_q(b)}" for b in by)
    filt = "".join(f" AND {_q(k)} = {_lit(v)}" for k, v in where.items())
    detail_sums = "".join(f", sum({_q(m)}) AS {_q(m + '_sum')}" for m in measures)
    inside = (
        f"{lon} BETWEEN -180 AND 180 AND {lat} BETWEEN -90 AND 90 "
        f"AND {lon} BETWEEN {x0!r} AND {x1!r} AND {lat} BETWEEN {y0!r} AND {y1!r} "
        f"AND ST_Contains((SELECT g FROM _area), ST_Point({lon}, {lat}))"
    )
    head = f"WITH _area AS (SELECT ST_GeomFromGeoJSON({_lit(gj)}) AS g) "
    if not usable:
        sql = (
            head + f"SELECT 1 AS _k{keys}, count(*) AS n{detail_sums} FROM {table} "
            f"WHERE {inside}{filt} GROUP BY ALL"
        )
        rows = cur.execute(sql).fetchall()
        names = [d[0] for d in cur.description]
        return {
            "table": table,
            "area": {k: area.get(k) for k in ("area_id", "name", "level")},
            "method": "the rows inside the area (exact point-in-outline test on every row; no rollup holds these measures, groupings or filters)",
            "rows": [dict(zip(names[1:], r[1:], strict=True)) for r in rows],
        }
    interior, boundary = cells(cur, area["geometry"], res)
    roll_sums = "".join(f", sum({_q(m + '_sum')}) AS {_q(m + '_sum')}" for m in measures)
    outer_sums = "".join(f", sum({_q(m + '_sum')}) AS {_q(m + '_sum')}" for m in measures)
    parts = []
    if interior:
        parts.append(
            f"SELECT 1 AS _k{keys}, sum(n) AS n{roll_sums} FROM {rollup} "
            f"WHERE h3 IN (SELECT unnest([{', '.join(str(c) for c in interior)}]::UBIGINT[])){filt} GROUP BY ALL"
        )
    if boundary:
        parts.append(
            f"SELECT 1 AS _k{keys}, count(*) AS n{detail_sums} FROM {table} WHERE {inside} "
            f"AND h3_latlng_to_cell({lat}, {lon}, {res}) IN "
            f"(SELECT unnest([{', '.join(str(c) for c in boundary)}]::UBIGINT[])){filt} GROUP BY ALL"
        )
    if not parts:
        return {
            "table": table,
            "area": {k: area.get(k) for k in ("area_id", "name", "level")},
            "rows": [],
            "method": "no H3 cell touches the area",
        }
    sql = (
        head
        + f"SELECT 1 AS _k{keys}, sum(n)::BIGINT AS n{outer_sums} FROM ("
        + " UNION ALL BY NAME ".join(parts)
        + ") GROUP BY ALL"
    )
    rows = cur.execute(sql).fetchall()
    names = [d[0] for d in cur.description]
    return {
        "table": table,
        "area": {k: area.get(k) for k in ("area_id", "name", "level")},
        "method": (
            f"exact: the stored H3 rollup (resolution {res}) of the {len(interior)} cells wholly "
            f"inside the area, plus the rows of the {len(boundary)} cells on its edge, each "
            "tested against the outline"
        ),
        "rollup": rollup,
        "res": res,
        "interior_cells": len(interior),
        "boundary_cells": len(boundary),
        "rows": [dict(zip(names[1:], r[1:], strict=True)) for r in rows],
    }
