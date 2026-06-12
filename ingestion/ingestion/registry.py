"""Source registry. Adapters self-register via the @register decorator."""

from __future__ import annotations

from ingestion.base import BaseSource

_REGISTRY: dict[str, type[BaseSource]] = {}


def register(cls: type[BaseSource]) -> type[BaseSource]:
    name = cls.meta.name
    if name in _REGISTRY:
        raise ValueError(f"duplicate source name: {name!r}")
    _REGISTRY[name] = cls
    return cls


def get_source(name: str) -> BaseSource:
    try:
        return _REGISTRY[name]()
    except KeyError:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(f"unknown source {name!r}; available: {available}") from None


def list_sources() -> list[type[BaseSource]]:
    return [_REGISTRY[name] for name in sorted(_REGISTRY)]
