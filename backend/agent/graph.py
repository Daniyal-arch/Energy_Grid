"""The agent graph (LangGraph StateGraph):

    START -> guard -> router -> analyst <-> tools -> [cartographer] -> grounding -> finish -> END
                                   ^                                     |
                                   +--------- one repair round ----------+

guard: input size and the daily spend cap; router: the fast model picks the kind of answer;
analyst: the main model with tools and skills (at most 12 tool calls); cartographer: the fast
model builds the MapSpec from result ids, only when a map or chart is asked; grounding: every
number in the answer is in this turn's tool results (one repair round by the analyst, then
unfound numbers are marked); finish: sources, cost, trace id, the run record and metrics.
"""

from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from agent import grounding as gr
from agent.analyst import analyst, tools_node, wants_tools
from agent.cartographer import cartographer, needs_cartographer, view_maps
from agent.deps import deps_of
from agent.limits import get_limits
from agent.router import router
from agent.runs import finish
from agent.state import AgentState
from obs.tracing import span


async def guard(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    d = deps_of(config)
    s = d.settings
    with span("agent.node.guard"):
        q = state["question"].strip()
        if not q:
            return {"stop": "empty", "answer": "Ask a question about the power system."}
        if len(q) > s.max_question_chars:
            return {
                "stop": "too_long",
                "answer": f"The question is longer than {s.max_question_chars} characters.",
            }
        if get_limits(s).spent_today() >= s.daily_spend_cap_usd:
            return {
                "stop": "budget",
                "answer": "Today's budget for questions is used. Please try again tomorrow (UTC).",
            }
        history = (state.get("history") or [])[-s.max_history_messages :]
        return {"question": q, "history": history, "tool_calls": 0, "repaired": False}


def after_guard(state: AgentState) -> str:
    return "finish" if state.get("stop") else "router"


def after_router(state: AgentState) -> str:
    """An edit of the map on screen goes straight to the cartographer (no new data)."""
    if (state.get("route") or {}).get("edit") and view_maps(state):
        return "cartographer"
    return "analyst"


def after_analyst(state: AgentState, config: RunnableConfig) -> str:
    if wants_tools(state, deps_of(config).settings.max_tool_calls):
        return "tools"
    if needs_cartographer(state):
        return "cartographer"
    return "grounding"


async def grounding(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    with span("agent.node.grounding") as sp:
        if state.get("stop"):
            return {"grounding": {**state.get("grounding", {}), "skipped": state["stop"]}}
        result = gr.check(
            state.get("answer", ""), gr.tool_payloads(state.get("tool_log", [])), state["question"]
        )
        sp.set_attribute("grounding.score", result["score"])
        prev = state.get("grounding", {})
        if result["ungrounded"] and not state.get("repaired"):
            get_stream_writer()(
                {
                    "event": "text_reset",
                    "data": {"reason": "grounding", "ungrounded": result["ungrounded"]},
                }
            )
            note = (
                "These numbers in your answer are not in this turn's tool results: "
                + ", ".join(result["ungrounded"])
                + ". Rewrite the answer using only numbers from the tool results (call a tool if "
                "a figure is needed), "
                "or leave the figure out."
            )
            return {
                "messages": [HumanMessage(content=note)],
                "repaired": True,
                "grounding": {**prev, "first_pass": result},
            }
        answer = state.get("answer", "")
        if result["ungrounded"]:
            answer += (
                "\n\n(Not found in the tool results, unverified: "
                + ", ".join(result["ungrounded"])
                + ")"
            )
        return {"answer": answer, "grounding": {**prev, **result}}


def after_grounding(state: AgentState) -> str:
    g = state.get("grounding", {})
    if "first_pass" in g and "score" not in g:
        return "analyst"
    return "finish"


def build_graph() -> Any:
    g = StateGraph(AgentState)
    g.add_node("guard", guard)
    g.add_node("router", router)
    g.add_node("analyst", analyst)
    g.add_node("tools", tools_node)
    g.add_node("cartographer", cartographer)
    g.add_node("grounding", grounding)
    g.add_node("finish", finish)
    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", after_guard, ["router", "finish"])
    g.add_conditional_edges("router", after_router, ["analyst", "cartographer"])
    g.add_conditional_edges("analyst", after_analyst, ["tools", "cartographer", "grounding"])
    g.add_edge("tools", "analyst")
    g.add_edge("cartographer", "grounding")
    g.add_conditional_edges("grounding", after_grounding, ["analyst", "finish"])
    g.add_edge("finish", END)
    return g.compile()


GRAPH = build_graph()


def initial_state(
    question: str,
    *,
    history: list[dict[str, str]] | None = None,
    view: dict[str, Any] | None = None,
    conversation_id: str | None = None,
    trace_id: str = "",
) -> AgentState:
    return {
        "question": question,
        "history": history or [],
        "view": view,
        "conversation_id": conversation_id,
        "trace_id": trace_id,
        "started": time.time(),
        "messages": [],
        "tool_log": [],
        "result_ids": [],
        "usage": [],
        "maps": [],
        "charts": [],
        "grounding": {},
    }
