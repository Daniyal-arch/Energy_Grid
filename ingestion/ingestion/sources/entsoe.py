"""ENTSO-E Transparency Platform — German grid data (free key).

Two distinct things SMARD can't give us (verified in scripts/probe_entsoe.py):
  * full national generation per production type, incl. conventional (A75)
    -> power_output (plant_id = 'DE-<type>', source = 'entsoe'), daily MWh
  * the ~90 large generation UNITS (>=100 MW) with name + capacity (A71)
    -> grid_units (independent operational confirmation for big plants)

National renewable generation overlaps SMARD, but ENTSO adds the conventional
mix; the per-unit registry is unique.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta

import httpx
from app.config import get_settings
from app.models import PowerOutput

from ingestion.base import BaseSource, LoadStats, RawRecord, RunContext, SourceMeta
from ingestion.registry import register
from supabase import Client

BASE = "https://web-api.tp.entsoe.eu/api"
DE_LU = "10Y1001A1001A82H"  # Germany-Luxembourg bidding zone

PSR = {
    "B01": "biomass", "B02": "lignite", "B03": "coal-gas", "B04": "gas", "B05": "hard-coal",
    "B06": "oil", "B09": "geothermal", "B10": "pumped-hydro", "B11": "run-of-river-hydro",
    "B12": "reservoir-hydro", "B14": "nuclear", "B15": "other-renewable", "B16": "solar",
    "B17": "waste", "B18": "wind-offshore", "B19": "wind-onshore", "B20": "other",
}
_RES_HOURS = {"PT15M": 0.25, "PT30M": 0.5, "PT60M": 1.0, "P1D": 24.0, "P7D": 168.0}


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M")


def _strip(tag: str) -> str:
    return tag.split("}")[-1]


def _find(el: ET.Element, name: str) -> ET.Element | None:
    return next((e for e in el.iter() if _strip(e.tag) == name), None)


@register
class EntsoeSource(BaseSource):
    meta = SourceMeta(
        name="entsoe",
        description="ENTSO-E: national generation per type + large generation units",
        cadence="daily",
        requires_credentials=("ENTSOE_API_KEY",),
        phase=2,
        site_scoped=False,
    )

    def _get(self, **params: str) -> ET.Element | None:
        key = get_settings().entsoe_api_key
        r = httpx.get(BASE, params={"securityToken": key, **params}, timeout=90)
        if r.status_code != 200:
            return None
        return ET.fromstring(r.text)

    def fetch(self, ctx: RunContext) -> Iterable[RawRecord]:
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        since = ctx.since or (date.today() - timedelta(days=14))
        start = datetime(since.year, since.month, since.day, tzinfo=UTC)

        # 1) actual generation per production type (A75) -> daily MWh per type
        root = self._get(documentType="A75", processType="A16", in_Domain=DE_LU,
                         periodStart=_fmt(start), periodEnd=_fmt(now))
        if root is not None:
            for ts in (e for e in root if _strip(e.tag) == "TimeSeries"):
                psr_el = _find(ts, "psrType")
                psr = psr_el.text if psr_el is not None else None
                period = _find(ts, "Period")
                if not psr or period is None:
                    continue
                res = _find(period, "resolution")
                p0 = _find(period, "start")  # timeInterval/start
                if res is None or p0 is None:
                    continue
                hours = _RES_HOURS.get(res.text or "", 1.0)
                t0 = datetime.fromisoformat((p0.text or "").replace("Z", "+00:00"))
                for pt in (e for e in period.iter() if _strip(e.tag) == "Point"):
                    pos = _find(pt, "position")
                    qty = _find(pt, "quantity")
                    if pos is None or qty is None:
                        continue
                    when = t0 + timedelta(hours=hours * (int(pos.text or 1) - 1))
                    yield {"kind": "gen", "psr": psr, "date": when.date(),
                           "mwh": float(qty.text or 0) * hours}

        # 2) installed capacity per generation unit (A71) -> the big-plant registry
        yr = now.year
        root = self._get(documentType="A71", processType="A33", in_Domain=DE_LU,
                         periodStart=f"{yr}01010000", periodEnd=f"{yr}12312300")
        if root is not None:
            for ts in (e for e in root if _strip(e.tag) == "TimeSeries"):
                name = cap = psr = eic = None
                for e in ts.iter():
                    t = _strip(e.tag)
                    if t == "name" and name is None:
                        name = e.text
                    elif t == "nominalP":
                        cap = e.text
                    elif t == "psrType":
                        psr = e.text
                    elif t == "mRID" and eic is None:
                        eic = e.text
                if eic and name:
                    yield {"kind": "unit", "eic": eic, "name": name,
                           "capacity_mw": float(cap) if cap else None,
                           "psr_type": PSR.get(psr or "", psr)}

    def transform(self, raw: Iterable[RawRecord]) -> Iterable[RawRecord]:
        # collapse the per-type generation points into one daily MWh row per (type, day)
        daily: dict[tuple[str, date], float] = defaultdict(float)
        units: list[RawRecord] = []
        for rec in raw:
            if rec["kind"] == "gen":
                daily[(rec["psr"], rec["date"])] += rec["mwh"]
            else:
                units.append(rec)
        for (psr, d), mwh in daily.items():
            yield {
                "kind": "gen",
                "row": PowerOutput(
                    plant_id=f"DE-{PSR.get(psr, psr)}", site_id=None, date=d,
                    mwh=round(mwh, 1), source="entsoe",
                ).model_dump(mode="json", exclude_none=True),
            }
        yield from units

    def load(self, records: Iterable[RawRecord], db: Client) -> LoadStats:
        recs = list(records)
        gen = [r["row"] for r in recs if r["kind"] == "gen"]
        units = [
            {
                "eic": r["eic"],
                "name": r["name"],
                "capacity_mw": r["capacity_mw"],
                "psr_type": r["psr_type"],
                "source": "entsoe",
            }
            for r in recs
            if r["kind"] == "unit"
        ]
        for i in range(0, len(gen), 500):
            db.table("power_output").upsert(
                gen[i : i + 500], on_conflict="plant_id,date,source"
            ).execute()
        for i in range(0, len(units), 500):
            db.table("grid_units").upsert(units[i : i + 500], on_conflict="eic").execute()
        return LoadStats(loaded=len(gen) + len(units))
