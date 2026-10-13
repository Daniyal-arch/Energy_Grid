"""Grid capacity: GB connection sites and plant types (scripts/fetch_connect_here.py)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_connect_here import gb_type, site_key  # noqa: E402


def test_site_key_drops_voltage_and_generic_words() -> None:
    assert site_key("Berkswell GSP") == "berkswell"
    assert site_key("Bramford 400kV Substation") == "bramford"
    assert site_key("East Claydon") == "east claydon"
    assert site_key("Trent Valley South Connection Node D 400kV Substation") == (
        "trent valley south connection node d"
    )


def test_gb_type_takes_the_first_listed_technology() -> None:
    assert gb_type("Energy Storage System;PV Array (Photo Voltaic/solar)") == "Storage"
    assert gb_type("PV Array (Photo Voltaic/solar)") == "Solar"
    assert gb_type("Demand;Energy Storage System") == "Demand"
    assert gb_type("CCGT (Combined Cycle Gas Turbine)") == "Gas"
    assert gb_type("Pumped Storage Hydro") == "Other"
