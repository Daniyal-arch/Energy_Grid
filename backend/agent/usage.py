"""Usage and cost of one model call, with its GenAI span attributes."""

from __future__ import annotations

from typing import Any

from opentelemetry import trace

from agent.models import ModelEntry
from obs.cost import cost_usd, usage_of


def record(node: str, entry: ModelEntry, message: Any, seconds: float) -> dict[str, Any]:
    u = usage_of(message)
    cost = cost_usd(u, entry.prices)
    sp = trace.get_current_span()
    attrs = {
        "gen_ai.system": entry.provider,
        "gen_ai.request.model": entry.model,
        "gen_ai.usage.input_tokens": u["input"],
        "gen_ai.usage.output_tokens": u["output"],
        "gen_ai.usage.cache_read_input_tokens": u["cache_read"],
        "gen_ai.usage.cache_creation_input_tokens": u["cache_write"],
        "gen_ai.cost_usd": cost or 0.0,
    }
    for k, v in attrs.items():
        sp.set_attribute(k, v)
    return {"node": node, "model": entry.id, **u, "cost_usd": cost, "ms": round(seconds * 1000, 1)}
