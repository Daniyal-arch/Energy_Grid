"""Energy-Charts (Fraunhofer ISE, api.energy-charts.info) — German generation mix,
day-ahead price, and cross-border physical flow. Free, no key, CC BY 4.0.

Energy-Charts publishes a "Renewable share of generation" series; it is stored as-is
as `renewable_share_of_generation` (source='energy-charts'). Carbon intensity and our
own `renewable_share` / carbon-free share have no ready-made number from this source:
we compute them here from generation-mix MW x static per-fuel
gCO2eq/kWh factors (UBA "Entwicklung der spezifischen Treibhausgas-Emissionen" 2023
for the German fossil fleet; IPCC AR5 WG3 Annex III median lifecycle values for
everything else) and fuel-category membership. This is the ONE place that computation
happens (CLAUDE.md rule 1: the agent never computes facts) — stored with
source='energy-charts:computed' so it's visibly distinct from passthrough values.

Shapes verified live against the API:
  GET /public_power?country=de -> {unix_seconds: [...], production_types: [{name, data}]}
  GET /price?bzn=DE-LU          -> {unix_seconds: [...], price: [...], unit}
  GET /cbpf?country=de          -> {unix_seconds: [...], countries: [{name, data}]}
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime

import httpx
from app.models import GridExchange, GridSnapshot

from ingestion.base import BaseSource, LoadStats, RawRecord, RunContext, SourceMeta
from ingestion.registry import register
from supabase import Client

BASE = "https://api.energy-charts.info"
ZONE = "DE"
COUNTRY = "de"
BZN = "DE-LU"
# the one derived series Energy-Charts publishes itself; passed through unchanged
PUBLISHED_SHARE = "Renewable share of generation"

# energy-charts `production_types[].name` -> our fuel key. Rows not listed here
# (Load, Residual load, *Renewable share*, Cross border electricity trading,
# Hydro pumped storage consumption) are not generation and are skipped.
FUEL_MAP = {
    "Fossil brown coal / lignite": "lignite",
    "Fossil hard coal": "hard_coal",
    "Fossil gas": "gas",
    "Fossil coal-derived gas": "gas",
    "Fossil oil": "oil",
    "Nuclear": "nuclear",
    "Biomass": "biomass",
    "Hydro Run-of-River": "hydro",
    "Hydro water reservoir": "hydro",
    "Hydro pumped storage": "hydro",
    "Solar": "solar",
    "Wind onshore": "wind",
    "Wind offshore": "wind",
    "Geothermal": "geothermal",
    "Waste": "waste",
    "Others": "other",
}

# gCO2eq/kWh. lignite/hard_coal: UBA 2023 (German fossil fleet, direct emissions).
# Everything else: IPCC AR5 WG3 Annex III, median lifecycle value. waste/other has
# no clean published figure — conservative fossil-comparable placeholder.
EMISSION_FACTORS = {
    "lignite": 1150.0,
    "hard_coal": 900.0,
    "gas": 410.0,
    "oil": 700.0,
    "nuclear": 12.0,
    "biomass": 230.0,
    "solar": 41.0,
    "wind": 11.0,
    "hydro": 24.0,
    "geothermal": 38.0,
    "waste": 700.0,
    "other": 700.0,
}

# standard renewable classification (wind/solar/hydro/geothermal/biomass — biogenic
# carbon is conventionally excluded from "renewable", same as national statistics).
# carbon-free adds nuclear. Both are production-based shares of DE's own generation
# mix only — unlike Electricity Maps' published figures, this does NOT adjust for the
# carbon content of imported electricity (we don't have neighbouring grids' mix data),
# so don't expect an exact match to their numbers.
RENEWABLE_FUELS = {"solar", "wind", "hydro", "biomass", "geothermal"}
CARBON_FREE_FUELS = RENEWABLE_FUELS | {"nuclear"}


def _to_dt(seconds: int) -> datetime:
    return datetime.fromtimestamp(seconds, tz=UTC)


@register
class EnergyChartsSource(BaseSource):
    meta = SourceMeta(
        name="energycharts",
        description=(
            "DE generation mix, day-ahead price, cross-border physical flow, and "
            "computed carbon intensity -> grid_snapshot / grid_exchange"
        ),
        cadence="hourly",
        requires_credentials=(),
        phase=2,
        site_scoped=False,
    )

    def fetch(self, ctx: RunContext) -> Iterable[RawRecord]:
        since = ctx.since or date.today()
        until = ctx.until or date.today()
        with httpx.Client(timeout=30) as c:
            power = c.get(f"{BASE}/public_power", params={"country": COUNTRY})
            power.raise_for_status()
            power_json = power.json()
            for series in power_json.get("production_types", []):
                if series["name"] == PUBLISHED_SHARE:
                    for sec, value in zip(power_json["unix_seconds"], series["data"], strict=True):
                        dt = _to_dt(sec)
                        if value is not None and since <= dt.date() <= until:
                            yield {"kind": "share", "ts": dt, "pct": float(value)}
                    continue
                fuel = FUEL_MAP.get(series["name"])
                if fuel is None:
                    continue
                for sec, value in zip(power_json["unix_seconds"], series["data"], strict=True):
                    if value is None:
                        continue
                    dt = _to_dt(sec)
                    if since <= dt.date() <= until:
                        yield {"kind": "power", "ts": dt, "fuel": fuel, "mw": float(value)}

            price = c.get(f"{BASE}/price", params={"bzn": BZN})
            price.raise_for_status()
            price_json = price.json()
            for sec, value in zip(price_json["unix_seconds"], price_json["price"], strict=True):
                if value is None:
                    continue
                dt = _to_dt(sec)
                if since <= dt.date() <= until:
                    yield {"kind": "price", "ts": dt, "eur_mwh": float(value)}

            flow = c.get(f"{BASE}/cbpf", params={"country": COUNTRY})
            flow.raise_for_status()
            flow_json = flow.json()
            for series in flow_json.get("countries", []):
                neighbor = series["name"]
                if neighbor == "sum":  # API includes a total-flow pseudo-row, not a real neighbor
                    continue
                for sec, value in zip(flow_json["unix_seconds"], series["data"], strict=True):
                    if value is None:
                        continue
                    dt = _to_dt(sec)
                    if since <= dt.date() <= until:
                        # API reports GW; store MW
                        yield {
                            "kind": "flow",
                            "ts": dt,
                            "neighbor": neighbor,
                            "mw": float(value) * 1000.0,
                        }

    def transform(self, raw: Iterable[RawRecord]) -> Iterable[GridSnapshot | GridExchange]:
        by_ts: dict[datetime, dict[str, float]] = {}
        for rec in raw:
            if rec["kind"] == "power":
                by_ts.setdefault(rec["ts"], {})[rec["fuel"]] = rec["mw"]
            elif rec["kind"] == "price":
                yield GridSnapshot(
                    zone=ZONE,
                    ts=rec["ts"],
                    metric="price_eur_mwh",
                    value=rec["eur_mwh"],
                    source="energy-charts",
                )
            elif rec["kind"] == "share":
                yield GridSnapshot(
                    zone=ZONE,
                    ts=rec["ts"],
                    metric="renewable_share_of_generation",
                    value=rec["pct"],
                    source="energy-charts",
                )
            elif rec["kind"] == "flow":
                yield GridExchange(
                    zone=ZONE,
                    neighbor_zone=rec["neighbor"],
                    ts=rec["ts"],
                    value_mw=rec["mw"],
                    source="energy-charts",
                )

        for ts, fuels in by_ts.items():
            for fuel, mw in fuels.items():
                yield GridSnapshot(
                    zone=ZONE, ts=ts, metric=f"gen_{fuel}", value=mw, source="energy-charts"
                )

            weighted = sum(max(mw, 0.0) * EMISSION_FACTORS[fuel] for fuel, mw in fuels.items())
            total = sum(max(mw, 0.0) for mw in fuels.values())
            if total > 0:
                yield GridSnapshot(
                    zone=ZONE,
                    ts=ts,
                    metric="carbon_intensity",
                    value=round(weighted / total, 1),
                    source="energy-charts:computed",
                )
                renewable_mw = sum(
                    max(mw, 0.0) for fuel, mw in fuels.items() if fuel in RENEWABLE_FUELS
                )
                carbon_free_mw = sum(
                    max(mw, 0.0) for fuel, mw in fuels.items() if fuel in CARBON_FREE_FUELS
                )
                yield GridSnapshot(
                    zone=ZONE,
                    ts=ts,
                    metric="renewable_share",
                    value=round(100 * renewable_mw / total, 1),
                    source="energy-charts:computed",
                )
                yield GridSnapshot(
                    zone=ZONE,
                    ts=ts,
                    metric="carbon_free_share",
                    value=round(100 * carbon_free_mw / total, 1),
                    source="energy-charts:computed",
                )

    def load(self, records: Iterable[GridSnapshot | GridExchange], db: Client) -> LoadStats:
        snapshots = [r.model_dump(mode="json") for r in records if isinstance(r, GridSnapshot)]
        exchanges = [r.model_dump(mode="json") for r in records if isinstance(r, GridExchange)]
        for i in range(0, len(snapshots), 500):
            db.table("grid_snapshot").upsert(
                snapshots[i : i + 500], on_conflict="zone,ts,metric,source"
            ).execute()
        for i in range(0, len(exchanges), 500):
            db.table("grid_exchange").upsert(
                exchanges[i : i + 500], on_conflict="zone,neighbor_zone,ts,source"
            ).execute()
        return LoadStats(loaded=len(snapshots) + len(exchanges))
