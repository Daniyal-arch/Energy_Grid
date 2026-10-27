"""finish: the answer's sources, cost and trace id; the run record on R2
(`agent/logs/<date>/<trace>.json`, no personal data, 90 days by an R2 lifecycle rule), CloudWatch
EMF metrics, the day's spend counter and the Langfuse grounding score."""

from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.runnables import RunnableConfig

from agent.deps import deps_of
from agent.limits import get_limits
from agent.state import AgentState
from obs import langfuse, metrics
from obs.tracing import span

log = logging.getLogger(__name__)


def sources_of(state: AgentState) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for t in state.get("tool_log", []):
        if t["name"] in (
            "search_catalog",
            "list_skills",
            "load_skill",
            "read_skill_file",
            "describe_table",
        ):
            continue
        for s in t["result"].get("sources", []):
            if s not in out:
                out.append(s)
    return out


async def finish(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    d = deps_of(config)
    s = d.settings
    with span("agent.node.finish"):
        usage = state.get("usage", [])
        cost = round(sum(u.get("cost_usd") or 0 for u in usage), 6)
        latency = round((time.time() - state["started"]) * 1000)
        g = state.get("grounding", {})
        run = {
            "trace_id": state.get("trace_id", ""),
            "date": time.strftime("%Y-%m-%d", time.gmtime()),
            "question": state["question"],
            "answer": state.get("answer", ""),
            "route": state.get("route", {}),
            "model": d.main_entry.id,
            "model_fast": d.fast_entry.id,
            "tool_calls": [
                {
                    "name": t["name"],
                    "args": t["args"],
                    "ms": t["ms"],
                    "error": t["error"],
                    "rows": (t["result"].get("data") or {}).get("row_count")
                    if isinstance(t["result"].get("data"), dict)
                    else None,
                }
                for t in state.get("tool_log", [])
            ],
            "sql": [t["sql"] for t in state.get("tool_log", []) if t.get("sql")],
            "usage": usage,
            "tokens": {
                k: sum(u.get(k, 0) for u in usage)
                for k in ("input", "output", "cache_read", "cache_write")
            },
            "cost_usd": cost,
            "latency_ms": latency,
            "grounding": {
                k: g.get(k) for k in ("numbers", "grounded", "ungrounded", "score") if k in g
            },
            "maps": [m["id"] for m in state.get("maps", [])],
            "stop": state.get("stop"),
            "sources": sources_of(state),
            "version": s.version,
        }
        if cost:
            try:
                get_limits(s).add_spend(cost)
            except Exception:
                log.exception("spend counter not updated")
        if s.run_records and run["trace_id"]:
            try:
                d.ctx.store.put_json(f"agent/logs/{run['date']}/{run['trace_id']}.json", run)
            except Exception:
                log.exception("run record not written")
        metrics.emit(
            d.main_entry.id,
            {
                "LatencyMs": latency,
                "InputTokens": run["tokens"]["input"],
                "OutputTokens": run["tokens"]["output"],
                "CachedTokens": run["tokens"]["cache_read"],
                "CostUSD": cost,
                "ToolCalls": len(run["tool_calls"]),
                "Errors": sum(1 for t in run["tool_calls"] if t["error"])
                + (1 if state.get("stop") == "refusal" else 0),
                "Ungrounded": len(g.get("ungrounded") or []),
            },
            route=str(state.get("route", {}).get("kind", "")),
        )
        if "score" in g and run["trace_id"]:
            langfuse.score(s, run["trace_id"], "grounding", float(g["score"]))
    return {"run": run}
