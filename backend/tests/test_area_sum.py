"""Brief 32: interior-plus-boundary sums equal full row-level sums, on many areas (boxes,
concave shapes, holes, several parts, circles, slivers, areas smaller than a cell or partly off
the data), every rollup resolution, with and without groupings and filters, for a point table
and a polygon table (placed by centroid). The fixture values are multiples of 1/8, so the double
sums are exact in any order and are compared with ==."""

from __future__ import annotations

import hashlib
import json

import pytest

from data.areas import Area
from tests.conftest import HAVE_H3, settings
from tools import area_sum as area_sum_mod
from tools.area_sum import area_sum, exact_sum
from tools.context import ToolContext

pytestmark = pytest.mark.skipif(not HAVE_H3, reason="the DuckDB h3 extension is not installed")

WKT = {
    "city_box": "POLYGON((9.9 52.3, 10.3 52.3, 10.3 52.55, 9.9 52.55, 9.9 52.3))",
    "region_box": "POLYGON((8 48, 11 48, 11 50.5, 8 50.5, 8 48))",
    "country_box": "POLYGON((5.5 47.5, 14.5 47.5, 14.5 54.5, 5.5 54.5, 5.5 47.5))",
    "l_shape": "POLYGON((6 48, 9 48, 9 49, 7 49, 7 51, 6 51, 6 48))",
    "triangle": "POLYGON((10 49, 13 49.2, 11.2 52, 10 49))",
    "star": "POLYGON((11 50, 11.4 51, 12.5 51.1, 11.6 51.7, 12 52.8, 11 52.1, 10 52.8, 10.4 51.7, 9.5 51.1, 10.6 51, 11 50))",
    "with_hole": "POLYGON((7 50, 10 50, 10 53, 7 53, 7 50), (8 51, 9 51, 9 52, 8 52, 8 51))",
    "two_parts": "MULTIPOLYGON(((6 47.2, 7 47.2, 7 48, 6 48, 6 47.2)), ((13 53, 14.6 53, 14.6 54.8, 13 54.8, 13 53)))",
    "sliver": "POLYGON((5.2 50, 14.8 50.02, 14.8 50.05, 5.2 50.03, 5.2 50))",
    "tiny": "POLYGON((10.001 50.001, 10.004 50.001, 10.004 50.003, 10.001 50.003, 10.001 50.001))",
    "off_edge": "POLYGON((14 46, 16 46, 16 48, 14 48, 14 46))",
    "diamond": "POLYGON((12 47.5, 13.5 49, 12 50.5, 10.5 49, 12 47.5))",
}
CIRCLES = {
    "circle_small": (9.0, 51.0, 0.05),
    "circle_mid": (12.0, 49.0, 0.4),
    "circle_big": (10.0, 51.0, 1.6),
}


def aid(name: str) -> str:
    return "a_" + hashlib.md5(name.encode()).hexdigest()[:12]  # noqa: S324 - an id, not security


def _areas(ctx: ToolContext) -> list[Area]:
    cur = ctx.lake.cursor()
    out = []
    shapes = {k: f"ST_GeomFromText('{v}')" for k, v in WKT.items()}
    shapes |= {k: f"ST_Buffer(ST_Point({x}, {y}), {r}, 32)" for k, (x, y, r) in CIRCLES.items()}
    for name, expr in shapes.items():
        gj, x0, y0, x1, y1, km2 = cur.execute(
            f"SELECT ST_AsGeoJSON(g), ST_XMin(g), ST_YMin(g), ST_XMax(g), ST_YMax(g), "
            f"ST_Area_Spheroid(g) / 1e6 FROM (SELECT {expr} AS g)"
        ).fetchone()
        a = Area(
            area_id=aid(name),
            name=name,
            level="drawn",
            iso3=[],
            parents=[],
            geometry=json.loads(gj),
            bbox=[x0, y0, x1, y1],
            area_km2=float(km2),
            source={"dataset": "test shape", "licence": "none"},
        )
        ctx.area_store.put(a)
        out.append(a)
    return out


def _reference(
    ctx: ToolContext,
    table: str,
    pos: tuple[str, str],
    area: Area,
    measure: str,
    by: list[str],
    where: dict,
) -> dict:
    lon, lat = pos
    keys = "".join(f', "{b}"' for b in by)
    filt = "".join(f" AND \"{k}\" = '{v}'" for k, v in where.items())
    rows = (
        ctx.lake.cursor()
        .execute(
            f'SELECT 1{keys}, count(*), sum("{measure}") FROM {table} '
            f"WHERE {lon} BETWEEN -180 AND 180 AND {lat} BETWEEN -90 AND 90 "
            f"AND ST_Contains(ST_GeomFromGeoJSON(?), ST_Point({lon}, {lat})){filt} GROUP BY ALL",
            [json.dumps(area.geometry)],
        )
        .fetchall()
    )
    return {tuple(r[1 : 1 + len(by)]): (r[-2], r[-1]) for r in rows}


def _got(data: dict, measure: str, by: list[str]) -> dict:
    return {tuple(r[b] for b in by): (r["n"], r[f"{measure}_sum"]) for r in data["rows"]}


CASES = [
    ("pts.units", ("lon", "lat"), "mw", [], {}),
    ("pts.units", ("lon", "lat"), "mw", ["fuel"], {}),
    ("pts.units", ("lon", "lat"), "mw", ["fuel", "status"], {}),
    ("pts.units", ("lon", "lat"), "mw", [], {"status": "planned"}),
    ("pts.units", ("lon", "lat"), "mw", ["status"], {"fuel": "solar"}),
    (
        "pts.parcels",
        ("ST_X(ST_Centroid(geometry))", "ST_Y(ST_Centroid(geometry))"),
        "capacity_mw",
        [],
        {},
    ),
    (
        "pts.parcels",
        ("ST_X(ST_Centroid(geometry))", "ST_Y(ST_Centroid(geometry))"),
        "capacity_mw",
        ["class"],
        {},
    ),
]


@pytest.mark.parametrize("detailed", [False, True])
@pytest.mark.parametrize("res", [5, 6, 7])
@pytest.mark.parametrize(("table", "pos", "measure", "by", "where"), CASES)
def test_interior_plus_boundary_equals_row_sum(
    table, pos, measure, by, where, res, detailed, monkeypatch
):
    """`detailed`: cells built the way detailed outlines are (boundary sampling, one exact test
    per group of cells), forced on the test shapes."""
    if detailed:
        monkeypatch.setattr(area_sum_mod, "DETAILED_VERTICES", 0)
    ctx = ToolContext(settings())
    used_rollup = 0
    for a in _areas(ctx):
        d = exact_sum(ctx, table, a.as_dict(), [measure], by, where, res)
        assert _got(d, measure, by) == _reference(ctx, table, pos, a, measure, by, where), (
            a.name,
            res,
        )
        used_rollup += d.get("interior_cells", 0)
    assert used_rollup > 0  # the rollups did part of the work


def test_tool_answer_names_its_method_and_sources():
    ctx = ToolContext(settings())
    _areas(ctx)
    r = area_sum(ctx, "pts.units", aid("region_box"), measures=["mw"], by=["fuel"])
    d = r["data"]
    assert d["method"].startswith("exact:") and d["rollup"] == "rollups.pts__units_r5"
    assert {s["table"] for s in r["sources"]} == {"pts.units", "rollups.pts__units_r5"}


def test_falls_back_to_rows_when_no_rollup_holds_the_column():
    ctx = ToolContext(settings())
    _areas(ctx)
    d = area_sum(ctx, "pts.units", aid("city_box"), measures=["id"])["data"]
    assert "rows inside the area" in d["method"] and "rollup" not in d
