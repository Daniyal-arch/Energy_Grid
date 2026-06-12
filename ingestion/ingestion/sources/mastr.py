"""Marktstammdatenregister via the open-mastr package.

STATUS: probe stage. Per project convention (CLAUDE.md rule 3), run
`uv run python scripts/probe_mastr.py` first to verify the open-mastr bulk download,
table/column names, and BW/BY ground-mounted-solar filters — then implement
fetch/transform/load here against the verified schema.

Planned flow:
  1. open-mastr bulk download (solar) into local SQLite.
  2. Filter: ground-mounted (Freifläche), net capacity >= 5 MW, Bundesland in (BW, BY).
  3. AOI polygon: match against OSM landuse=solar near the MaStR coordinates;
     fallback: capacity-based square buffer (~1.4 ha per MW) around the point.
  4. Upsert into `sites` (on_conflict=mastr_id).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ingestion.base import BaseSource, LoadStats, RawRecord, RunContext, SourceMeta
from ingestion.registry import register
from supabase import Client


@register
class MaStRSource(BaseSource):
    meta = SourceMeta(
        name="mastr",
        description="German registry of energy units (ground-mounted solar >=5 MW, BW+BY) -> sites",
        cadence="monthly",
        requires_credentials=(),
        phase=1,
        site_scoped=False,
    )

    def fetch(self, ctx: RunContext) -> Iterable[RawRecord]:
        raise NotImplementedError(
            "mastr adapter is in probe stage - run `uv run python scripts/probe_mastr.py` "
            "and review its output first (CLAUDE.md rule 3)."
        )

    def transform(self, raw: Iterable[RawRecord]) -> Iterable[Any]:
        raise NotImplementedError

    def load(self, records: Iterable[Any], db: Client) -> LoadStats:
        raise NotImplementedError
