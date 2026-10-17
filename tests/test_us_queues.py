"""US live queues: type mapping and active sums (scripts/fetch_us_queues.py)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_us_queues import state_of, summarise, types_of  # noqa: E402


def test_types_split_hybrids_only_at_separators() -> None:
    assert types_of("Photovoltaic + Storage") == ["Solar", "Battery"]
    assert types_of("SUN BAT") == ["Solar", "Battery"]
    assert types_of("Hybrid - Solar/Storage") == ["Solar", "Battery"]
    assert types_of("Wind - Wind Turbine") == ["Wind"]
    assert types_of("Offshore Wind") == ["Offshore Wind"]
    assert types_of("Pumped Storage Hydro") == ["Other Storage"]
    assert types_of("Gas - Combined-Cycle") == ["Gas"]
    assert types_of(None) == ["Other"]


def test_summarise_counts_active_requests_per_state_and_type() -> None:
    rows = [
        {"Status": "Active", "Capacity (MW)": 100, "State": "Texas", "Generation Type": "SUN BAT"},
        {"Status": "ACTIVE", "Capacity (MW)": "50", "State": "TX", "Generation Type": "Wind"},
        {"Status": "Withdrawn", "Capacity (MW)": 999, "State": "TX", "Generation Type": "Gas"},
        {"Status": "Active", "Capacity (MW)": float("nan"), "State": None, "Generation Type": None},
    ]
    s = summarise(rows)
    assert s["requests"] == 4 and s["active"] == 3 and s["active_mw"] == 150
    assert s["by_type"] == {"Solar": 100, "Battery": 100, "Wind": 50, "Other": 0}
    assert s["by_state"]["TX"] == {"Solar": 100, "Battery": 100, "Wind": 50}
    assert s["statuses"]["Withdrawn"] == 1
    assert state_of("Texas") == "TX" and state_of("nan") is None
