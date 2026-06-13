"""Marktstammdatenregister -> sites.

Reads the open-mastr Zenodo snapshot (the official bulk server is throttled to ~6 KB/s;
see scripts/download_mastr.py). Filters to monitorable, ground-based generation sites
across all of Germany:

  * net capacity >= 5 MW
  * solar: ground-mounted only (Lage == 'Freifläche'); other technologies are inherently
    ground-based facilities
  * excludes permanently decommissioned units

Wind turbines are clustered into farm footprints (one farm = one construction site).
AOI polygons are capacity-based buffers (OSM polygon matching is a Phase 2 refinement).
"""

from __future__ import annotations

import io
import zipfile
from collections import Counter
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from app.config import get_settings
from app.models import Site, Technology

from ingestion import geo
from ingestion.base import BaseSource, LoadStats, RawRecord, RunContext, SourceMeta
from ingestion.registry import register
from supabase import Client

MIN_KW = 5000.0
DECOMMISSIONED = "Endgültig stillgelegt"

# tech -> (csv filename, Technology, ground_filter, ha_per_mw, min_side_m)
TECH_CONFIG: dict[str, tuple[str, Technology, bool, float, float]] = {
    "solar": ("bnetza_mastr_solar_raw.csv", Technology.SOLAR, True, 1.4, 200.0),
    "wind": ("bnetza_mastr_wind_raw.csv", Technology.WIND, False, 0.0, 0.0),
    "biomass": ("bnetza_mastr_biomass_raw.csv", Technology.BIOMASS, False, 0.2, 150.0),
    "hydro": ("bnetza_mastr_hydro_raw.csv", Technology.HYDRO, False, 0.2, 150.0),
    "gsgk": ("bnetza_mastr_gsgk_raw.csv", Technology.GEOTHERMAL, False, 0.2, 150.0),
    "combustion": ("bnetza_mastr_combustion_raw.csv", Technology.COMBUSTION, False, 0.3, 200.0),
    "storage": ("bnetza_mastr_storage_raw.csv", Technology.STORAGE, False, 0.3, 150.0),
}

# verified MaStR column names (scripts/probe_mastr_csv.py)
C_ID = "EinheitMastrNummer"
C_NAME = "Name"
C_CAP = "Nettonennleistung"  # kW
C_STATUS = "EinheitBetriebsstatus"
C_STATE = "Bundesland"
C_DISTRICT = "Landkreis"
C_MUNI = "Gemeinde"
C_LAT = "Breitengrad"
C_LON = "Laengengrad"
C_COMM = "Inbetriebnahmedatum"
C_PLANNED = "GeplantesInbetriebnahmedatum"
C_OWNER = "AnlagenbetreiberMastrNummer"
C_LAGE = "Lage"


def _parse_date(value: Any) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _mode(values: Iterable[Any]) -> Any:
    counts = Counter(v for v in values if v is not None and not pd.isna(v))
    return counts.most_common(1)[0][0] if counts else None


def _clean(value: Any) -> str | None:
    """Trim a CSV cell to a non-empty string, or None for missing/NaN."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


@register
class MaStRSource(BaseSource):
    meta = SourceMeta(
        name="mastr",
        description="German registry -> generation sites (>=5 MW, ground-based, nationwide)",
        cadence="monthly",
        requires_credentials=(),
        phase=1,
        site_scoped=False,
    )

    def _zip(self) -> zipfile.ZipFile:
        path = Path(get_settings().mastr_zip_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            raise FileNotFoundError(
                f"MaStR snapshot not found at {path}. Run scripts/download_mastr.py first."
            )
        return zipfile.ZipFile(path)

    def fetch(self, ctx: RunContext) -> Iterable[RawRecord]:
        z = self._zip()
        members = {n.split("/")[-1]: n for n in z.namelist()}
        usecols = [
            C_ID,
            C_NAME,
            C_CAP,
            C_STATUS,
            C_STATE,
            C_DISTRICT,
            C_MUNI,
            C_LAT,
            C_LON,
            C_COMM,
            C_PLANNED,
            C_OWNER,
            C_LAGE,
        ]
        for tech, (fname, _, ground_only, *_rest) in TECH_CONFIG.items():
            member = members.get(fname)
            if not member:
                continue
            with z.open(member) as f:
                reader = pd.read_csv(
                    io.TextIOWrapper(f, encoding="utf-8"),
                    usecols=lambda c: c in usecols,
                    chunksize=200_000,
                    low_memory=False,
                )
                for chunk in reader:
                    cap = pd.to_numeric(chunk.get(C_CAP), errors="coerce")
                    sel = chunk[cap >= MIN_KW].copy()
                    sel = sel[sel[C_STATUS] != DECOMMISSIONED]
                    sel = sel[sel[C_LAT].notna() & sel[C_LON].notna()]
                    if ground_only and C_LAGE in sel:
                        sel = sel[sel[C_LAGE] == "Freifläche"]
                    for row in sel.to_dict("records"):
                        row["_tech"] = tech
                        yield row

    def transform(self, raw: Iterable[RawRecord]) -> Iterable[Site]:
        wind: list[RawRecord] = []
        for rec in raw:
            if rec["_tech"] == "wind":
                wind.append(rec)
            else:
                yield self._unit_site(rec)
        yield from self._wind_farms(wind)

    def _unit_site(self, rec: RawRecord) -> Site:
        _, technology, _, ha_per_mw, min_side = TECH_CONFIG[rec["_tech"]]
        capacity_mw = float(rec[C_CAP]) / 1000.0
        lon, lat = float(rec[C_LON]), float(rec[C_LAT])
        side = geo.capacity_side_m(capacity_mw, ha_per_mw, min_side)
        return Site(
            mastr_id=str(rec[C_ID]),
            name=_clean(rec.get(C_NAME)) or f"{technology.value} {rec[C_ID]}",
            geom_wkt=geo.square_wkt(lon, lat, side),
            capacity_mw=round(capacity_mw, 3),
            state=_clean(rec.get(C_STATE)) or "unbekannt",
            owner=_clean(rec.get(C_OWNER)),
            technology=technology,
            mastr_status=_clean(rec.get(C_STATUS)),
            commissioning_date=_parse_date(rec.get(C_COMM)),
            planned_commissioning_date=_parse_date(rec.get(C_PLANNED)),
            municipality=_clean(rec.get(C_MUNI)),
            district=_clean(rec.get(C_DISTRICT)),
            aoi_method="capacity_buffer",
            lat=lat,
            lon=lon,
        )

    def _wind_farms(self, turbines: list[RawRecord]) -> Iterable[Site]:
        if not turbines:
            return
        coords = [(float(t[C_LON]), float(t[C_LAT])) for t in turbines]
        for members in geo.cluster_turbines(coords):
            group = [turbines[i] for i in members]
            mcoords = [coords[i] for i in members]
            ids = sorted(str(t[C_ID]) for t in group)
            capacity_mw = sum(float(t[C_CAP]) for t in group) / 1000.0
            statuses = [t.get(C_STATUS) for t in group]
            # a farm with any unit still in planning is treated as under construction
            status = "In Planung" if any(s == "In Planung" for s in statuses) else _mode(statuses)
            muni = _clean(_mode(t.get(C_MUNI) for t in group))
            comm_dates = [d for d in (_parse_date(t.get(C_COMM)) for t in group) if d]
            planned = [d for d in (_parse_date(t.get(C_PLANNED)) for t in group) if d]
            yield Site(
                mastr_id=f"WINDFARM-{ids[0]}",
                name=f"Wind farm {muni}" if muni else f"Wind farm {ids[0]}",
                geom_wkt=geo.farm_wkt(mcoords),
                capacity_mw=round(capacity_mw, 3),
                state=_clean(_mode(t.get(C_STATE) for t in group)) or "unbekannt",
                technology=Technology.WIND,
                mastr_status=_clean(status),
                commissioning_date=min(comm_dates) if comm_dates else None,
                planned_commissioning_date=min(planned) if planned else None,
                municipality=muni,
                district=_clean(_mode(t.get(C_DISTRICT) for t in group)),
                unit_count=len(group),
                aoi_method="turbine_cluster",
            )

    def load(self, records: Iterable[Site], db: Client) -> LoadStats:
        rows = [s.to_row() for s in records]
        for i in range(0, len(rows), 500):
            db.table("sites").upsert(rows[i : i + 500], on_conflict="mastr_id").execute()
        return LoadStats(loaded=len(rows))
