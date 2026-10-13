"""Climate TRACE assets: previous year by id, groups (scripts/fetch_climate_trace.py)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_climate_trace import build  # noqa: E402


def asset(i: int, t: float, sector: str, lon: float | None = 1.0) -> dict:
    return {
        "Id": i,
        "Name": f"A{i}",
        "Country": "POL",
        "Sector": sector,
        "Centroid": {"Geometry": [lon, 51.0]},
        "Owners": [{"CompanyName": "X"}, {"CompanyName": "X"}, {"CompanyName": "Y"}],
        "EmissionsSummary": [{"Gas": "co2e_100yr", "EmissionsQuantity": t}],
    }


def test_build_joins_previous_year_and_groups() -> None:
    now = [
        asset(1, 2e6, "electricity-generation"),
        asset(2, 5e6, "cement"),
        asset(2, 5e6, "cement"),  # listed twice: kept once
        asset(3, 3e5, "coal-mining", lon=None),  # no position: left out
    ]
    before = [asset(1, 1.5e6, "electricity-generation")]
    out = build(now, before, 2025)
    assert [r[3] for r in out["rows"]] == ["A2", "A1"]  # largest first
    a1 = out["rows"][1]
    assert a1[5] == 2_000_000 and a1[6] == 1_500_000 and a1[7] == "X; Y"
    assert out["rows"][0][6] is None
    groups = [out["groups"][out["group_of"][r[4]]] for r in out["rows"]]
    assert groups == ["Cement and lime", "Power and heat"]
