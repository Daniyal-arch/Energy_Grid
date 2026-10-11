"""A US day in the shape of the Europe day files (scripts/build_us_day.py)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_us_day import build  # noqa: E402


def test_regions_flows_and_renewable_share() -> None:
    # 2026-10-07 starts at 04:00 UTC (EDT)
    region = [
        {
            "respondent": "TEX",
            "respondent-name": "Texas",
            "type": "D",
            "period": "2026-10-07T04",
            "value": "50000",
        },
        {
            "respondent": "US48",
            "respondent-name": "Lower 48",
            "type": "D",
            "period": "2026-10-07T04",
            "value": "400000",
        },
    ]
    fuel = [
        {"respondent": "TEX", "fueltype": "WND", "period": "2026-10-07T04", "value": "20000"},
        {"respondent": "TEX", "fueltype": "NG", "period": "2026-10-07T04", "value": "30000"},
        {"respondent": "TEX", "fueltype": "BAT", "period": "2026-10-07T04", "value": "-500"},
    ]
    inter = [
        {"fromba": "TEX", "toba": "CENT", "period": "2026-10-07T04", "value": "800"},
    ]
    day = build(date(2026, 10, 7), region, fuel, inter)
    assert day["slots"] == 24 and day["step_s"] == 3600
    tex = day["countries"]["TEX"]
    assert tex["load"][0] == 50000.0
    assert tex["generation"]["wind"][0] == 20000.0
    assert tex["renewable_share"][0] == 40.0  # 20 GW of 50 GW positive output
    # one direction per pair: CENT < TEX, so the pair is CENT>TEX and the flow flips
    assert day["borders"] == [{"a": "CENT", "b": "TEX", "values": [-800.0] + [None] * 23}]
    assert day["eu"]["load"][0] == 400000.0
    assert day["names"]["TEX"] == "Texas"
