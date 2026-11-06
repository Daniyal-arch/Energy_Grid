"""The six tools of brief 30 Track 4.6, against hand-written SQL on the same app tables."""

import pytest

from tests.conftest import settings
from tools.context import ToolContext
from tools.more import along, compare_areas, explain_coverage, export, nearest, trend
from tools.registry import by_name
from tools.sql import run_sql


@pytest.fixture()
def ctx():
    return ToolContext(settings())


def test_registered_with_mcp():
    names = set(by_name())
    assert {"nearest", "along", "compare_areas", "trend", "export", "explain_coverage"} <= names


def test_nearest_orders_by_distance(ctx):
    r = nearest(ctx, "plants_eu", lon=13.4, lat=52.5, k=5)["data"]
    km = [row[r["columns"].index("km")] for row in r["rows"]]
    assert len(km) == 5 and km == sorted(km) and km[0] < 50
    assert "haversine" in r["km_how"]
    assert "error" in nearest(ctx, "plants_eu")["data"]


def test_along_a_corridor(ctx):
    line = [[6.6, 51.4], [7.5, 51.5]]  # across the Ruhr
    r = along(ctx, "plants_eu", line=line, buffer_km=10, name="test line")
    d = r["data"]
    assert d["corridor"]["area_id"].startswith("a_") and d["row_count"] >= 1
    aid = d["corridor"]["area_id"]
    want = run_sql(ctx, f"SELECT count(*) FROM app.eu_plants WHERE in_area(lon, lat, '{aid}')")
    assert want["data"]["rows"][0][0] == d["row_count"]


def test_compare_two_countries(ctx):
    d = compare_areas(ctx, ["France", "Germany"], ["plants"])["data"]
    assert {t["area"] for t in d["tables"]} == {"France", "Germany"}
    fr = next(t for t in d["tables"] if t["area"] == "France")
    want = run_sql(
        ctx,
        "SELECT fuel, count(*) AS plants, round(sum(mw), 1) AS mw FROM app.eu_plants WHERE country IN ('FR') GROUP BY fuel ORDER BY mw DESC",
    )
    assert fr["rows"] == want["data"]["rows"]


def test_trend_by_commissioning_year(ctx):
    d = trend(ctx, "Spain", years=[2020, 2021])["data"]
    assert d["rows"] and {r[0] for r in d["rows"]} <= {2020, 2021}
    assert "retired" in d["method"]


def test_export_csv_with_terms_and_refusal(ctx):
    r = run_sql(ctx, "SELECT name, lon, lat, mw FROM app.eu_plants WHERE country = 'LU'")
    out = export(ctx, r["result_id"], "geojson")["data"]
    assert out["url"].startswith("/api/exports/x_") and out["rows"] == r["data"]["row_count"]
    assert (ctx.settings.results_dir / out["file"]).exists()
    pq = export(ctx, r["result_id"], "parquet")["data"]
    assert (ctx.settings.results_dir / pq["file"]).stat().st_size > 0
    ctx.results.put(
        "r_ffffffffffff",
        {"columns": ["a"], "rows": [[1]], "sources": [{"dataset": "x", "licence": "CC BY-NC 4.0"}]},
    )
    assert "not exported" in export(ctx, "r_ffffffffffff")["data"]["error"]


def test_explain_coverage(ctx):
    d = explain_coverage(ctx, "France", "room to connect")["data"]
    assert d["cells"] and d["cells"][0]["country"] == "FR" and d["cells"][0]["status"]


def test_export_route():
    from fastapi.testclient import TestClient

    from app.main import app

    ctx = ToolContext(settings())
    r = run_sql(ctx, "SELECT name, lon, lat FROM app.eu_plants WHERE country = 'LU'")
    with TestClient(app) as c:
        got = c.get("/api/export", params={"result_id": r["result_id"], "format": "csv"})
        assert got.status_code == 200 and got.text.startswith("name,lon,lat")
        assert c.get("/api/export", params={"result_id": "r_000000000000"}).status_code == 404
        assert c.get("/api/export", params={"result_id": "x"}).status_code == 422
