"""US EV fast chargers (scripts/fetch_ev_chargers.py): points, state and network sums."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fetch_ev_chargers as f  # noqa: E402


def _s(name: str, state: str, dc: int | None, l2: int | None, net: str, opened: str | None) -> dict:
    return {
        "station_name": name,
        "state": state,
        "ev_dc_fast_num": dc,
        "ev_level2_evse_num": l2,
        "ev_network": net,
        "open_date": opened,
        "longitude": -100.123456789,
        "latitude": 40.987654321,
    }


def test_fast_drawn_level2_counted() -> None:
    out = f.build(
        [
            _s("A", "CA", 8, None, "Tesla", "2021-05-01"),
            _s("B", "CA", None, 4, "ChargePoint Network", "2019-01-01"),
            _s("C", "TX", 2, 2, "Electrify America", None),
            _s("D", "TX", 4, None, "Tesla", "2024-02-02"),
        ]
    )
    assert out["networks"] == ["Tesla", "Electrify America"]
    assert out["names"] == ["A", "C", "D"]
    assert out["points"][0] == [-100.12346, 40.98765, 8, 0, 2021]
    assert out["points"][1][3:] == [1, None]
    assert out["states"] == {"CA": [2, 1, 4, 8], "TX": [2, 2, 2, 6]}
    assert out["total"] == [4, 3, 6, 14]
    assert out["by_network"] == [["Tesla", 2, 12], ["Electrify America", 1, 2]]
