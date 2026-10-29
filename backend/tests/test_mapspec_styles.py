"""MapSpec v2: the 22 styles, several maps side by side, edits of a map on screen."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.cartographer import view_maps
from agent.graph import after_router
from agent.mapspec import FLAT_STYLES, STYLES_3D, MapSpec
from agent.router import heuristic

RID = "r_0123456789ab"


def overlay(kind: str, **extra: object) -> dict:
    return {
        "id": f"o_{kind}",
        "kind": kind,
        "data": {"result_id": RID, "lon": "lon", "lat": "lat"},
        "value": {"column": "mw", "unit": "MW"},
        "legend": {"title": "MW", "how": "as published"},
        "source": "test source",
        **extra,
    }


def test_at_least_ten_styles_each():
    assert len(FLAT_STYLES) >= 10 and len(STYLES_3D) >= 10


@pytest.mark.parametrize(
    "kind",
    [
        "dots",
        "bubbles",
        "hexbin",
        "grid",
        "heatmap",
        "contour",
        "columns",
        "beams",
        "spikes",
        "lollipops",
        "hex_columns",
        "grid_columns",
        "terrain",
        "point_cloud",
    ],
)
def test_point_styles_validate(kind: str):
    MapSpec.model_validate({"title": "t", "overlays": [overlay(kind)]})


def test_shape_pair_and_special_styles():
    shape = {"result_id": RID, "key": "iso2", "shapes": "countries"}
    MapSpec.model_validate({"title": "t", "overlays": [overlay("prisms", data=shape)]})
    pair = {"result_id": RID, "from_lon": "a", "from_lat": "b", "to_lon": "c", "to_lat": "d"}
    for k in ("flows", "arcs_3d", "lines"):
        MapSpec.model_validate({"title": "t", "overlays": [overlay(k, data=pair)]})
    MapSpec.model_validate(
        {"title": "t", "overlays": [overlay("bivariate", value2={"column": "t", "unit": "t"})]}
    )
    MapSpec.model_validate({"title": "t", "overlays": [overlay("pies", category="fuel")]})
    with pytest.raises(ValidationError):
        MapSpec.model_validate({"title": "t", "overlays": [overlay("bivariate")]})
    with pytest.raises(ValidationError):
        MapSpec.model_validate({"title": "t", "overlays": [overlay("pies")]})


def test_panels_are_several_maps():
    spec = {
        "title": "Two variables",
        "panels": [
            {"title": "Capacity", "overlays": [overlay("bubbles")]},
            {"title": "Emissions", "overlays": [{**overlay("hexbin"), "id": "o_e"}]},
        ],
        "replaces": "m_0123456789ab",
    }
    m = MapSpec.model_validate(spec)
    assert len(m.all_overlays()) == 2
    with pytest.raises(ValidationError):
        MapSpec.model_validate({"title": "t", "panels": [spec["panels"][0]]})
    with pytest.raises(ValidationError):
        MapSpec.model_validate({**spec, "overlays": [overlay("dots")]})


def test_edits_go_straight_to_the_cartographer():
    assert heuristic("make it 3D with hexagons")["edit"]
    assert not heuristic("how much coal capacity has Poland")["edit"]
    view = {"maps": [{"id": "m_0123456789ab"}]}
    state = {"route": {"edit": True, "map": True}, "view": view}
    assert view_maps(state) == view["maps"]
    assert after_router(state) == "cartographer"
    assert after_router({"route": {"edit": True}, "view": None}) == "analyst"
