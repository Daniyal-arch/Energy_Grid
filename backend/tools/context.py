"""What every tool needs: settings, the lake, the catalogue, the gazetteer, the result store,
the object store and an event writer (the graph's custom stream; a no-op elsewhere)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from app.settings import Settings
from data.areas import Areas, AreaStore
from data.duck import Lake, get_lake
from data.gazetteer import Gazetteer
from data.r2 import Store, get_store
from tools.catalog import Catalogue
from tools.results import ResultStore

Emit = Callable[[str, dict[str, Any]], None]


@dataclass
class ToolContext:
    settings: Settings
    emit: Emit = field(default=lambda _e, _d: None)
    # the browser's view (countries, drawn area, camera) for "here" and "what I drew"
    view: dict[str, Any] | None = None
    # the areas resolved in this request, registered in every run_sql (brief 27 A2)
    turn_areas: list[str] = field(default_factory=list)

    @cached_property
    def lake(self) -> Lake:
        return get_lake(self.settings)

    @cached_property
    def catalogue(self) -> Catalogue:
        return get_catalogue(self.settings)

    @cached_property
    def gazetteer(self) -> Gazetteer:
        return get_gazetteer(self.settings)

    @cached_property
    def results(self) -> ResultStore:
        return ResultStore(self.settings.results_dir)

    @cached_property
    def store(self) -> Store:
        return get_store(self.settings)

    @cached_property
    def area_store(self) -> AreaStore:
        return AreaStore(self.settings.results_dir, self.store)

    @cached_property
    def areas(self) -> Areas:
        return Areas(self.lake, self.gazetteer, self.settings.agent_dir, self.area_store)


_catalogues: dict[str, Catalogue] = {}
_gazetteers: dict[str, Gazetteer] = {}


def get_catalogue(s: Settings) -> Catalogue:
    key = str(s.atlas_root)
    if key not in _catalogues:
        _catalogues[key] = Catalogue(
            s.agent_dir, s.atlas_root / "frontend" / "src" / "app" / "datasets.json"
        )
    return _catalogues[key]


def get_gazetteer(s: Settings) -> Gazetteer:
    key = str(s.public_dir)
    if key not in _gazetteers:
        _gazetteers[key] = Gazetteer(s.public_dir)
    return _gazetteers[key]


def result(
    data: Any, sources: list[dict[str, str]], result_id: str | None = None
) -> dict[str, Any]:
    """The shape of every tool result."""
    out: dict[str, Any] = {"data": data, "sources": sources}
    if result_id:
        out["result_id"] = result_id
    return out
