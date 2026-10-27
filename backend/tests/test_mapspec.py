import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.mapspec import ChartSpec, MapSpec

BACKEND = Path(__file__).resolve().parents[1]


def overlay(**kw):
    base = {
        "id": "a",
        "kind": "choropleth",
        "data": {"result_id": "r_0123456789ab", "key": "country", "shapes": "countries"},
        "value": {"column": "mw", "unit": "MW", "scale": "sequential", "palette": "solar"},
        "legend": {"title": "Solar", "how": "sum"},
        "source": "MaStR",
    }
    base.update(kw)
    return base


def test_valid_choropleth():
    m = MapSpec.model_validate({"title": "t", "overlays": [overlay()]})
    assert m.overlays[0].value.palette == "solar"


@pytest.mark.parametrize(
    "bad",
    [
        {"data": {"result_id": "r_0123456789ab"}},  # no key/shapes
        {"value": None},
        {"kind": "points", "data": {"result_id": "r_0123456789ab"}},
        {"kind": "arcs", "data": {"result_id": "r_0123456789ab", "from_lon": "a"}},
        {"value": {"column": "mw", "unit": "MW", "palette": "hotpink"}},
        {"data": {"key": "c", "shapes": "countries"}},  # no source of rows
        {"data": {"result_id": "r_x", "key": "c", "shapes": "countries"}},
        {"extra": 1},
        {"source": ""},
    ],
)
def test_invalid_overlays(bad):
    with pytest.raises(ValidationError):
        MapSpec.model_validate({"title": "t", "overlays": [overlay(**bad)]})


def test_empty_map_and_duplicate_ids_refused():
    with pytest.raises(ValidationError):
        MapSpec.model_validate({"title": "t"})
    MapSpec.model_validate({"title": "t", "app": {"layers": ["plants"]}})
    with pytest.raises(ValidationError):
        MapSpec.model_validate({"title": "t", "overlays": [overlay(), overlay()]})


def test_chart_limits():
    rows = [{"x": i, "y": i} for i in range(2001)]
    with pytest.raises(ValidationError):
        ChartSpec.model_validate(
            {
                "kind": "line",
                "title": "t",
                "data": {"inline": rows},
                "x": {"column": "x"},
                "series": [{"column": "y", "label": "y", "unit": "MW"}],
                "source": "s",
            }
        )


def test_generated_files_up_to_date():
    r = subprocess.run(
        [sys.executable, "scripts/gen_mapspec.py", "--check"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout
