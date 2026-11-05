"""Instant answers (brief 30 Track 4.2): six SQL templates, numbers equal to hand-written SQL,
the router rule, the graph's quick node (no model call) and the route."""

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from agent.deps import build_deps
from agent.graph import GRAPH, initial_state
from app.main import app
from tests.conftest import settings
from tools.context import ToolContext
from tools.quick import TEMPLATES, as_text, match, quick
from tools.sql import run_sql


@pytest.fixture()
def ctx():
    return ToolContext(settings())


def rows(ctx, sql):
    return run_sql(ctx, sql)["data"]["rows"]


def test_six_templates():
    assert set(TEMPLATES) == {"profile", "top", "totals", "compare", "published", "prices"}


def test_profile_equals_the_sql(ctx):
    r = quick(ctx, "profile", "Benelux")
    t = r["data"]["tables"][0]
    want = rows(
        ctx,
        "SELECT fuel, count(*) AS plants, round(sum(mw), 1) AS mw FROM app.eu_plants "
        "WHERE country IN ('BE', 'NL', 'LU') GROUP BY fuel ORDER BY mw DESC",
    )
    assert t["rows"] == want
    # the area eval's total (agent/evals/areas.yaml: 343 plants, 54,490 MW)
    assert sum(x[1] for x in t["rows"]) == 343
    assert round(sum(x[2] for x in t["rows"])) == 54490
    assert t["as_of"] and t["method"] and r["sources"]


def test_top_totals_prices_published_compare(ctx):
    top = quick(ctx, "top", "Germany", n=5)["data"]["tables"][0]
    want = rows(
        ctx,
        "SELECT name, country, fuel, mw, year FROM app.eu_plants WHERE country IN ('DE') ORDER BY mw DESC LIMIT 5",
    )
    assert top["rows"] == want and len(want) == 5
    tot = quick(ctx, "totals", "Texas")["data"]["tables"][0]
    assert tot["columns"] == ["status", "plants", "mw"] and tot["rows"]
    pr = quick(ctx, "prices", "Germany")["data"]["tables"][0]
    assert pr["rows"] == rows(
        ctx,
        "SELECT zone, mean_eur_mwh, min_eur_mwh, max_eur_mwh, negative_hours, period_start, period_end FROM app.eu_prices WHERE country IN ('DE') ORDER BY zone",
    )
    pub = quick(ctx, "published", "France")["data"]["tables"][0]
    assert pub["rows"] and {r[0] for r in pub["rows"]} == {"FR"}
    cmp = quick(ctx, "compare", "France; Germany")["data"]
    assert [a["iso3"] for a in cmp["area"]] == [["FRA"], ["DEU"]]
    assert {t["area"] for t in cmp["tables"]} == {"France", "Germany"}


def test_unknown_area_is_an_error_not_a_guess(ctx):
    r = quick(ctx, "profile", "Atlantis")
    assert "error" in r["data"] and r["sources"] == []
    assert as_text(r["data"]).startswith("No instant answer")


@pytest.mark.parametrize(
    ("q", "want"),
    [
        ("Tell me about Bavaria", {"template": "profile", "area": "Bavaria"}),
        (
            "top 5 power plants in Spain?",
            {"template": "top", "area": "Spain", "n": 5, "kind": "plants"},
        ),
        (
            "largest substations in Italy",
            {"template": "top", "area": "Italy", "kind": "substations"},
        ),
        ("capacity by fuel in Poland", {"template": "totals", "area": "Poland"}),
        ("Compare France and Germany", {"template": "compare", "area": "France;Germany"}),
        ("What data is published for Ireland?", {"template": "published", "area": "Ireland"}),
        ("day-ahead prices in Denmark", {"template": "prices", "area": "Denmark"}),
        ("Why are prices negative in Germany?", None),
        ("Show the largest power plants in Germany on a map", None),
    ],
)
def test_router_rule(q, want):
    assert match(q) == want


def test_graph_answers_without_a_model():
    d = build_deps(settings())
    out = asyncio.run(
        GRAPH.ainvoke(
            initial_state("Tell me about the Benelux", trace_id="t" * 32),
            {"configurable": {"deps": d}, "recursion_limit": 80},
        )
    )
    assert out["route"]["kind"] == "quick"
    assert [t["name"] for t in out["tool_log"]] == ["quick"]
    assert not out.get("usage")
    assert out["grounding"]["score"] == 1.0, out["grounding"]
    assert "as of" in out["answer"]


def test_route_under_a_second():
    with TestClient(app) as c:
        c.get("/api/quick/profile", params={"area": "Benelux"})  # warm
        t0 = time.perf_counter()
        r = c.get("/api/quick/profile", params={"area": "Benelux"})
        assert time.perf_counter() - t0 < 1.0
        assert r.status_code == 200 and r.json()["tables"] and r.json()["text"]
        assert c.get("/api/quick/nope", params={"area": "Benelux"}).status_code == 404
        assert c.get("/api/quick/profile", params={"area": "Atlantis"}).status_code == 404
