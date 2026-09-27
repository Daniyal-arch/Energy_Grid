"""Shared Pydantic domain models. Single source of truth for backend AND ingestion.

These mirror the Supabase schema (supabase/migrations/). Keep them in sync.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SiteState(StrEnum):
    UNKNOWN = "unknown"
    NO_ACTIVITY = "no_activity"
    CLEARING = "clearing"
    EARTHWORKS = "earthworks"
    CONSTRUCTION = "construction"
    COMPLETE = "complete"


class Sensor(StrEnum):
    S2 = "s2"
    S1 = "s1"


class Metric(StrEnum):
    NDVI = "ndvi"
    BSI = "bsi"
    VH_DB = "vh_db"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Technology(StrEnum):
    SOLAR = "solar"
    WIND = "wind"
    BIOMASS = "biomass"
    HYDRO = "hydro"
    GEOTHERMAL = "geothermal"
    COMBUSTION = "combustion"
    STORAGE = "storage"


class Site(BaseModel):
    id: UUID | None = None
    mastr_id: str | None = None
    name: str
    geom_wkt: str = Field(description="MultiPolygon WKT, SRID 4326", exclude=True)
    capacity_mw: float
    state: str
    owner: str | None = None
    status: SiteState = SiteState.UNKNOWN
    status_since: date | None = None
    aoi_method: str | None = None
    # expanded MaStR attributes (all-technology, nationwide scope)
    technology: Technology | None = None
    mastr_status: str | None = None
    commissioning_date: date | None = None
    planned_commissioning_date: date | None = None
    municipality: str | None = None
    district: str | None = None
    unit_count: int = 1
    # populated when reading from the sites_with_centroid view
    lat: float | None = None
    lon: float | None = None

    def to_row(self) -> dict[str, Any]:
        row = self.model_dump(mode="json", exclude_none=True, exclude={"lat", "lon"})
        row["geom"] = f"SRID=4326;{self.geom_wkt}"
        return row


class Deadline(BaseModel):
    id: UUID | None = None
    site_id: UUID
    source: str
    deadline_date: date
    type: str


class TimeseriesPoint(BaseModel):
    site_id: UUID
    date: date
    sensor: Sensor
    metric: Metric
    value: float
    scene_id: str | None = None


class Evidence(BaseModel):
    id: UUID | None = None
    site_id: UUID
    scene_id: str
    sensor: Sensor
    acquired_at: date
    chip_url: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class Detection(BaseModel):
    id: UUID | None = None
    site_id: UUID
    detected_at: date
    from_state: SiteState
    to_state: SiteState
    confidence: Confidence
    evidence_ids: list[UUID] = Field(default_factory=list)


class WeatherDay(BaseModel):
    site_id: UUID
    date: date
    rain_mm: float | None = None
    snow: bool = False
    temp_c: float | None = None


class PowerOutput(BaseModel):
    plant_id: str
    site_id: UUID | None = None
    date: date
    mwh: float
    source: str


class GridSnapshot(BaseModel):
    """Zone-level hourly metric: generation mix per fuel, day-ahead price, and a
    carbon intensity figure WE compute (source='energy-charts:computed') from the
    mix x static emission factors — never derived live by the agent or frontend."""

    zone: str
    ts: datetime
    metric: str
    value: float
    source: str


class GridExchange(BaseModel):
    """Zone-level hourly cross-border physical flow. value_mw is signed:
    positive = import to `zone`, negative = export from `zone`."""

    zone: str
    neighbor_zone: str
    ts: datetime
    value_mw: float
    source: str
