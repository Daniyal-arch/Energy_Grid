"""DWD weather via Bright Sky (https://brightsky.dev). Free JSON API, no key.

Fetches hourly weather per site centroid and aggregates to daily rows in `weather`:
rain_mm (sum of precipitation), temp_c (mean), snow (any hour reports snow icon/condition).
Used by the detection pipeline to mask false alarms on snow/frozen days.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any

import httpx
from app.models import WeatherDay

from ingestion.base import BaseSource, LoadStats, RawRecord, RunContext, SourceMeta
from ingestion.registry import register
from supabase import Client

API_URL = "https://api.brightsky.dev/weather"
SNOW_MARKERS = ("snow", "sleet", "hail")


@register
class BrightSkySource(BaseSource):
    meta = SourceMeta(
        name="brightsky",
        description="Daily DWD weather per site (rain, snow, temperature) for observation masking",
        cadence="daily",
        requires_credentials=(),
        phase=1,
        site_scoped=True,
    )

    def fetch(self, ctx: RunContext) -> Iterable[RawRecord]:
        since = ctx.since or date.today() - timedelta(days=7)
        until = ctx.until or date.today()
        with httpx.Client(timeout=30) as client:
            for site in ctx.sites:
                if site.lat is None or site.lon is None:
                    continue
                resp = client.get(
                    API_URL,
                    params={
                        "lat": site.lat,
                        "lon": site.lon,
                        "date": since.isoformat(),
                        "last_date": until.isoformat(),
                    },
                )
                resp.raise_for_status()
                yield {"site_id": str(site.id), "payload": resp.json()}

    def transform(self, raw: Iterable[RawRecord]) -> Iterable[WeatherDay]:
        for record in raw:
            site_id = record["site_id"]
            by_day: dict[date, list[dict[str, Any]]] = defaultdict(list)
            for hour in record["payload"].get("weather", []):
                day = date.fromisoformat(hour["timestamp"][:10])
                by_day[day].append(hour)
            for day, hours in sorted(by_day.items()):
                temps = [h["temperature"] for h in hours if h.get("temperature") is not None]
                rains = [h["precipitation"] for h in hours if h.get("precipitation") is not None]
                snow = any(
                    marker in (h.get("icon") or "") or marker in (h.get("condition") or "")
                    for h in hours
                    for marker in SNOW_MARKERS
                )
                yield WeatherDay(
                    site_id=site_id,
                    date=day,
                    rain_mm=round(sum(rains), 2) if rains else None,
                    temp_c=round(sum(temps) / len(temps), 2) if temps else None,
                    snow=snow,
                )

    def load(self, records: Iterable[WeatherDay], db: Client) -> LoadStats:
        rows = [r.model_dump(mode="json") for r in records]
        if rows:
            db.table("weather").upsert(rows, on_conflict="site_id,date").execute()
        return LoadStats(loaded=len(rows))
