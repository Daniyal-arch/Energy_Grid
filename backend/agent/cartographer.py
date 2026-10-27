"""The cartographer: the fast model turns the analyst's query results into a MapSpec (and a
ChartSpec when one was asked), validated, at most three tries. A separate small model builds
specs well and keeps the analyst's context clean."""

from __future__ import annotations

import json
import time
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer

from agent.analyst import _emit
from agent.deps import deps_of, prompt
from agent.mapspec import ChartSpec, MapSpec
from agent.models import text_of
from agent.state import AgentState
from agent.usage import record
from obs.tracing import span
from tools.maps import check_map, known_layers, make_chart, make_map

TRIES = 3


def _json(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in the reply")
    out = json.loads(text[start : end + 1])
    if not isinstance(out, dict):
        raise ValueError("the reply is not a JSON object")
    return out


def needs_cartographer(state: AgentState) -> bool:
    route = state.get("route") or {}
    done = any(
        t["name"] in ("make_map", "make_chart") and not t["error"]
        for t in state.get("tool_log", [])
    )
    return (
        bool(route.get("map") or route.get("chart"))
        and bool(state.get("result_ids"))
        and not done
        and not state.get("cartographer_done")
        and state.get("stop") is None
    )


async def cartographer(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    d = deps_of(config)
    d.ctx.emit = _emit(get_stream_writer())
    route = state.get("route") or {}
    summaries = [x for rid in state.get("result_ids", [])[-4:] if (x := d.ctx.results.summary(rid))]
    schema = {"MapSpec": MapSpec.model_json_schema(), "ChartSpec": ChartSpec.model_json_schema()}
    sys = prompt(
        "cartographer.md",
        layers=", ".join(sorted(known_layers(str(d.settings.atlas_root)))) or "(none)",
        schema=json.dumps(schema, separators=(",", ":")),
    )
    wanted = " and ".join(
        w for w, on in (("a map", route.get("map")), ("a chart", route.get("chart"))) if on
    )
    ask = (
        f"Question: {state['question']}\nAnswer so far: {state.get('answer', '')[:1500]}\n"
        f"Wanted: {wanted}\n\nRESULTS: {json.dumps(summaries, default=str)}\n\n"
    )
    msgs: list[BaseMessage] = [SystemMessage(content=sys), HumanMessage(content=ask)]
    usage, maps, charts, errors = [], [], [], []
    with span("agent.node.cartographer"):
        for _ in range(TRIES):
            t0 = time.perf_counter()
            resp = await d.fast.ainvoke(msgs, config)
            usage.append(record("cartographer", d.fast_entry, resp, time.perf_counter() - t0))
            try:
                out = _json(text_of(resp))
                problems = []
                if route.get("map") and out.get("map"):
                    m, err, _ = check_map(d.ctx, out["map"])
                    if err:
                        problems.append(f"map: {err}")
                if route.get("chart") and out.get("chart"):
                    try:
                        ChartSpec.model_validate(out["chart"])
                    except Exception as e:
                        problems.append(f"chart: {e}")
                if problems:
                    raise ValueError("; ".join(problems))
            except ValueError as e:
                errors.append(str(e)[:500])
                msgs += [
                    AIMessage(content=text_of(resp)),
                    HumanMessage(content=f"Invalid: {e}. Reply with corrected JSON only."),
                ]
                continue
            if route.get("map") and out.get("map"):
                r = make_map(d.ctx, out["map"])
                if "map_id" in r["data"]:
                    maps.append({"id": r["data"]["map_id"], "spec": out["map"]})
            if route.get("chart") and out.get("chart"):
                r = make_chart(d.ctx, out["chart"])
                if r["data"].get("chart") == "sent":
                    charts.append(out["chart"])
            break
    return {
        "maps": maps,
        "charts": charts,
        "usage": usage,
        "cartographer_done": True,
        "grounding": {**state.get("grounding", {}), "cartographer_errors": errors},
    }
