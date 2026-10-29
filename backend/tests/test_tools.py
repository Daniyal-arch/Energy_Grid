import json

import pytest

from tests.conftest import settings
from tools.context import ToolContext
from tools.registry import by_name, langchain_tools, specs


@pytest.fixture(scope="module")
def ctx():
    return ToolContext(settings())


def call(ctx, tool, **kw):
    out = by_name()[tool].run(ctx, **kw)
    assert set(out) >= {"data", "sources"}
    for s in out["sources"]:
        assert set(s) == {"dataset", "table", "licence", "retrieved"}
    return out


def test_tool_list_sorted_and_typed(ctx):
    names = [s.name for s in specs()]
    assert names == sorted(names)
    assert {
        "search_catalog",
        "describe_table",
        "run_sql",
        "find_place",
        "site_figures",
        "live",
        "make_map",
        "make_chart",
        "load_skill",
    } <= set(names)
    for t in langchain_tools(ctx):
        assert t.args_schema is not None


def test_search_catalog(ctx):
    hits = call(ctx, "search_catalog", query="negative day-ahead prices per zone")["data"][
        "matches"
    ]
    assert hits[0]["name"] == "app.eu_prices" and hits[0]["queryable"]
    assert len(hits) <= 10


def test_describe_table_app_and_lake(ctx):
    d = call(ctx, "describe_table", name="app.eu_plants")["data"]
    assert d["queryable"] and d["row_count"] > 7000 and len(d["sample"]) == 5
    assert any(c["name"] == "mw" and "MW" in c["meaning"] for c in d["columns"])
    d = call(ctx, "describe_table", name="registers.gb")["data"]
    assert d["queryable"] and d["catalogue"]["examples"]
    assert "error" in call(ctx, "describe_table", name="nope.nope")["data"]


def test_run_sql_result_id_and_sources(ctx):
    out = call(
        ctx,
        "run_sql",
        sql="SELECT country, round(sum(mw)) AS mw FROM app.eu_plants GROUP BY 1 ORDER BY 2 DESC",
    )
    d = out["data"]
    assert d["columns"] == ["country", "mw"] and d["row_count"] == len(d["rows"])
    assert out["result_id"].startswith("r_") and out["sources"][0]["dataset"] == "plants"
    full = ctx.results.get(out["result_id"])
    assert full["rows"] == d["rows"]


def test_run_sql_shows_at_most_the_configured_rows(ctx):
    out = call(ctx, "run_sql", sql="SELECT * FROM app.world_plants")
    n = ctx.settings.sql_rows_returned
    assert out["data"]["rows_shown"] == n and out["data"]["row_count"] > n
    assert len(ctx.results.get(out["result_id"])["rows"]) == out["data"]["row_count"]


def test_run_sql_refusal_goes_back_as_data(ctx):
    out = call(ctx, "run_sql", sql="DROP TABLE app.eu_plants")
    assert out["data"]["error"].startswith("refused")


def test_find_place(ctx):
    assert call(ctx, "find_place", text="Texas")["data"]["places"][0]["codes"] == {"state": "TX"}
    assert call(ctx, "find_place", text="DK1")["data"]["places"][0]["kind"] == "bidding_zone"
    p = call(ctx, "find_place", text="52.37 N, 4.90 E")["data"]["places"][0]
    assert p["codes"]["iso2"] == "NL" and p["centre"] == [4.9, 52.37]
    assert call(ctx, "find_place", text="Germany")["data"]["places"][0]["codes"] == {"iso2": "DE"}


def test_site_figures_amsterdam(ctx):
    d = call(ctx, "site_figures", lon=4.90, lat=52.37, radius_km=50)["data"]
    items = {f[0]: f for f in d["figures"]}
    assert d["place"]["codes"]["iso2"] == "NL"
    assert items["Substations within 50 km"][1] > 0
    assert items["Day-ahead NL, 12-month average"][2] == "EUR/MWh"
    assert "Baseline water stress" in items
    assert all(len(f) == 5 for f in d["figures"])


def test_site_figures_us(ctx):
    d = call(ctx, "site_figures", lon=-95.37, lat=29.76, radius_km=25)["data"]
    assert d["place"]["codes"]["state"] == "TX"
    assert any(f[0].startswith("Operating within") and f[1] > 0 for f in d["figures"])


def test_live_validation(ctx):
    assert (
        "file must be one of"
        in call(ctx, "live", source="eu_snapshot", params={"file": "../secrets"})["data"]["error"]
    )
    assert "not configured" in call(ctx, "live", source="eia930", params={})["data"]["error"]


def test_make_map_and_chart(ctx):
    rid = call(
        ctx,
        "run_sql",
        sql="SELECT name, fuel, mw, lon, lat FROM app.eu_plants WHERE country = 'NL' LIMIT 20",
    )["result_id"]
    spec = {
        "title": "Plants in the Netherlands",
        "overlays": [
            {
                "id": "nl",
                "kind": "points",
                "data": {"result_id": rid, "lon": "lon", "lat": "lat"},
                "size": {"column": "mw", "unit": "MW"},
                "legend": {"title": "Capacity", "how": "as published"},
                "tooltip": ["name", "mw"],
                "source": "powerplantmatching",
            }
        ],
    }
    events = []
    ctx.emit = lambda e, d: events.append(e)
    out = call(ctx, "make_map", spec=spec)
    assert out["data"]["map_id"].startswith("m_") and "map" in events
    saved = ctx.store.get_json(f"agent/maps/{out['data']['map_id']}.json")
    assert saved["data"][rid]["columns"] == ["name", "fuel", "mw", "lon", "lat"]
    bad = json.loads(json.dumps(spec))
    bad["overlays"][0]["tooltip"] = ["nope"]
    assert "not in the data" in call(ctx, "make_map", spec=bad)["data"]["error"]
    bad["app"] = {"layers": ["notALayer"]}
    assert "unknown app layers" in call(ctx, "make_map", spec=bad)["data"]["error"]
    chart = {
        "kind": "bar",
        "title": "MW",
        "data": {"result_id": rid},
        "x": {"column": "name"},
        "series": [{"column": "mw", "label": "MW", "unit": "MW"}],
        "source": "powerplantmatching",
    }
    assert call(ctx, "make_chart", spec=chart)["data"]["chart"] == "sent"


def test_skills_tools(ctx):
    assert any(s["name"] == "prices" for s in call(ctx, "list_skills")["data"])
    body = call(ctx, "load_skill", name="lake-sql")["data"]
    assert "references/patterns.md" in body["files"]
    assert (
        "haversine"
        in call(ctx, "read_skill_file", name="lake-sql", path="references/patterns.md")["data"][
            "text"
        ]
    )
    assert (
        "error" in call(ctx, "read_skill_file", name="lake-sql", path="../../models.yaml")["data"]
    )
