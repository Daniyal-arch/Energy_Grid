"""SMARD (smard.de, Bundesnetzagentur) — German electricity generation by technology.

Free, no key. Two-step API (verified in scripts/probe_smard.py): an index of yearly
file timestamps, then a per-file daily [unix_ms, MWh] series (null = not yet published).
We store national daily generation per technology in `power_output` (plant_id =
'DE-<tech>', source = 'smard'). This is REGIONAL/national data — context and, for the
largest plants, a completion cross-check; per-unit confirmation needs ENTSO-E.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta

import httpx
from app.models import PowerOutput

from ingestion.base import BaseSource, LoadStats, RawRecord, RunContext, SourceMeta
from ingestion.registry import register
from supabase import Client

BASE = "https://www.smard.de/app/chart_data"
REGION = "DE"
RES = "day"
UA = {"User-Agent": "Mozilla/5.0"}

# SMARD generation filter IDs -> our technology labels
FILTERS = {
    "4068": "solar",
    "4067": "wind_onshore",
    "1225": "wind_offshore",
    "4066": "biomass",
    "1226": "hydro",
}


def _to_date(ms: int) -> date:
    # daily buckets sit at German midnight; +12h lands squarely in the right calendar day
    return datetime.fromtimestamp(ms / 1000 + 43200, tz=UTC).date()


@register
class SmardSource(BaseSource):
    meta = SourceMeta(
        name="smard",
        description="German national generation by technology (daily MWh) -> power_output",
        cadence="daily",
        requires_credentials=(),
        phase=2,
        site_scoped=False,
    )

    def fetch(self, ctx: RunContext) -> Iterable[RawRecord]:
        since = ctx.since or (date.today() - timedelta(days=60))
        until = ctx.until or date.today()
        since_ms = int(datetime(since.year, since.month, since.day, tzinfo=UTC).timestamp() * 1000)
        with httpx.Client(timeout=30, headers=UA) as c:
            for smard_id, label in FILTERS.items():
                idx = c.get(f"{BASE}/{smard_id}/{REGION}/index_{RES}.json")
                idx.raise_for_status()
                for file_ts in idx.json().get("timestamps", []):
                    # each file covers ~1 year; skip files that can't reach `since`
                    if file_ts + 366 * 86_400_000 < since_ms:
                        continue
                    data = c.get(
                        f"{BASE}/{smard_id}/{REGION}/{smard_id}_{REGION}_{RES}_{file_ts}.json"
                    )
                    if data.status_code != 200:
                        continue
                    for ms, value in data.json().get("series", []):
                        if value is None:
                            continue
                        d = _to_date(ms)
                        if since <= d <= until:
                            yield {"label": label, "date": d, "mwh": float(value)}

    def transform(self, raw: Iterable[RawRecord]) -> Iterable[PowerOutput]:
        for rec in raw:
            yield PowerOutput(
                plant_id=f"DE-{rec['label']}",
                site_id=None,
                date=rec["date"],
                mwh=round(rec["mwh"], 1),
                source="smard",
            )

    def load(self, records: Iterable[PowerOutput], db: Client) -> LoadStats:
        rows = [r.model_dump(mode="json", exclude_none=True) for r in records]
        for i in range(0, len(rows), 500):
            db.table("power_output").upsert(
                rows[i : i + 500], on_conflict="plant_id,date,source"
            ).execute()
        return LoadStats(loaded=len(rows))
