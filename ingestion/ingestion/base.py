"""Pluggable data-source framework.

A new source = ONE adapter class implementing BaseSource + an @register decorator.
Nothing in this file or run.py changes when sources are added.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, ClassVar

from app.models import Site

from supabase import Client

RawRecord = dict[str, Any]


@dataclass(frozen=True)
class SourceMeta:
    name: str
    description: str
    cadence: str  # 'daily' | 'weekly' | 'monthly' | 'on_demand'
    requires_credentials: tuple[str, ...] = ()  # env var names; () if keyless
    phase: int = 1
    site_scoped: bool = True  # False for global sources like MaStR


@dataclass
class RunContext:
    """Everything an adapter run gets handed by the runner."""

    db: Client
    since: date | None = None
    until: date | None = None
    sites: list[Site] = field(default_factory=list)  # empty for non-site-scoped sources
    dry_run: bool = False


@dataclass
class LoadStats:
    fetched: int = 0
    loaded: int = 0
    skipped: int = 0

    def __str__(self) -> str:
        return f"fetched={self.fetched} loaded={self.loaded} skipped={self.skipped}"


class MissingCredentialsError(RuntimeError):
    pass


class BaseSource(ABC):
    """Adapter contract: fetch raw payloads -> transform to typed rows -> load (upsert)."""

    meta: ClassVar[SourceMeta]

    @abstractmethod
    def fetch(self, ctx: RunContext) -> Iterable[RawRecord]:
        """Pull raw data from the external source."""

    @abstractmethod
    def transform(self, raw: Iterable[RawRecord]) -> Iterable[Any]:
        """Map raw payloads to Pydantic domain models."""

    @abstractmethod
    def load(self, records: Iterable[Any], db: Client) -> LoadStats:
        """Upsert typed records into Supabase."""

    def check_credentials(self) -> None:
        missing = [var for var in self.meta.requires_credentials if not os.environ.get(var)]
        if missing:
            raise MissingCredentialsError(
                f"source '{self.meta.name}' needs env vars: {', '.join(missing)} "
                "(see .env.example / docs/SETUP.md)"
            )

    def run(self, ctx: RunContext) -> LoadStats:
        """Default orchestration. Adapters rarely need to override this."""
        self.check_credentials()
        raw = list(self.fetch(ctx))
        records = list(self.transform(raw))
        if ctx.dry_run:
            stats = LoadStats(fetched=len(raw), loaded=0, skipped=len(records))
        else:
            stats = self.load(records, ctx.db)
            stats.fetched = len(raw)
        return stats
