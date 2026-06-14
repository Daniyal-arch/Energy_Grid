"""MaStR wind units -> per-turbine geometry (turbines table).

The `mastr` adapter clusters wind turbines into farm *sites* (one farm = one
construction site, geom = the farm hull). This adapter reads the same wind CSV,
reproduces the *exact* same clustering, and writes one row per turbine carrying
its real hub height and rotor diameter — so the frontend can place a correctly
scaled 3D turbine mesh at each point. It never touches `sites`, so re-running it
is safe and does not clobber OSM-refined AOIs.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd
from app.config import get_settings

from ingestion import geo
from ingestion.base import BaseSource, LoadStats, RawRecord, RunContext, SourceMeta
from ingestion.registry import register
from ingestion.sources.mastr import (
    C_CAP,
    C_ID,
    C_LAT,
    C_LON,
    C_STATUS,
    DECOMMISSIONED,
    MIN_KW,
)
from supabase import Client

WIND_CSV = "bnetza_mastr_wind_raw.csv"
C_HUB = "Nabenhoehe"  # hub height, metres
C_ROTOR = "Rotordurchmesser"  # rotor diameter, metres

# plausible onshore ranges; outside these the MaStR value is junk (we saw 1 m hubs,
# 0.2 m rotors) so we fall back to the fleet median for a sane-looking model
HUB_RANGE = (25.0, 300.0)
ROTOR_RANGE = (20.0, 220.0)
HUB_DEFAULT = 100.0
ROTOR_DEFAULT = 90.0


def _num(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return v if lo <= v <= hi else default


@register
class WindTurbinesSource(BaseSource):
    meta = SourceMeta(
        name="wind_turbines",
        description="MaStR wind units -> per-turbine geometry (hub height, rotor diameter)",
        cadence="monthly",
        requires_credentials=(),
        phase=2,
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
        member = next((n for n in z.namelist() if n.split("/")[-1] == WIND_CSV), None)
        if not member:
            return
        usecols = [C_ID, C_CAP, C_STATUS, C_LAT, C_LON, C_HUB, C_ROTOR]
        with z.open(member) as f:
            reader = pd.read_csv(
                io.TextIOWrapper(f, encoding="utf-8"),
                usecols=lambda c: c in usecols,
                chunksize=200_000,
                low_memory=False,
            )
            # NB: same filter order as mastr.MaStRSource.fetch — this preserves row
            # order, so cluster_turbines reproduces identical farms / WINDFARM ids
            for chunk in reader:
                cap = pd.to_numeric(chunk.get(C_CAP), errors="coerce")
                sel = chunk[cap >= MIN_KW].copy()
                sel = sel[sel[C_STATUS] != DECOMMISSIONED]
                sel = sel[sel[C_LAT].notna() & sel[C_LON].notna()]
                for row in sel.to_dict("records"):
                    yield row

    def transform(self, raw: Iterable[RawRecord]) -> Iterable[RawRecord]:
        turbines = list(raw)
        if not turbines:
            return
        coords = [(float(t[C_LON]), float(t[C_LAT])) for t in turbines]
        for members in geo.cluster_turbines(coords):
            group = [turbines[i] for i in members]
            ids = sorted(str(t[C_ID]) for t in group)
            farm_mastr_id = f"WINDFARM-{ids[0]}"  # must match mastr._wind_farms
            for t in group:
                yield {
                    "farm_mastr_id": farm_mastr_id,
                    "mastr_id": str(t[C_ID]),
                    "lat": float(t[C_LAT]),
                    "lon": float(t[C_LON]),
                    "hub_height_m": _num(t.get(C_HUB), *HUB_RANGE, HUB_DEFAULT),
                    "rotor_diameter_m": _num(t.get(C_ROTOR), *ROTOR_RANGE, ROTOR_DEFAULT),
                    "capacity_kw": float(t[C_CAP]) if pd.notna(t.get(C_CAP)) else None,
                    "status": (str(t[C_STATUS]).strip() or None) if pd.notna(t.get(C_STATUS)) else None,
                }

    def load(self, records: Iterable[RawRecord], db: Client) -> LoadStats:
        turbines = list(records)
        farm_ids = sorted({t["farm_mastr_id"] for t in turbines})
        # resolve farm mastr_id -> site uuid
        site_by_farm: dict[str, str] = {}
        for i in range(0, len(farm_ids), 300):
            batch = farm_ids[i : i + 300]
            rows = db.table("sites").select("id,mastr_id").in_("mastr_id", batch).execute().data or []
            for r in rows:
                site_by_farm[r["mastr_id"]] = r["id"]

        rows: list[dict[str, Any]] = []
        skipped = 0
        for t in turbines:
            site_id = site_by_farm.get(t["farm_mastr_id"])
            if not site_id:  # farm not in sites (e.g. filtered out) — skip its turbines
                skipped += 1
                continue
            rows.append(
                {
                    "site_id": site_id,
                    "mastr_id": t["mastr_id"],
                    "lat": t["lat"],
                    "lon": t["lon"],
                    "hub_height_m": t["hub_height_m"],
                    "rotor_diameter_m": t["rotor_diameter_m"],
                    "capacity_kw": t["capacity_kw"],
                    "status": t["status"],
                }
            )
        for i in range(0, len(rows), 500):
            db.table("turbines").upsert(rows[i : i + 500], on_conflict="mastr_id").execute()
        return LoadStats(loaded=len(rows), skipped=skipped)
