"""POST /api/ask: the agent, streamed as Server-Sent Events (app/sse.py)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from opentelemetry import context as otel_context
from pydantic import BaseModel, Field

from agent.deps import build_deps
from agent.graph import GRAPH, initial_state
from agent.limits import get_limits, hash_ip
from agent.models import ModelError
from app.deps import settings
from app.sse import event, graph_events, with_heartbeat
from mcp_server.client import external_tools
from obs import langfuse
from obs.tracing import current_trace_id, flush, tracer

router = APIRouter()


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=8000)


class AskRequest(BaseModel):
    question: str = Field(max_length=4000)
    history: list[Turn] = Field(default_factory=list, max_length=40)
    view: dict[str, Any] | None = None
    conversation_id: str | None = Field(default=None, max_length=80)
    model: str | None = None


def client_ip(request: Request) -> str:
    h = request.headers
    return (
        h.get("cf-connecting-ip")
        or (h.get("x-forwarded-for") or "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )


@router.post("/api/ask")
async def ask(body: AskRequest, request: Request) -> StreamingResponse:
    s = settings()
    if not get_limits(s).take(hash_ip(client_ip(request), s.ip_hash_salt)):
        raise HTTPException(429, "too many questions from this address; try again later")
    try:
        deps = build_deps(s, model=body.model)
    except ModelError as e:
        raise HTTPException(400, str(e)) from e
    deps.extra_tools = await external_tools(s)
    parent = otel_context.get_current()

    async def stream() -> AsyncIterator[str]:
        with tracer().start_as_current_span("agent.ask", context=parent) as sp:
            tid = current_trace_id()
            sp.set_attribute("gen_ai.request.model", deps.main_entry.model)
            state = initial_state(
                body.question,
                history=[t.model_dump() for t in body.history],
                view=body.view,
                conversation_id=body.conversation_id,
                trace_id=tid,
            )
            config = {
                "configurable": {"deps": deps},
                "callbacks": langfuse.callbacks(s, tid),
                "metadata": langfuse.run_metadata(
                    body.conversation_id, [deps.main_entry.id, s.version]
                ),
                "recursion_limit": 60,
            }
            try:
                async for item in graph_events(
                    GRAPH.astream(state, config, stream_mode=["messages", "updates", "custom"])
                ):
                    yield item
            except Exception as e:
                yield event(
                    "error", {"message": f"{type(e).__name__}: {str(e)[:300]}", "trace_id": tid}
                )
        flush()
        langfuse.flush(s)

    return StreamingResponse(
        with_heartbeat(stream()),
        media_type="text/event-stream",
        headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
    )
