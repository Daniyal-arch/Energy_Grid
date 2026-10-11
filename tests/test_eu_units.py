"""Output per plant: units placed and summed by the JRC plant code (scripts/build_eu_units.py)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_eu_units import build  # noqa: E402


def test_units_of_one_plant_are_summed_and_unplaced_units_counted() -> None:
    slots = 96
    a = [100.0] * slots
    b = [None] * slots
    b[0] = 50.0
    units = {
        "U1": {"area": "DE-Amprion", "name": "Block A", "fuel": "coal", "values": a},
        "U2": {"area": "DE-Amprion", "name": "Block B", "fuel": "coal", "values": b},
        "U3": {"area": "FR", "name": "Nowhere", "fuel": "gas", "values": a},
    }
    jrc = {
        "U1": {"eic_p": "P1", "name_p": "Plant", "lat": "51.0", "lon": "6.6", "capacity_g": "600"},
        "U2": {"eic_p": "P1", "name_p": "Plant", "lat": "51.0", "lon": "6.6", "capacity_g": "400"},
    }
    out = build(date(2026, 10, 1), units, ["IT"], jrc)
    assert len(out["plants"]) == 1
    lon, lat, fuel, iso, capacity, name, n = out["plants"][0]
    assert (iso, capacity, name, n) == ("DE", 1000.0, "Plant", 2)
    assert out["fuels"][fuel] == "coal"
    assert out["output"][0][0] == 150.0  # both units in the first slot
    assert out["output"][0][1] == 100.0  # only the first afterwards
    assert out["countries"] == {"DE": {"units": 2, "placed": 2}, "FR": {"units": 1}}
    assert out["areas_without_data"] == ["IT"]
