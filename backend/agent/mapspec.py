"""MapSpec and ChartSpec: how the agent draws (docs/AGENT.md section 5).

Plain JSON validated here; the JSON Schema (agent/mapspec.schema.json) and the TypeScript
types (frontend/src/lib/mapspec.ts) are generated from these models by
`uv run python scripts/gen_mapspec.py`. Style comes from the app: the model picks a scale and
one of the app's named palettes; sizes are bounded; data comes from a `result_id` (the full
query result kept server-side) or inline rows.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Scale = Literal["sequential", "diverging", "categorical"]
# the app's palettes (frontend/src/app/colors.ts and lib/energy.ts); the frontend maps the names
Palette = Literal[
    "share",
    "price",
    "price_glow",
    "offline",
    "solar",
    "wind",
    "fuel",
    "plant_type",
    "voltage",
    "neutral",
]
Shapes = Literal[
    "countries",
    "us_states",
    "us_counties",
    "nuts0",
    "nuts1",
    "nuts2",
    "nuts3",
    "bidding_zones",
    "admin1",
]
OverlayKind = Literal["points", "lines", "arcs", "choropleth", "columns", "labels"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Camera(Strict):
    """A preset, or a centre and zoom, or a bounding box [west, south, east, north]."""

    preset: Literal["europe", "world", "us"] | None = None
    center: tuple[float, float] | None = Field(default=None, description="[lon, lat]")
    zoom: float | None = Field(default=None, ge=0, le=14)
    bbox: tuple[float, float, float, float] | None = None


class AppState(Strict):
    """The app's own state: layers switched on (store.ts LayerId), colouring, mode, selection."""

    layers: list[str] = Field(default_factory=list, max_length=8)
    colour: str | None = Field(
        default=None, description="a dataset id that colours the countries, or 'none'"
    )
    mode: Literal["live", "day", "year"] | None = None
    selection: str | None = Field(default=None, description="a country (ISO alpha-2) or place code")


class DataRef(Strict):
    """Where the overlay's rows come from and how they are placed."""

    result_id: str | None = Field(default=None, pattern=r"^r_[0-9a-f]{12}$")
    inline: list[dict[str, str | float | int | bool | None]] | None = Field(
        default=None, max_length=5000
    )
    key: str | None = Field(default=None, description="column holding the shape key (choropleth)")
    shapes: Shapes | None = None
    lon: str | None = None
    lat: str | None = None
    from_lon: str | None = None
    from_lat: str | None = None
    to_lon: str | None = None
    to_lat: str | None = None

    @model_validator(mode="after")
    def one_source(self) -> DataRef:
        if (self.result_id is None) == (self.inline is None):
            raise ValueError("data needs exactly one of result_id or inline")
        return self


class ValueEncoding(Strict):
    column: str
    unit: str
    scale: Scale = "sequential"
    palette: Palette = "neutral"


class SizeEncoding(Strict):
    column: str
    unit: str
    max_px: int = Field(default=18, ge=2, le=40)


class Legend(Strict):
    title: str = Field(max_length=80)
    how: str = Field(
        description="how the value was computed, e.g. 'sum of units commissioned in 2025'",
        max_length=200,
    )


class Overlay(Strict):
    id: str = Field(pattern=r"^[a-z0-9_]{1,40}$")
    kind: OverlayKind
    data: DataRef
    value: ValueEncoding | None = None
    size: SizeEncoding | None = None
    label: str | None = Field(default=None, description="column with the label text (labels)")
    legend: Legend
    tooltip: list[str] = Field(default_factory=list, max_length=8)
    source: str = Field(min_length=3, max_length=300)

    @model_validator(mode="after")
    def placement(self) -> Overlay:
        d = self.data
        point = bool(d.lon and d.lat)
        keyed = bool(d.key and d.shapes)
        if self.kind == "choropleth" and not keyed:
            raise ValueError("a choropleth needs data.key and data.shapes")
        if self.kind == "choropleth" and self.value is None:
            raise ValueError("a choropleth needs a value encoding")
        if self.kind in ("points", "labels", "columns") and not (point or keyed):
            raise ValueError(f"{self.kind} need data.lon and data.lat (or key and shapes)")
        if self.kind in ("lines", "arcs") and not (
            d.from_lon and d.from_lat and d.to_lon and d.to_lat
        ):
            raise ValueError(f"{self.kind} need from_lon, from_lat, to_lon and to_lat columns")
        if self.kind == "labels" and not self.label:
            raise ValueError("labels need a label column")
        if self.kind == "columns" and self.size is None and self.value is None:
            raise ValueError("columns need a value or size encoding (the height)")
        return self


class MapSpec(Strict):
    title: str = Field(max_length=120)
    camera: Camera | None = None
    app: AppState | None = None
    overlays: list[Overlay] = Field(default_factory=list, max_length=4)
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def something_to_show(self) -> MapSpec:
        if not self.overlays and not (self.app and self.app.layers):
            raise ValueError("a map shows at least one overlay or one app layer")
        ids = [o.id for o in self.overlays]
        if len(ids) != len(set(ids)):
            raise ValueError("overlay ids must be unique")
        return self


class ChartAxis(Strict):
    column: str
    unit: str | None = None


class ChartSeries(Strict):
    column: str
    label: str = Field(max_length=60)
    unit: str


class ChartSpec(Strict):
    kind: Literal["line", "bar", "stacked"]
    title: str = Field(max_length=120)
    data: DataRef
    x: ChartAxis
    series: list[ChartSeries] = Field(min_length=1, max_length=2)
    source: str = Field(min_length=3, max_length=300)
    how: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def small(self) -> ChartSpec:
        if self.data.inline is not None and len(self.data.inline) > 2000:
            raise ValueError("a chart takes at most 2,000 points inline")
        return self


def schema() -> dict:
    """One JSON Schema with both specs (the shared contract)."""
    from pydantic.json_schema import models_json_schema

    _, top = models_json_schema(
        [(MapSpec, "validation"), (ChartSpec, "validation")],
        title="InfraAtlas MapSpec and ChartSpec",
    )
    top["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    top["description"] = "Generated from backend/agent/mapspec.py; do not edit by hand."
    return top
