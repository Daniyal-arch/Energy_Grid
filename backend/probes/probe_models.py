"""Probe: one streamed round trip with a tool call per provider whose key is set.

Records tool calling, streaming (chunks), usage with cached tokens, and the registry's price for
the model (agent/models.yaml, with its pricing page and date). Providers without a key are
listed as skipped; the scripted fake always runs.

    uv run python -m probes.probe_models
"""

from __future__ import annotations

import asyncio
import os
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from agent.models import Registry, chat_model, system_message
from app.settings import get_settings
from obs.cost import cost_usd, usage_of

CANDIDATES = [
    ("ANTHROPIC_API_KEY", "claude-haiku-5-5"),
    ("ANTHROPIC_API_KEY", "claude-opus-5-5"),
    ("OPENAI_API_KEY", "gpt-6-luna"),
    ("GOOGLE_API_KEY", "gemini-3.8-flash"),
    ("GROQ_API_KEY", "groq-gpt-oss-120b"),
    ("GROQ_API_KEY", "groq-gpt-oss-20b"),
    ("AWS_BEDROCK_PROBE_MODEL", "bedrock"),
    (None, "fake"),
]


@tool
def find_place(text: str) -> dict:
    """Resolve a place name to codes."""
    return {"places": [{"name": text, "codes": {"iso2": "NL"}}]}


async def probe(model_id: str) -> None:
    s = get_settings()
    reg = Registry(s.agent_dir / "models.yaml")
    entry = reg.resolve(
        os.environ["AWS_BEDROCK_PROBE_MODEL"] if model_id == "bedrock" else model_id
    )
    m = chat_model(entry, s, role="analyst", max_tokens=400).bind_tools([find_place])
    sys = system_message("You answer with tools. " * 400, entry)  # long enough to cache
    msgs = [sys, HumanMessage(content="Call find_place for 'Amsterdam', then stop.")]
    for attempt in (1, 2):  # the second call should read the cache
        t0 = time.perf_counter()
        chunks, first, final = 0, None, None
        async for ch in m.astream(msgs):
            chunks += 1
            first = first or time.perf_counter() - t0
            final = ch if final is None else final + ch
        u = usage_of(final)
        print(
            f"{entry.id} call {attempt}: chunks={chunks} first={first:.2f}s total={time.perf_counter() - t0:.2f}s "
            f"tool_calls={[tc['name'] for tc in final.tool_calls]} usage={u} "
            f"cost=${cost_usd(u, entry.prices)} price_source={entry.price_source!r}"
        )


async def main() -> None:
    for key, model_id in CANDIDATES:
        if key and not os.environ.get(key):
            print(f"{model_id}: skipped ({key} not set)")
            continue
        try:
            await probe(model_id)
        except Exception as e:  # report and go on
            print(f"{model_id}: FAILED {type(e).__name__}: {str(e)[:200]}")
    _ = SystemMessage


if __name__ == "__main__":
    asyncio.run(main())
