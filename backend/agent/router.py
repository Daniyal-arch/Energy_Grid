"""The router: the fast model names the kind of answer and the specialists it needs."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agent.deps import deps_of, prompt
from agent.models import text_of
from agent.state import AgentState
from agent.usage import record
from obs.tracing import span

MAP_WORDS = re.compile(r"\b(map|show|where|draw|shade|plot)\b", re.I)
CHART_WORDS = re.compile(r"\b(chart|trend|over time|time series|by month|by year)\b", re.I)


def heuristic(question: str) -> dict[str, Any]:
    m = bool(MAP_WORDS.search(question))
    return {
        "kind": "map" if m else "answer",
        "map": m,
        "chart": bool(CHART_WORDS.search(question)),
        "skills": [],
    }


def parse(text: str, question: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    try:
        route = json.loads(text[start : end + 1])
        if not isinstance(route, dict):
            raise ValueError
    except ValueError:
        return {**heuristic(question), "parsed": False}
    base = heuristic(question)
    return {
        "kind": str(route.get("kind", base["kind"])),
        "map": bool(route.get("map", base["map"])),
        "chart": bool(route.get("chart", base["chart"])),
        "skills": [str(s) for s in route.get("skills", [])][:2],
        "parsed": True,
    }


async def router(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    d = deps_of(config)
    q = state["question"]
    sys = prompt("router.md", skills=d.skills.index_text())
    t0 = time.perf_counter()
    with span("agent.node.router"):
        try:
            resp = await d.fast.ainvoke(
                [SystemMessage(content=sys), HumanMessage(content=f"Question: {q}")], config
            )
        except Exception:
            return {"route": {**heuristic(q), "parsed": False, "error": "router model failed"}}
    route = parse(text_of(resp), q)
    route["skills"] = [s for s in route["skills"] if s in d.skills.skills]
    return {
        "route": route,
        "usage": [record("router", d.fast_entry, resp, time.perf_counter() - t0)],
    }
