"""The cartographer: the fast model designs the map (one map, or several side by side) and a
chart when one was asked, from the analyst's query results and the maps already on screen,
validated, at most three tries. It also edits a map on screen ("make it 3D", "split it into two
maps"): the browser sends the maps it shows, their data is brought back from the saved maps,
and the new spec replaces the old one. A separate small model builds specs well and keeps the
analyst's context clean."""

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
from tools.context import ToolContext
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


def view_maps(state: AgentState) -> list[dict[str, Any]]:
    """The agent maps the browser shows: [{id, spec}] (ids of saved maps)."""
    maps = (state.get("view") or {}).get("maps") or []
    return [m for m in maps if isinstance(m, dict) and str(m.get("id", "")).startswith("m_")][:4]


def restore_view_maps(ctx: ToolContext, maps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bring back the data of the maps on screen (their saved records) as results; returns the
    maps with their saved specs."""
    out = []
    for m in maps:
        rec = ctx.store.get_json(f"agent/maps/{m['id']}.json")
        if not rec:
            continue
        for rid, d in (rec.get("data") or {}).items():
            ctx.results.put(rid, {**d, "sources": rec.get("sources", [])})
        out.append({"id": rec["id"], "spec": rec["spec"]})
    return out


def needs_cartographer(state: AgentState) -> bool:
    route = state.get("route") or {}
    done = any(
        t["name"] in ("make_map", "make_chart") and not t["error"]
        for t in state.get("tool_log", [])
    )
    return (
        bool(route.get("map") or route.get("chart"))
        and bool(state.get("result_ids") or view_maps(state))
        and not done
        and not state.get("cartographer_done")
        and state.get("stop") is None
    )


async def cartographer(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    d = deps_of(config)
    d.ctx.emit = _emit(get_stream_writer())
    route = state.get("route") or {}
    current = restore_view_maps(d.ctx, view_maps(state))
    rids = list(dict.fromkeys(state.get("result_ids", [])[-6:]))
    for m in current:
        for o in MapSpec.model_validate(m["spec"]).all_overlays():
            if o.data.result_id and o.data.result_id not in rids:
                rids.append(o.data.result_id)
    summaries = [x for rid in rids if (x := d.ctx.results.summary(rid))]
    areas = [a.summary() for i in d.ctx.turn_areas if (a := d.ctx.area_store.get(i))]
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
        + (
            f"AREAS (resolved this turn): {json.dumps(areas, default=str)[:3000]}\n\n"
            if areas
            else ""
        )
        + (
            f"CURRENT MAPS (on screen): {json.dumps(current, default=str)[:6000]}\n\n"
            if current
            else ""
        )
    )
    msgs: list[BaseMessage] = [SystemMessage(content=sys), HumanMessage(content=ask)]
    usage, maps, charts, errors = [], [], [], []
    note = ""
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
            note = str(out.get("note") or "")[:300]
            if out.get("map"):
                spec = out["map"]
                panels = spec.get("panels") or []
                kinds = [o.get("kind") for o in spec.get("overlays") or []] + [
                    o.get("kind") for p in panels for o in p.get("overlays") or []
                ]
                d.ctx.emit(
                    "design",
                    {
                        "styles": kinds,
                        "maps": len(panels) or 1,
                        "edit": bool(spec.get("replaces")),
                        "note": note,
                        "tries": len(errors) + 1,
                    },
                )
            if route.get("map") and out.get("map"):
                r = make_map(d.ctx, out["map"])
                if "map_id" in r["data"]:
                    maps.append({"id": r["data"]["map_id"], "spec": out["map"]})
            if route.get("chart") and out.get("chart"):
                r = make_chart(d.ctx, out["chart"])
                if r["data"].get("chart") == "sent":
                    charts.append(out["chart"])
            break
    upd: dict[str, Any] = {
        "maps": maps,
        "charts": charts,
        "usage": usage,
        "cartographer_done": True,
        "grounding": {**state.get("grounding", {}), "cartographer_errors": errors},
    }
    # an edit of a map on screen has no analyst answer: the note says what changed
    if not state.get("answer") and note and maps:
        upd["answer"] = note
        d.ctx.emit("text", {"delta": note})
    return upd
