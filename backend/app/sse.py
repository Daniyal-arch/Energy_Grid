"""The graph's stream as Server-Sent Events (docs/AGENT.md section 6).

`graph.astream(..., stream_mode=["messages", "updates", "custom"])` becomes:
  text     {"delta": "..."}                 the analyst's words as they come
           {"reset": true, "reason": ...}   the grounding check asked for a rewrite: clear the text
  tool     {"name", "status": running|done|error, "args"?, "ms"?, "rows"?, "result_id"?}
  map      {"id", "spec"}                   a validated MapSpec (open with ?map=<id>)
  chart    {"spec", "rows"}
  sources  {"sources": [{dataset, table, licence, retrieved}]}
  done     {"trace_id", "answer", "grounding", "cost_usd", "latency_ms", "model", "maps"}
  error    {"message"}
and a comment line (": heartbeat") every 15 s so proxies keep the connection open.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

log = logging.getLogger(__name__)
HEARTBEAT_S = 15.0
_END = object()


def event(name: str, data: Any) -> str:
    return f"event: {name}\ndata: {json.dumps(data, default=str)}\n\n"


def chunk_text(msg: Any) -> str:
    c = getattr(msg, "content", "")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(
            b.get("text", "")
            for b in c
            if isinstance(b, dict) and b.get("type") in ("text", "text_delta")
        )
    return ""


async def graph_events(stream: AsyncIterator[tuple[str, Any]]) -> AsyncIterator[str]:
    """Map (mode, chunk) pairs to SSE strings; the final state's run gives sources and done."""
    async for mode, chunk in stream:
        if mode == "messages":
            msg, md = chunk
            # only the model's own words: the node's instructions to the model (a HumanMessage
            # it adds, e.g. at the time limit) also pass through this stream
            if md.get("langgraph_node") == "analyst" and getattr(msg, "type", "") in (
                "ai",
                "AIMessageChunk",
            ):
                text = chunk_text(msg)
                if text:
                    yield event("text", {"delta": text})
        elif mode == "custom":
            name, data = chunk.get("event"), chunk.get("data", {})
            if name == "text_reset":
                yield event("text", {"reset": True, **data})
            elif name == "text":
                yield event("text", data)
            elif name in ("tool", "map", "chart"):
                yield event(name, data)
        elif mode == "updates" and "finish" in chunk:
            run = chunk["finish"]["run"]
            yield event("sources", {"sources": run["sources"]})
            yield event(
                "done",
                {
                    "trace_id": run["trace_id"],
                    "answer": run.get("answer", ""),
                    "grounding": run["grounding"],
                    "cost_usd": run["cost_usd"],
                    "latency_ms": run["latency_ms"],
                    "model": run["model"],
                    "maps": run["maps"],
                    "stop": run["stop"],
                },
            )


async def with_heartbeat(
    source: AsyncIterator[str], every: float = HEARTBEAT_S
) -> AsyncIterator[str]:
    queue: asyncio.Queue[object] = asyncio.Queue()

    async def pump() -> None:
        try:
            async for item in source:
                await queue.put(item)
        except Exception as e:  # the stream says what failed; the log has the trace
            log.exception("agent stream failed")
            await queue.put(event("error", {"message": f"{type(e).__name__}: {str(e)[:300]}"}))
        finally:
            await queue.put(_END)

    task = asyncio.create_task(pump())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=every)
            except TimeoutError:
                yield ": heartbeat\n\n"
                continue
            if item is _END:
                break
            yield str(item)
    finally:
        task.cancel()
