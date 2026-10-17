"""US node prices: the ET day, placement, spreads per market (scripts/fetch_us_nodes.py)."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_us_nodes import build, day_window  # noqa: E402


def test_day_window_follows_daylight_saving() -> None:
    start, slots = day_window(date(2026, 10, 15))
    assert start == datetime(2026, 10, 15, 4, tzinfo=UTC) and slots == 24
    assert day_window(date(2026, 11, 1))[1] == 25
    assert day_window(date(2026, 3, 8))[1] == 23


def test_build_places_caiso_nodes_and_summarises_each_market() -> None:
    t = datetime(2026, 10, 15, 4, tzinfo=UTC)
    rows = {
        "CAISO": [
            (0, "A_N1", "Node", 10.0, None, None, None, t),
            (0, "B_N2", "Node", 30.0, None, None, None, t),
            (1, "A_N1", "Node", 12.5, None, None, None, t),
        ],
        "ERCOT": [(0, "HB_HOUSTON", "Trading Hub", 25.0, None, None, None, t)],
    }
    positions = {"A_N1": (-120.0, 36.0, "CA")}
    out = build(date(2026, 10, 15), rows, positions, "2026-10-17T00:00:00+00:00")
    assert out["slots"] == 24
    assert out["nodes"] == [[-120.0, 36.0, "A_N1", "CA"]]
    assert out["prices"][0][:2] == [10.0, 12.5] and out["prices"][0][2] is None
    assert out["markets"]["CAISO"]["nodes"] == 2 and out["markets"]["CAISO"]["placed"] == 1
    assert out["markets"]["CAISO"]["hours"][0] == [10.0, 12.0, 20.0, 28.0, 30.0]
    assert out["markets"]["ERCOT"]["placed"] == 0 and out["markets"]["ERCOT"]["hours"][1] is None
