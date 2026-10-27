"""Per-request dependencies of the graph, passed in `config["configurable"]["deps"]`."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from agent.mapspec import MapSpec
from agent.models import ModelEntry, ModelError, Registry, chat_model
from agent.skills import Skills, get_skills
from app.settings import Settings
from tools.context import ToolContext
from tools.registry import langchain_tools

PROMPTS = Path(__file__).resolve().parent / "prompts"


@lru_cache
def _read(name: str) -> str:
    return (PROMPTS / name).read_text()


def prompt(name: str, **values: str) -> str:
    """A prompt file with its {placeholders} filled (other braces, as in JSON, stay)."""
    text = _read(name)
    for k, v in values.items():
        text = text.replace("{" + k + "}", v)
    return text


@dataclass
class Deps:
    settings: Settings
    ctx: ToolContext
    main_entry: ModelEntry
    fast_entry: ModelEntry
    main: BaseChatModel
    fast: BaseChatModel
    tools: list[BaseTool]
    skills: Skills
    extra_tools: list[BaseTool] = field(default_factory=list)

    @property
    def all_tools(self) -> list[BaseTool]:
        return sorted([*self.tools, *self.extra_tools], key=lambda t: t.name)

    def system_text(self) -> str:
        return _system_text(
            str(self.settings.atlas_root),
            self.skills.index_text(),
            tuple(self.ctx.catalogue.dataset_list()),
        )


@lru_cache(maxsize=4)
def _system_text(_root: str, skills: str, datasets: tuple[tuple[str, str], ...]) -> str:
    ds = "\n".join(f"- {n}: {t}" for n, t in datasets)
    schema = json.dumps(MapSpec.model_json_schema(), separators=(",", ":"))
    return prompt("system.md", datasets=ds, skills=skills, mapspec=schema)


@lru_cache
def registry(path: str) -> Registry:
    return Registry(Path(path))


def build_deps(
    settings: Settings, *, model: str | None = None, ctx: ToolContext | None = None
) -> Deps:
    reg = registry(str(settings.agent_dir / "models.yaml"))
    main_name = model or settings.agent_model
    if (
        model
        and model not in settings.models_allowed()
        and reg.resolve(model).id not in settings.models_allowed()
    ):
        raise ModelError(f"model {model!r} is not in AGENT_MODELS_ALLOWED")
    main_entry = reg.resolve(main_name)
    fast_entry = reg.resolve(
        settings.agent_model_fast if main_entry.provider != "fake" else main_name
    )
    ctx = ctx or ToolContext(settings)
    return Deps(
        settings=settings,
        ctx=ctx,
        main_entry=main_entry,
        fast_entry=fast_entry,
        main=chat_model(
            main_entry, settings, role="analyst", max_tokens=settings.max_output_tokens
        ),
        fast=chat_model(fast_entry, settings, role="router", max_tokens=2000),
        tools=langchain_tools(ctx),
        skills=get_skills(settings.agent_dir),
    )


def deps_of(config: RunnableConfig) -> Deps:
    return config["configurable"]["deps"]
