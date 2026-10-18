"""GB carbon intensity (scripts/fetch_gb_carbon.py) and Denmark live (scripts/fetch_dk_live.py)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fetch_dk_live  # noqa: E402
import fetch_gb_carbon  # noqa: E402


def _p(t: str, forecast: int, actual: int | None) -> dict:
    return {
        "from": t,
        "to": t,
        "intensity": {"forecast": forecast, "actual": actual, "index": "low"},
    }


MIX = {"from": "a", "to": "b", "generationmix": [{"fuel": "wind", "perc": 42.1}]}
REG = [
    {
        "from": "a",
        "to": "b",
        "regions": [
            {
                "regionid": 1,
                "shortname": "North Scotland",
                "dnoregion": "SSE",
                "intensity": {"forecast": 0, "index": "very low"},
            }
        ],
    }
]


def test_gb_now_is_the_newest_actual() -> None:
    past = [
        _p("2026-10-18T04:00Z", 60, 61),
        _p("2026-10-18T04:30Z", 64, 69),
        _p("2026-10-18T05:00Z", 67, None),
    ]
    out = fetch_gb_carbon.build(past, [_p("2026-10-18T05:00Z", 67, None)], MIX, REG)
    assert out["now"] == {
        "from": "2026-10-18T04:30Z",
        "to": "2026-10-18T04:30Z",
        "gco2_kwh": 69,
        "kind": "actual",
        "index": "low",
    }
    assert out["mix"]["pct"] == {"wind": 42.1}
    assert out["regions"]["rows"] == [[1, "North Scotland", "SSE", 0, "very low"]]


def test_gb_forecast_labelled_when_no_actual() -> None:
    out = fetch_gb_carbon.build([_p("2026-10-18T05:00Z", 67, None)], [], MIX, REG)
    assert out["now"]["kind"] == "forecast" and out["now"]["gco2_kwh"] == 67


def test_dk_grid_and_newest_production() -> None:
    end = datetime(2026, 10, 18, 5, 27, tzinfo=UTC)
    co2 = [
        {"Minutes5UTC": "2026-10-18T05:20:00", "PriceArea": "DK1", "CO2Emission": 107.0},
        {"Minutes5UTC": "2026-10-17T05:25:00", "PriceArea": "DK2", "CO2Emission": 20.0},
        {"Minutes5UTC": "2026-10-17T05:20:00", "PriceArea": "DK2", "CO2Emission": 99.0},
    ]
    prod = [
        {"Minutes5UTC": "2026-10-18T05:15:00", "PriceArea": "DK1", "SolarPower": 1.0},
        {"Minutes5UTC": "2026-10-18T05:20:00", "PriceArea": "DK1", "SolarPower": 87.129997},
    ]
    out = fetch_dk_live.build(co2, prod, end)
    # the 24 h before 05:25: 288 slots from 2026-10-17T05:25
    assert out["co2"]["start"] == "2026-10-17T05:25:00+00:00"
    assert len(out["co2"]["DK1"]) == 288
    assert out["co2"]["DK1"][-1] == 107.0 and out["co2"]["DK2"][0] == 20.0
    assert 99.0 not in out["co2"]["DK2"]
    assert out["production"]["DK1"]["at"] == "2026-10-18T05:20:00+00:00"
    assert out["production"]["DK1"]["mw"]["SolarPower"] == 87.13
    assert "DK2" not in out["production"]
