"""Probe: a trace for one question reaches Langfuse when its keys are set; otherwise the spans
print to the console (OTEL_CONSOLE) and are summarised here. Also writes the run record.

    uv run python -m probes.probe_tracing ["question"]
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter

os.environ.setdefault("AGENT_MODEL", "fake")
os.environ.setdefault("AGENT_MODEL_FAST", "fake")
os.environ.setdefault("LAKE_DB", "")

from agent.deps import build_deps  # noqa: E402
from agent.graph import GRAPH, initial_state  # noqa: E402
from app.settings import get_settings  # noqa: E402
from obs import langfuse, tracing  # noqa: E402


async def main(question: str) -> None:
    s = get_settings()
    tracing.setup_tracing(s, in_memory=True)
    d = build_deps(s)
    with tracing.span("probe.request") as sp:
        tid = tracing.current_trace_id()
        config = {
            "configurable": {"deps": d},
            "callbacks": langfuse.callbacks(s, tid),
            "metadata": langfuse.run_metadata("probe-session", [d.main_entry.id, s.version]),
        }
        out = await GRAPH.ainvoke(initial_state(question, trace_id=tid), config)
        sp.set_attribute("grounding", out["grounding"].get("score", -1))
    tracing.flush()
    langfuse.flush(s)
    spans = tracing.memory_exporter.get_finished_spans()
    print(f"trace {tid}: {len(spans)} spans")
    for name, n in sorted(Counter(sp.name for sp in spans).items()):
        print(f"  {n} x {name}")
    model = next(sp for sp in spans if sp.name == "agent.node.analyst")
    print("  model span:", {k: v for k, v in model.attributes.items() if k.startswith("gen_ai")})
    sql = next((sp for sp in spans if sp.name == "sql.query"), None)
    if sql:
        print("  sql span:", dict(sql.attributes))
    where = (
        "Langfuse " + s.langfuse_host
        if s.langfuse_configured
        else "console/in-memory (LANGFUSE_* not set)"
    )
    print("exported to:", where)
    rec = d.ctx.store.get_json(f"agent/logs/{out['run']['date']}/{tid}.json")
    print(
        "run record:",
        "R2" if s.r2_configured else s.local_store_dir,
        f"agent/logs/{out['run']['date']}/{tid}.json",
    )
    print("  keys:", sorted(rec))
    print(
        "  tool calls:",
        [(t["name"], t["rows"], t["ms"]) for t in rec["tool_calls"]],
        "cost",
        rec["cost_usd"],
        "latency_ms",
        rec["latency_ms"],
    )


if __name__ == "__main__":
    asyncio.run(
        main(sys.argv[1] if len(sys.argv) > 1 else "How much capacity per fuel does Spain have?")
    )
