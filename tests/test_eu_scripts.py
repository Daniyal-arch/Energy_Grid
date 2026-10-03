"""Unit tests for the pure helpers of the data scripts (no network)."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_eu_day import align, day_window  # noqa: E402
from fetch_eu_snapshot import newest_complete_index  # noqa: E402


def test_newest_complete_index_skips_partial_last_interval():
    # the last interval: one series missing, one dropped from a non-zero value to 0
    a = [1.0, 2.0, 3.0, None]
    b = [5.0, 6.0, 7.0, 0.0]
    assert newest_complete_index([a, b]) == 2


def test_newest_complete_index_keeps_idle_zero():
    # a zero after a zero is a real idle reading, not a gap
    assert newest_complete_index([[0.0, 0.0, 0.0]]) == 2


def test_align_puts_values_on_the_15_min_grid():
    start = 1_000_000 - (1_000_000 % 900)
    seconds = [start, start + 900, start + 1800]
    assert align(seconds, [1.0, None, 3.0], start, 4) == [1.0, None, 3.0, None]


def test_align_spreads_hourly_values_over_four_slots():
    start = 3600 * 100
    assert align([start, start + 3600], [10.0, 20.0], start, 8) == [10.0] * 4 + [20.0] * 4


def test_day_window_follows_daylight_saving():
    assert day_window(date(2026, 9, 24))[1] == 96
    assert day_window(date(2026, 3, 29))[1] == 92  # clocks go forward
    assert day_window(date(2026, 10, 25))[1] == 100  # clocks go back
    start, _ = day_window(date(2026, 9, 24))
    assert start.isoformat() == "2026-09-23T22:00:00+00:00"  # local midnight, CEST
