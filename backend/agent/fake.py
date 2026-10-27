"""A scripted tool-calling chat model for tests, local runs and the done-check (no network).

`FakeChatModel()` plays the router, the analyst or the cartographer (told apart by the system
prompt) with a small
deterministic policy over the app tables, so the whole graph runs end to end: the analyst calls
search_catalog, then run_sql, then answers with numbers taken from the query result (so the
grounding check passes). `script=[...]` replays fixed replies instead (unit tests).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field

COUNTRIES = {
    "germany": "DE",
    "france": "FR",
    "spain": "ES",
    "italy": "IT",
    "poland": "PL",
    "netherlands": "NL",
    "belgium": "BE",
    "austria": "AT",
    "sweden": "SE",
    "norway": "NO",
    "finland": "FI",
    "denmark": "DK",
    "portugal": "PT",
    "greece": "GR",
    "czechia": "CZ",
    "romania": "RO",
    "united kingdom": "GB",
    "britain": "GB",
}
MAP_WORDS = ("map", "show", "where", "draw")


def _text(m: BaseMessage) -> str:
    c = m.content
    if isinstance(c, str):
        return c
    return " ".join(b.get("text", "") for b in c if isinstance(b, dict))


def _question(messages: Sequence[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            t = _text(m)
            return t.split("Question:", 1)[-1].strip()
    return ""


def _country(q: str) -> str:
    ql = q.lower()
    for name, code in COUNTRIES.items():
        if name in ql:
            return code
    m = re.search(r"\b([A-Z]{2})\b", q)
    return m.group(1) if m else "DE"


def _fmt(v: Any) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return f"{v:,}" if isinstance(v, int | float) else str(v)


class FakeChatModel(BaseChatModel):
    role: str = "analyst"
    variant: str = "scripted"
    script: list[AIMessage] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake-scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> FakeChatModel:  # type: ignore[override]
        return self

    # ------------------------------------------------------------------ policy
    def _reply(self, messages: list[BaseMessage]) -> AIMessage:
        if self.script:
            return self.script.pop(0)
        q = _question(messages)
        system = _text(messages[0]) if messages and messages[0].type == "system" else ""
        role = (
            "router"
            if system.startswith("You route")
            else "cartographer"
            if system.startswith("You build one MapSpec")
            else self.role
        )
        if role == "router":
            wants_map = any(w in q.lower() for w in MAP_WORDS)
            route = {
                "kind": "map" if wants_map else "answer",
                "map": wants_map,
                "chart": "chart" in q.lower(),
                "skills": ["prices"] if "price" in q.lower() else [],
            }
            return AIMessage(content=json.dumps(route))
        if role == "cartographer":
            return AIMessage(content=json.dumps(self._map(messages)))
        return self._analyst(messages, q)

    def _analyst(self, messages: list[BaseMessage], q: str) -> AIMessage:
        tools_done = [m for m in messages if isinstance(m, ToolMessage) and m.name != "load_skill"]
        ql = q.lower()
        hint = next(
            (
                _text(m)
                for m in messages
                if isinstance(m, HumanMessage) and "Skills that fit this question:" in _text(m)
            ),
            "",
        )
        if hint and not any(
            isinstance(m, ToolMessage) and m.name == "load_skill" for m in messages
        ):
            name = (
                hint.split("Skills that fit this question:", 1)[1]
                .split("\n")[0]
                .split(",")[0]
                .strip()
            )
            return AIMessage(
                content="",
                tool_calls=[{"name": "load_skill", "args": {"name": name}, "id": "call_0"}],
            )
        if not tools_done:
            return AIMessage(
                content="",
                tool_calls=[{"name": "search_catalog", "args": {"query": q[:200]}, "id": "call_1"}],
            )
        if len(tools_done) == 1:
            if "price" in ql or "negative" in ql:
                sql = (
                    "SELECT zone, country, mean_eur_mwh, negative_hours FROM app.eu_prices "
                    "ORDER BY negative_hours DESC LIMIT 5"
                )
            elif any(w in ql for w in MAP_WORDS):
                sql = (
                    "SELECT name, fuel, mw, lon, lat FROM app.eu_plants "
                    f"WHERE country = '{_country(q)}' ORDER BY mw DESC LIMIT 200"
                )
            else:
                sql = (
                    "SELECT fuel, round(sum(mw)) AS mw, count(*) AS plants FROM app.eu_plants "
                    f"WHERE country = '{_country(q)}' GROUP BY fuel ORDER BY mw DESC"
                )
            return AIMessage(
                content="", tool_calls=[{"name": "run_sql", "args": {"sql": sql}, "id": "call_2"}]
            )
        last = tools_done[-1]
        body = _text(last)
        payload = json.loads(body[body.find("{") : body.rfind("}") + 1])
        data = payload.get("data", {})
        cols, rows = data.get("columns", []), data.get("rows", [])
        src = "; ".join(s.get("retrieved", "") for s in payload.get("sources", []))
        lines = [
            ", ".join(f"{c} {_fmt(v)}" for c, v in zip(cols, r, strict=False)) for r in rows[:3]
        ]
        text = "From the query result: " + "; ".join(lines) + f". Source: {src}."
        return AIMessage(content=text)

    def _map(self, messages: list[BaseMessage]) -> dict[str, Any]:
        body = _text(messages[-1])
        results = json.loads(body[body.find("RESULTS:") + 8 :].strip().split("\n\n")[0])
        r = results[-1]
        cols = r["columns"]
        src = "; ".join(s.get("retrieved", "") for s in r.get("sources", [])) or "query result"
        if "lon" in cols and "lat" in cols:
            size = next((c for c in ("mw", "value") if c in cols), None)
            overlay: dict[str, Any] = {
                "id": "result",
                "kind": "points",
                "data": {"result_id": r["result_id"], "lon": "lon", "lat": "lat"},
                "legend": {"title": "Query result", "how": "rows of the query, as returned"},
                "tooltip": [c for c in cols if c not in ("lon", "lat")][:4],
                "source": src,
            }
            if size:
                overlay["size"] = {"column": size, "unit": "MW", "max_px": 18}
            if "fuel" in cols:
                overlay["value"] = {
                    "column": "fuel",
                    "unit": "fuel",
                    "scale": "categorical",
                    "palette": "fuel",
                }
        else:
            key = next((c for c in ("country", "zone") if c in cols), cols[0])
            val = next((c for c in cols if c not in (key, "zone", "country")), cols[-1])
            overlay = {
                "id": "result",
                "kind": "choropleth",
                "data": {
                    "result_id": r["result_id"],
                    "key": key,
                    "shapes": "countries" if key == "country" else "bidding_zones",
                },
                "value": {
                    "column": val,
                    "unit": "as in the result",
                    "scale": "sequential",
                    "palette": "neutral",
                },
                "legend": {"title": val, "how": "as returned by the query"},
                "tooltip": [key, val],
                "source": src,
            }
        return {
            "map": {"title": "Answer", "camera": {"preset": "europe"}, "overlays": [overlay]},
            "chart": None,
        }

    # ------------------------------------------------------------------ chat model API
    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        msg = self._reply(messages)
        msg.usage_metadata = msg.usage_metadata or {
            "input_tokens": 100 * len(messages),
            "output_tokens": 20,
            "total_tokens": 100 * len(messages) + 20,
        }
        msg.response_metadata = msg.response_metadata or {
            "stop_reason": "tool_use" if msg.tool_calls else "end_turn",
            "model_name": "fake",
        }
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        msg = self._generate(messages).generations[0].message
        assert isinstance(msg, AIMessage)
        if msg.tool_calls:
            chunk = AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {"name": tc["name"], "args": json.dumps(tc["args"]), "id": tc["id"], "index": i}
                    for i, tc in enumerate(msg.tool_calls)
                ],
                usage_metadata=msg.usage_metadata,
                response_metadata=msg.response_metadata,
            )
            yield ChatGenerationChunk(message=chunk)
            return
        text = msg.content if isinstance(msg.content, str) else _text(msg)
        words = re.findall(r"\S+\s*", text) or [""]
        for i, w in enumerate(words):
            last = i == len(words) - 1
            chunk = AIMessageChunk(
                content=w,
                usage_metadata=msg.usage_metadata if last else None,
                response_metadata=msg.response_metadata if last else {},
            )
            if run_manager:
                run_manager.on_llm_new_token(w, chunk=ChatGenerationChunk(message=chunk))
            yield ChatGenerationChunk(message=chunk)
