"""MapSpec and ChartSpec: how the agent draws (docs/AGENT.md section 5).

Plain JSON validated here; the JSON Schema (agent/mapspec.schema.json) and the TypeScript
types (frontend/src/lib/mapspec.ts) are generated from these models by
`uv run python scripts/gen_mapspec.py`. Style comes from the app: the model picks one of the
map styles (12 flat, 10 in 3D), a scale and one of the app's named palettes; sizes are bounded;
data comes from a `result_id` (the full query result kept server-side) or inline rows. A spec is
one map (`overlays`) or several maps of the same place side by side (`panels`, one camera), and
may replace a map already on screen (`replaces`).
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
    "heat",
    "cool",
    "green",
    "purple",
    "emissions",
    "room",
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
# the map styles the app draws (frontend/src/map/agentLayers.ts); "points" and "arcs" are the
# first version's names for "dots" and "arcs_3d"
FLAT_STYLES = (
    "dots",
    "bubbles",
    "choropleth",
    "hexbin",
    "grid",
    "heatmap",
    "contour",
    "lines",
    "flows",
    "labels",
    "bivariate",
    "pies",
)
STYLES_3D = (
    "columns",
    "beams",
    "spikes",
    "lollipops",
    "hex_columns",
    "grid_columns",
    "prisms",
    "arcs_3d",
    "terrain",
    "point_cloud",
)
OverlayKind = Literal[
    "dots",
    "bubbles",
    "choropleth",
    "hexbin",
    "grid",
    "heatmap",
    "contour",
    "lines",
    "flows",
    "labels",
    "bivariate",
    "pies",
    "columns",
    "beams",
    "spikes",
    "lollipops",
    "hex_columns",
    "grid_columns",
    "prisms",
    "arcs_3d",
    "terrain",
    "point_cloud",
    "points",
    "arcs",
]
# what each style needs to place its rows
POINT_STYLES = {
    "dots",
    "bubbles",
    "hexbin",
    "grid",
    "heatmap",
    "contour",
    "labels",
    "pies",
    "columns",
    "beams",
    "spikes",
    "lollipops",
    "hex_columns",
    "grid_columns",
    "terrain",
    "point_cloud",
    "points",
}
SHAPE_STYLES = {"choropleth", "prisms"}
PAIR_STYLES = {"lines", "flows", "arcs_3d", "arcs"}


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
    kind: OverlayKind = Field(
        description="the map style: flat dots, bubbles, choropleth, hexbin, grid, heatmap, "
        "contour, lines, flows, labels, bivariate, pies; 3D columns, beams, spikes, lollipops, "
        "hex_columns, grid_columns, prisms, arcs_3d, terrain, point_cloud"
    )
    data: DataRef
    value: ValueEncoding | None = None
    value2: ValueEncoding | None = Field(
        default=None, description="the second variable of a bivariate map"
    )
    size: SizeEncoding | None = None
    category: str | None = Field(
        default=None, description="column whose values colour the marks (types, fuels, classes)"
    )
    radius_km: float | None = Field(
        default=None, ge=0.5, le=200, description="bin size of hexbin, grid and their 3D forms"
    )
    label: str | None = Field(default=None, description="column with the label text (labels)")
    legend: Legend
    tooltip: list[str] = Field(default_factory=list, max_length=8)
    source: str = Field(min_length=3, max_length=300)

    @property
    def is_3d(self) -> bool:
        return self.kind in STYLES_3D or self.kind == "arcs"

    @model_validator(mode="after")
    def placement(self) -> Overlay:
        d = self.data
        k = self.kind
        point = bool(d.lon and d.lat)
        keyed = bool(d.key and d.shapes)
        if k in SHAPE_STYLES and not keyed:
            raise ValueError(f"{k} needs data.key and data.shapes")
        if k in SHAPE_STYLES | {"heatmap", "contour", "terrain", "bivariate"} and not self.value:
            raise ValueError(f"{k} needs a value encoding")
        if k in POINT_STYLES and not (point or keyed):
            raise ValueError(f"{k} needs data.lon and data.lat (or key and shapes)")
        if k == "bivariate" and not (self.value2 and (point or keyed)):
            raise ValueError("bivariate needs value and value2, and lon/lat or key and shapes")
        if k in PAIR_STYLES and not (d.from_lon and d.from_lat and d.to_lon and d.to_lat):
            raise ValueError(f"{k} needs from_lon, from_lat, to_lon and to_lat columns")
        if k == "labels" and not self.label:
            raise ValueError("labels need a label column")
        if k == "pies" and not (self.category and self.value):
            raise ValueError("pies need a category column and a value (the parts of each place)")
        if k in STYLES_3D and k not in ("prisms", "terrain") and not (self.size or self.value):
            raise ValueError(f"{k} needs a value or size encoding (the height)")
        if k == "prisms" and not self.value:
            raise ValueError("prisms need a value encoding (the height)")
        return self


class Panel(Strict):
    """One of several maps of the same place (side by side, one camera)."""

    title: str = Field(max_length=80)
    app: AppState | None = None
    overlays: list[Overlay] = Field(default_factory=list, max_length=3)


class MapSpec(Strict):
    title: str = Field(max_length=120)
    camera: Camera | None = None
    app: AppState | None = None
    overlays: list[Overlay] = Field(default_factory=list, max_length=4)
    panels: list[Panel] = Field(
        default_factory=list,
        max_length=6,
        description="several maps side by side (2-6), one variable or theme each; "
        "instead of overlays",
    )
    replaces: str | None = Field(
        default=None,
        pattern=r"^m_[0-9a-f]{12}$",
        description="the id of a map on screen this one replaces (an edit)",
    )
    notes: str | None = Field(default=None, max_length=500)

    def all_overlays(self) -> list[Overlay]:
        return [*self.overlays, *(o for p in self.panels for o in p.overlays)]

    @model_validator(mode="after")
    def something_to_show(self) -> MapSpec:
        if self.panels:
            if self.overlays:
                raise ValueError("use either overlays (one map) or panels (several maps)")
            if len(self.panels) < 2:
                raise ValueError("panels are for 2 to 6 maps; one map uses overlays")
            for p in self.panels:
                if not p.overlays and not (p.app and p.app.layers):
                    raise ValueError(f"panel {p.title!r} shows nothing")
        elif not self.overlays and not (self.app and self.app.layers):
            raise ValueError("a map shows at least one overlay or one app layer")
        ids = [o.id for o in self.all_overlays()]
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
