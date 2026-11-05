"""The result cache (brief 30 Track 4.3): a repeated query reads the cache (marked cached), the
result id still serves its rows, a new catalogue date misses, errors are not cached."""

import asyncio

from langchain_core.messages import AIMessage

from agent.cache import ResultCache, _norm_sql, key_of
from agent.deps import build_deps
from agent.fake import FakeChatModel
from agent.graph import GRAPH, initial_state
from tests.conftest import settings
from tools.context import ToolContext
from tools.sql import run_sql


def test_keys_fold_whitespace_and_case_but_not_literals():
    assert _norm_sql("SELECT  1\n FROM t;") == _norm_sql("select 1 from t")
    assert _norm_sql("SELECT 'A'") != _norm_sql("SELECT 'a'")
    assert key_of("run_sql", {"sql": "SELECT 1"}, "d1") != key_of(
        "run_sql", {"sql": "SELECT 1"}, "d2"
    )


def test_hit_restores_the_result_rows():
    ctx = ToolContext(settings())
    c = ResultCache(ctx)
    args = {"sql": "SELECT 41.5 AS v -- cache test"}
    res = run_sql(ctx, **args)
    c.put("run_sql", args, res)
    (ctx.settings.results_dir / f"{res['result_id']}.json").unlink()
    hit = c.get("run_sql", {"sql": "select 41.5 as v -- cache test"})
    assert hit == res and ctx.results.get(res["result_id"])["rows"] == [[41.5]]
    c.put("run_sql", {"sql": "SELECT nope"}, {"data": {"error": "x"}, "sources": []})
    assert c.get("run_sql", {"sql": "SELECT nope"}) is None
    assert c.get("live", {"source": "eu_snapshot"}) is None


def test_second_ask_reads_the_cache():
    sql = {"name": "run_sql", "args": {"sql": "SELECT 77.25 AS v"}, "id": "c1"}

    def once():
        d = build_deps(settings())
        d.main = FakeChatModel(
            script=[AIMessage(content="", tool_calls=[sql]), AIMessage(content="It is 77.25.")]
        )
        return asyncio.run(
            GRAPH.ainvoke(
                initial_state("What is v?", trace_id="t" * 32),
                {"configurable": {"deps": d}, "recursion_limit": 80},
            )
        )

    once()
    out = once()
    assert out["tool_log"][0]["cached"] is True and out["grounding"]["score"] == 1.0
