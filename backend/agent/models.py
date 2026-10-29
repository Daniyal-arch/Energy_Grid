"""Any chat model by configuration; provider details live only here.

- The registry `agent/models.yaml`: prices, context, tool calling, caching kind, effort.
- `chat_model()` builds the model with `init_chat_model("<provider>:<model>")` (the scripted
  fake for `fake:*`). Anthropic: effort through `output_config`, no sampling parameters (the
  current models refuse them). OpenAI and Google cache prompt prefixes by themselves.
- `system_message()` puts the cache breakpoint after the tools and the frozen system prompt
  (Anthropic renders tools, then system, so one breakpoint on the system block covers both).
- `stop_reason()` normalises refusals and length stops across providers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage


class ModelError(ValueError):
    pass


@dataclass
class ModelEntry:
    id: str
    model: str
    prices: dict[str, float] = field(default_factory=dict)
    price_source: str = ""
    context: int | None = None
    tool_calling: bool = True
    caching: str = "none"
    effort: str | None = None
    temperature: float | None = None
    role: str = "main"

    @property
    def provider(self) -> str:
        return self.model.split(":", 1)[0]


class Registry:
    def __init__(self, path: Path) -> None:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {"models": []}
        self.entries = [ModelEntry(**m) for m in raw.get("models", [])]

    def resolve(self, name: str) -> ModelEntry:
        """An entry by id or `provider:model`; an unlisted `provider:model` gets no prices."""
        for e in self.entries:
            if name in (e.id, e.model):
                return e
        if ":" not in name:
            raise ModelError(f"unknown model {name!r}; add it to agent/models.yaml")
        return ModelEntry(id=name, model=name)


def chat_model(entry: ModelEntry, settings: Any, *, role: str, max_tokens: int) -> BaseChatModel:
    if not entry.tool_calling:
        raise ModelError(f"model {entry.id} has no tool calling; the agent needs it")
    provider, name = entry.model.split(":", 1)
    if provider == "fake":
        from agent.fake import FakeChatModel

        return FakeChatModel(role=role, variant=name)
    from langchain.chat_models import init_chat_model

    kwargs: dict[str, Any] = {}
    if provider == "anthropic":
        kwargs["max_tokens"] = max_tokens
        if settings.anthropic_api_key:
            kwargs["api_key"] = settings.anthropic_api_key
        if entry.effort:
            kwargs["output_config"] = {"effort": entry.effort}
    elif provider == "openai":
        kwargs["max_tokens"] = max_tokens
        if settings.openai_api_key:
            kwargs["api_key"] = settings.openai_api_key
        if entry.effort:
            kwargs["reasoning_effort"] = entry.effort
    elif provider == "google_genai":
        kwargs["max_output_tokens"] = max_tokens
        if settings.google_api_key:
            kwargs["google_api_key"] = settings.google_api_key
    elif provider == "groq":
        kwargs["max_tokens"] = max_tokens
        if settings.groq_api_key:
            kwargs["api_key"] = settings.groq_api_key
    elif provider in ("bedrock_converse", "bedrock"):
        kwargs["max_tokens"] = max_tokens
        kwargs["region_name"] = settings.aws_region
        # a Bedrock API key instead of IAM credentials (boto3 reads this variable)
        if settings.bedrock_api_key and not os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = settings.bedrock_api_key
    elif provider == "ollama":
        kwargs["num_predict"] = max_tokens
    if entry.temperature is not None:
        kwargs["temperature"] = entry.temperature
    try:
        return init_chat_model(entry.model, **kwargs)
    except ImportError as e:
        raise ModelError(f"provider {provider} is not installed (uv sync --extra ...): {e}") from e


def system_message(text: str, entry: ModelEntry) -> SystemMessage:
    if entry.caching == "anthropic_breakpoints":
        return SystemMessage(
            content=[{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]
        )
    return SystemMessage(content=text)


def text_of(message: AIMessage) -> str:
    """The visible text of a reply (thinking and tool-use blocks left out)."""
    c = message.content
    if isinstance(c, str):
        return c
    return "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")


def stop_reason(message: AIMessage) -> str:
    """'refusal', 'length', 'tool_use' or 'end' for every provider."""
    md = message.response_metadata or {}
    raw = str(
        md.get("stop_reason") or md.get("finish_reason") or md.get("done_reason") or ""
    ).lower()
    if raw in (
        "refusal",
        "content_filter",
        "safety",
        "blocklist",
        "prohibited_content",
        "recitation",
    ):
        return "refusal"
    if raw in ("max_tokens", "length", "max_output_tokens"):
        return "length"
    if message.tool_calls:
        return "tool_use"
    return "end"
