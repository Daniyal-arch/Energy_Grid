"""Areas in queries are parsed once per container and shared by every cursor (brief 32)."""

import pytest

from tests.conftest import settings
from tools.context import ToolContext


def square(i: int, x0: float, y0: float, d: float) -> dict:
    ring = [[x0, y0], [x0 + d, y0], [x0 + d, y0 + d], [x0, y0 + d], [x0, y0]]
    return {"area_id": f"a_{i:012x}", "name": f"sq{i}", "level": "polygon",
            "geometry": {"type": "Polygon", "coordinates": [ring]}, "bbox": [x0, y0, x0 + d, y0 + d]}  # fmt: skip


def test_areas_registered_once_and_answers_unchanged() -> None:
    lake = ToolContext(settings()).lake
    a, b = square(1, 0, 0, 10), square(2, 20, 20, 5)
    sql = (
        "SELECT count(*) FROM (SELECT x::DOUBLE AS x, y::DOUBLE AS y FROM range(30) t(x), "
        "range(30) u(y)) WHERE in_area(x, y, '{}')"
    )
    first = lake.run(sql.format(a["area_id"]), areas=[a]).rows
    assert first == [[81]]  # points 1..9 x 1..9 strictly inside (boundary excluded)
    again = lake.run(sql.format(a["area_id"]), areas=[a, b]).rows
    assert again == first
    assert lake.run(sql.format(b["area_id"]), areas=[b]).rows == [[16]]
    # the query sees only its own areas
    assert lake.run("SELECT count(*) FROM areas", areas=[b]).rows == [[1]]
    n = (
        lake.cursor()
        .execute(
            "SELECT count(*) FROM areamem.areas WHERE area_id IN (?, ?)",
            [a["area_id"], b["area_id"]],
        )
        .fetchone()[0]
    )
    assert n == 2  # each outline parsed once


def test_least_recently_used_areas_dropped(monkeypatch) -> None:
    lake = ToolContext(settings()).lake
    monkeypatch.setattr(type(lake), "AREAS_KEPT", 3)
    for i in range(6):
        a = square(10 + i, i, 0, 1)
        assert lake.run("SELECT count(*) FROM areas", areas=[a]).rows == [[1]]
    n = lake.cursor().execute("SELECT count(*) FROM areamem.areas").fetchone()[0]
    assert n == 3


@pytest.mark.parametrize("detailed", [False, True])
def test_cell_accelerated_in_area_equals_plain_contains(detailed: bool, monkeypatch) -> None:
    """in_area through H3 cells and clipped outlines gives exactly ST_Contains, on every shape
    of the area-sum tests, at points spread over each box and points within metres of edges;
    `detailed` builds the cells the way detailed outlines are built (boundary sampling and one
    test per group of cells, tools.area_sum._cells_detailed)."""
    from tests.test_area_sum import _areas
    from tools import area_sum

    ctx = ToolContext(settings())
    lake = ctx.lake
    areas = [a.as_dict() for a in _areas(ctx)]
    if detailed:
        monkeypatch.setattr(area_sum, "DETAILED_VERTICES", 0)
        # fresh ids: the plain variant may have built cells for these areas already
        areas = [{**a, "area_id": "a_d" + a["area_id"][3:]} for a in areas]
    cur = lake.cursor()
    for a in areas:
        if a["area_id"] in lake._area_res:
            continue
        lake.run("SELECT 1", areas=[a])
    lake.wait_cells()
    built = [a for a in areas if a["area_id"] in lake._area_res]
    assert built, "no area got H3 cells (h3 extension missing?)"
    for a in built:
        x0, y0, x1, y1 = a["bbox"]
        # a 60 x 60 grid over the box, plus points on and just off the outline's vertices
        pts = f"""
            SELECT {x0} + (i + 0.5) * {(x1 - x0) / 60} AS x, {y0} + (j + 0.5) * {(y1 - y0) / 60} AS y
            FROM range(60) a(i), range(60) b(j)
            UNION ALL
            SELECT ST_X(p) + d, ST_Y(p) + d FROM (
                SELECT unnest(ST_Dump(ST_Points(geometry))).geom AS p FROM areamem.areas
                WHERE area_id = '{a["area_id"]}'), (VALUES (0.0), (1e-7), (-1e-7), (1e-4)) t(d)"""
        want = cur.execute(
            f"SELECT count(*) FILTER (WHERE ST_Contains(g, ST_Point(x, y))), count(*) FROM ({pts}), "
            f"(SELECT geometry AS g FROM areamem.areas WHERE area_id = '{a['area_id']}')"
        ).fetchone()
        got = lake.run(
            f"SELECT count(*) FILTER (WHERE in_area(x, y, '{a['area_id']}')), count(*) FROM ({pts})",
            areas=[a],
        ).rows[0]
        assert list(got) == list(want), a["name"]
