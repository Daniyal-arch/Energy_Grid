"""Areas in queries are parsed once per container and shared by every cursor (brief 32)."""

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
    n = lake.cursor().execute("SELECT count(*) FROM areamem.areas").fetchone()[0]
    assert n == 2  # each outline parsed once


def test_least_recently_used_areas_dropped(monkeypatch) -> None:
    lake = ToolContext(settings()).lake
    monkeypatch.setattr(type(lake), "AREAS_KEPT", 3)
    for i in range(6):
        a = square(10 + i, i, 0, 1)
        assert lake.run("SELECT count(*) FROM areas", areas=[a]).rows == [[1]]
    n = lake.cursor().execute("SELECT count(*) FROM areamem.areas").fetchone()[0]
    assert n == 3
