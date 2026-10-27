"""The graph's state for one request (stateless between requests: the browser sends the
conversation, trimmed)."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    question: str
    history: list[dict[str, str]]
    view: dict[str, Any] | None
    conversation_id: str | None
    trace_id: str
    started: float
    messages: Annotated[list[AnyMessage], add_messages]
    route: dict[str, Any]
    tool_calls: int
    tool_log: Annotated[list[dict[str, Any]], operator.add]
    result_ids: Annotated[list[str], operator.add]
    usage: Annotated[list[dict[str, Any]], operator.add]
    maps: Annotated[list[dict[str, Any]], operator.add]
    charts: Annotated[list[dict[str, Any]], operator.add]
    answer: str
    grounding: dict[str, Any]
    repaired: bool
    stop: str | None
    cartographer_done: bool
    run: dict[str, Any]
