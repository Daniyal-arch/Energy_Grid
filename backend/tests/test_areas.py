"""Areas (brief 27 A1, A2): resolve_area at several levels and in_area in run_sql."""

import pytest

from tests.conftest import settings
from tools.areas import resolve_area
from tools.context import ToolContext
from tools.sql import run_sql


@pytest.fixture()
def ctx():
    return ToolContext(settings())


def area(ctx, **kw):
    r = resolve_area(ctx, **kw)
    assert r["data"].get("area"), r["data"]
    return r["data"]


def test_country_group_state_and_county(ctx):
    de = area(ctx, names=["Germany"])["area"]
    assert de["level"] == "country" and de["iso3"] == ["DEU"]
    assert 340_000 < de["area_km2"] < 370_000
    assert de["area_id"].startswith("a_") and len(de["area_id"]) == 14
    assert area(ctx, names=["Germany"])["area"]["area_id"] == de["area_id"]  # stable
    nordics = area(ctx, names=["the Nordics"])["area"]
    assert nordics["level"] == "group" and set(nordics["iso3"]) >= {"DNK", "SWE", "FIN", "NOR"}
    assert area(ctx, names=["Texas"])["area"]["level"] == "us_state"
    harris = area(ctx, names=["Harris County, Texas"])["area"]
    assert harris["level"] == "us_county" and harris["parents"][0] == "Texas"


def test_region_city_neighbourhood_and_ambiguity(ctx):
    d = area(ctx, names=["Oberbayern"])
    assert d["area"]["level"] == "nuts2"
    lim = area(ctx, names=["Limburg"])
    assert lim["ambiguous"] and {c["iso3"][0] for c in lim["candidates"]} >= {"NLD", "BEL"}
    be = area(ctx, names=["Limburg (BE)"])["area"]
    assert be["iso3"] == ["BEL"]
    paris = area(ctx, names=["Paris"])
    assert paris["area"]["iso3"] == ["FRA"] and paris["ambiguous"]
    tx = area(ctx, names=["Paris, Texas"])["area"]
    assert tx["iso3"] == ["USA"] and tx["level"] == "us_place"
    nb = area(ctx, names=["Burgwallen-Oude Zijde"], level="neighbourhood")["area"]
    assert nb["level"] == "nl_buurt" and nb["parents"][0] == "Amsterdam"


def test_drawn_circle_union_buffer_screen_and_world(ctx):
    ctx.view = {
        "drawn": {"kind": "polygon", "ring": [[4.8, 52.3], [5.0, 52.3], [5.0, 52.4], [4.8, 52.4]]},
        "camera": {"center": [5, 52], "zoom": 6, "bounds": [3, 50, 7, 54]},
    }
    drawn = area(ctx, from_view="drawn")["area"]
    assert drawn["level"] == "polygon" and drawn["iso3"] == ["NLD"]
    screen = area(ctx, from_view="screen")["area"]
    assert screen["level"] == "bbox"
    c = area(ctx, point=(4.48, 51.92), radius_km=20, name="Rotterdam port")["area"]
    assert c["level"] == "circle" and abs(c["area_km2"] - 1256.6) < 10
    u = area(ctx, names=["Belgium", "Netherlands", "Luxembourg"])["area"]
    assert set(u["iso3"]) == {"BEL", "NLD", "LUX"}
    b = area(ctx, names=["Luxembourg"], buffer_km=10)["area"]
    lux = area(ctx, names=["Luxembourg"])["area"]
    assert b["area_km2"] > lux["area_km2"] + 2000
    assert area(ctx, names=["world"])["area"]["area_km2"] > 5e8
    assert area(ctx, names=["Lyon"], radius_km=30)["area"]["level"] == "circle"


def test_nothing_invented(ctx):
    r = resolve_area(ctx, names=["Lyon"])["data"]
    assert r["area"] is None and "no outline" in r["note"]
    r = resolve_area(ctx, names=["Atlantis"])["data"]
    assert r["area"] is None


def test_in_area_in_run_sql(ctx):
    de = area(ctx, names=["Germany"])["area"]["area_id"]
    r = run_sql(ctx, f"SELECT count(*) AS n FROM app.eu_plants WHERE in_area(lon, lat, '{de}')")
    n = r["data"]["rows"][0][0]
    k = run_sql(ctx, "SELECT count(*) FROM app.eu_plants WHERE country = 'DE'")["data"]["rows"][0][
        0
    ]
    assert abs(n - k) <= 5
    assert any(de in s["table"] for s in r["sources"])
    assert "BETWEEN" in ctx.results.get(r["result_id"])["sql"]  # the bbox test came first
    r = run_sql(ctx, f"SELECT name, round(km2_inside(area_geom('{de}'), '{de}')) FROM areas")
    assert r["data"]["rows"][0][0] == "Germany"
    r = run_sql(ctx, "SELECT 1 WHERE in_area(1, 1, 'a_000000000000')")
    assert "unknown area" in r["data"]["error"]
    r = run_sql(ctx, f"SELECT round(km_inside(ST_GeomFromText('LINESTRING(5 50, 16 50)'), '{de}'))")
    assert 400 < r["data"]["rows"][0][0] < 500


def test_map_with_area_and_backend_shapes(ctx):
    from tools.maps import make_map

    a = area(ctx, names=["Oberbayern"])["area"]["area_id"]
    r = run_sql(ctx, "SELECT nuts_id, 1.5 AS v FROM shapes.nuts")
    spec = {
        "title": "Test",
        "area": {"area_id": a},
        "overlays": [
            {
                "id": "c",
                "kind": "choropleth",
                "data": {"result_id": r["result_id"], "key": "nuts_id", "shapes": "nuts2"},
                "value": {"column": "v", "unit": "x"},
                "legend": {"title": "t", "how": "h"},
                "source": "test",
            }
        ],
    }
    out = make_map(ctx, spec)
    assert out["data"]["map_id"].startswith("m_"), out
    rec = ctx.store.get_json(f"agent/maps/{out['data']['map_id']}.json")
    assert a in rec["areas"] and rec["areas"][a]["geometry"]["type"] in ("Polygon", "MultiPolygon")
    assert set(rec["shapes"]["nuts2"]["features"]) == {"NL42", "BE22", "DE21"}
    bad = make_map(ctx, {**spec, "area": {"area_id": "a_000000000000"}})
    assert "unknown area" in bad["data"]["error"]


def test_area_routes():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        r = c.get("/api/areas/resolve", params={"q": "Oberbayern"}).json()
        aid = r["area"]["area_id"]
        g = c.get(f"/api/areas/{aid}").json()
        assert g["name"] == "Oberbayern" and g["geometry"]["type"]
        s = c.get("/api/shapes/nuts2/DEU").json()
        assert list(s["features"]) == ["DE21"]
        assert c.get("/api/shapes/nope/DEU").status_code == 404


def test_area_stats_people_by_cell_centres(ctx):
    from tools.area_stats import area_stats

    a = area(ctx, names=["Oberbayern"])
    # the fixture box 10.7-13.1 E, 47.4-49.1 N holds 240 x 170 cells of 0.01 degrees, one person each
    assert a["area"]["figures"]["people"]["value"] == 240 * 170
    r = area_stats(ctx, a["area"]["area_id"], ["people", "solar"])
    f = r["data"]["figures"]
    assert f["people"]["value"] == 40800 and "centre lies inside" in f["people"]["how"]
    assert f["solar"]["value"] is None and "R2" in f["solar"]["error"]
    assert r["sources"][0]["licence"].startswith("CC BY 4.0")


def test_intersects_area_with_a_bbox_column_is_pruned(ctx):
    from data.duck import expand_in_area

    a = area(ctx, names=["Oberbayern"])["area"]
    rec = ctx.area_store.get(a["area_id"]).as_dict()
    sql = f"SELECT count(*) FROM t WHERE intersects_area(geometry, '{a['area_id']}', bbox)"
    out = expand_in_area(sql, [rec])
    assert "bbox.xmin <= 13.1" in out and "ST_INTERSECTS" in out.upper()
    r = run_sql(
        ctx,
        f"SELECT count(*) FROM (SELECT ST_Point(11.5, 48.1) AS geometry, "
        f"{{'xmin': 11.5, 'ymin': 48.1, 'xmax': 11.5, 'ymax': 48.1}} AS bbox) t "
        f"WHERE intersects_area(geometry, '{a['area_id']}', bbox)",
    )
    assert r["data"]["rows"] == [[1]], r
