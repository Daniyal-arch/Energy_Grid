import asyncio
import json

from agent.deps import build_deps
from agent.graph import GRAPH, initial_state
from agent.limits import MemoryLimits, hash_ip
from agent.skills import get_skills
from app.settings import get_settings
from app.sse import with_heartbeat
from obs import tracing
from tests.conftest import settings
from tools.context import ToolContext


def test_heartbeat_between_slow_events():
    async def slow():
        await asyncio.sleep(0.25)
        yield "event: done\ndata: {}\n\n"

    async def collect():
        return [x async for x in with_heartbeat(slow(), every=0.1)]

    out = asyncio.run(collect())
    assert out[0] == ": heartbeat\n\n" and out[-1].startswith("event: done")


def test_stream_error_becomes_an_event():
    async def broken():
        yield "event: text\ndata: {}\n\n"
        raise RuntimeError("boom")

    async def collect():
        return [x async for x in with_heartbeat(broken(), every=1)]

    out = asyncio.run(collect())
    assert out[-1].startswith("event: error") and "boom" in out[-1]


def test_token_bucket_and_spend():
    lim = MemoryLimits(per_hour=2)
    h = hash_ip("203.0.113.9", "salt")
    assert len(h) == 24 and "203" not in h
    assert lim.take(h) and lim.take(h) and not lim.take(h)
    lim.add_spend(0.5)
    lim.add_spend(0.25)
    assert lim.spent_today() == 0.75


def test_every_skill_parses_and_names_its_catalogue_entries():
    s = get_skills(get_settings().agent_dir)
    assert set(s.skills) == {
        "lake-sql",
        "make-map",
        "site-screening",
        "explain-view",
        "prices",
        "grid-capacity",
        "emissions",
        "places-and-shapes",
        "area-analysis",
        "datacentre-siting",
        "battery-siting",
        "solar-wind-siting",
        "offshore-wind",
        "physical-risk",
        "grid-planning",
        "revenues",
        "industrial-decarbonisation",
        "heat-networks",
        "ev-electrification",
        "public-money",
    }
    for sk in s.skills.values():
        assert sk.description and "Relies on" in sk.body


def test_trace_spans_and_run_record():
    exp = tracing.memory_exporter
    exp.clear()
    s = settings()
    d = build_deps(s, ctx=ToolContext(s))
    with tracing.span("test.request"):
        tid = tracing.current_trace_id()
        out = asyncio.run(
            GRAPH.ainvoke(
                initial_state("How much capacity per fuel does Poland have?", trace_id=tid),
                {"configurable": {"deps": d}},
            )
        )
    spans = exp.get_finished_spans()
    names = {sp.name for sp in spans}
    assert {
        "agent.node.guard",
        "agent.node.router",
        "agent.node.analyst",
        "agent.tool",
        "sql.query",
        "agent.node.grounding",
        "agent.node.finish",
    } <= names
    assert all(format(sp.context.trace_id, "032x") == tid for sp in spans)
    model_span = next(sp for sp in spans if sp.name == "agent.node.analyst")
    assert model_span.attributes["gen_ai.request.model"] == "fake:scripted"
    assert model_span.attributes["gen_ai.usage.input_tokens"] > 0
    sql_span = next(sp for sp in spans if sp.name == "sql.query")
    assert (
        sql_span.attributes["db.rows"] > 0 and len(sql_span.attributes["db.statement.hash"]) == 16
    )
    rec = d.ctx.store.get_json(f"agent/logs/{out['run']['date']}/{tid}.json")
    assert (
        rec["question"].startswith("How much") and rec["sql"] and rec["grounding"]["score"] == 1.0
    )
    assert rec["tool_calls"][1]["rows"] > 0 and "cost_usd" in rec and json.dumps(rec)


def test_eval_questions_and_scorers():
    from pathlib import Path

    import yaml

    from evals.scorers import map_correct, number_correct

    qs = yaml.safe_load(
        (Path(get_settings().agent_dir) / "evals" / "questions.yaml").read_text(encoding="utf-8")
    )["questions"]
    assert sum(1 for q in qs if "numbers" in q) >= 40 and sum(1 for q in qs if "map" in q) >= 10
    assert len({q["id"] for q in qs}) == len(qs)
    assert number_correct(["15,508", "16,011"], "wind 15,508 MW and offshore 16.0 GW") == 0.5
    assert number_correct(["176042304.25"], "176,042,304.25 customer-hours") == 1.0
    assert number_correct(["700.75"], "ES had 700.75 hours") == 1.0
    spec = {
        "title": "t",
        "overlays": [
            {
                "id": "a",
                "kind": "choropleth",
                "data": {"result_id": "r_0123456789ab", "key": "zone", "shapes": "bidding_zones"},
                "value": {"column": "h", "unit": "h"},
                "legend": {"title": "t", "how": "h"},
                "source": "ENTSO-E",
            }
        ],
    }
    assert map_correct({"kind": "choropleth", "key": "zone"}, [{"spec": spec}]) == 1.0
    assert map_correct({"kind": "points", "key": "lon/lat"}, [{"spec": spec}]) == 0.0
