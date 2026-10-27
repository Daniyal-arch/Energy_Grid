import asyncio
import json

from langchain_core.messages import AIMessage

from agent.deps import build_deps
from agent.fake import FakeChatModel
from agent.graph import GRAPH, initial_state
from agent.limits import MemoryLimits, get_limits
from tests.conftest import settings


def run(question, deps=None, **kw):
    s = settings(**kw)
    d = deps or build_deps(s)
    return asyncio.run(
        GRAPH.ainvoke(
            initial_state(question, trace_id="t" * 32),
            {"configurable": {"deps": d}, "recursion_limit": 80},
        )
    ), d


def test_answer_with_grounded_numbers():
    out, _ = run("How much capacity per fuel does Spain have?")
    assert [t["name"] for t in out["tool_log"]] == ["search_catalog", "run_sql"]
    assert out["grounding"]["score"] == 1.0 and out["grounding"]["numbers"] > 0
    assert out["run"]["sources"][0]["dataset"] == "plants"
    assert out["route"]["kind"] == "answer" and not out["maps"]


def test_map_question_runs_the_cartographer():
    out, _ = run("Show the largest power plants in France on a map")
    assert out["route"]["map"] and len(out["maps"]) == 1
    assert out["maps"][0]["spec"]["overlays"][0]["kind"] == "points"


def test_price_question_loads_the_prices_skill():
    out, _ = run("Which zones had the most negative price hours?")
    assert out["route"]["skills"] == ["prices"]
    assert out["tool_log"][0]["name"] == "load_skill" and out["tool_log"][0]["args"] == {
        "name": "prices"
    }
    assert "Zones, not countries" in json.dumps(out["tool_log"][0]["result"])


def scripted(*replies):
    s = settings()
    d = build_deps(s)
    d.main = FakeChatModel(script=list(replies))
    return d


def test_grounding_repair_then_mark():
    sql = {"name": "run_sql", "args": {"sql": "SELECT 41.5 AS v"}, "id": "c1"}
    d = scripted(
        AIMessage(content="", tool_calls=[sql]),
        AIMessage(content="The value is 99.9."),  # not in the result: repair round
        AIMessage(content="The value is 77.7."),  # still not: marked
    )
    out, _ = run("What is the value?", deps=d)
    assert out["repaired"] and out["grounding"]["first_pass"]["ungrounded"] == ["99.9"]
    assert out["grounding"]["ungrounded"] == ["77.7"]
    assert out["answer"].endswith("(Not found in the tool results, unverified: 77.7)")


def test_grounding_repair_fixes():
    sql = {"name": "run_sql", "args": {"sql": "SELECT 41.5 AS v"}, "id": "c1"}
    d = scripted(
        AIMessage(content="", tool_calls=[sql]),
        AIMessage(content="It is 99.9."),
        AIMessage(content="It is 41.5."),
    )
    out, _ = run("What is the value?", deps=d)
    assert out["grounding"]["score"] == 1.0 and out["answer"] == "It is 41.5."


def test_tool_call_cap():
    call = {"name": "find_place", "args": {"text": "Texas"}, "id": "c"}
    d = scripted(
        *[AIMessage(content="", tool_calls=[{**call, "id": f"c{i}"}]) for i in range(2)],
        AIMessage(content="", tool_calls=[{**call, "id": "c9"}]),
    )
    d.settings = settings(max_tool_calls=2)
    out, _ = run("Where is Texas?", deps=d)
    assert out["tool_calls"] == 2  # the third call is never run
    assert any("Stop calling tools" in str(m.content) for m in out["messages"])


def test_refusal_is_handled():
    d = scripted(AIMessage(content="", response_metadata={"stop_reason": "refusal"}))
    out, _ = run("Something the model declines", deps=d)
    assert out["stop"] == "refusal" and "declined" in out["answer"]


def test_budget_cap_stops_before_any_model_call():
    lim = get_limits(settings())
    assert isinstance(lim, MemoryLimits)
    lim.add_spend(1000.0)
    try:
        out, _ = run("Anything")
        assert out["stop"] == "budget" and not out["usage"]
    finally:
        lim.spend.clear()


def test_too_long_question():
    out, _ = run("x" * 3000)
    assert out["stop"] == "too_long"
