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


def test_day_payload_cuts_one_day_from_a_multi_day_window():
    from build_eu_day import day_payload

    first, _ = day_window(date(2026, 9, 24))
    t0 = int(first.timestamp())
    q = [t0 + 900 * k for k in range(192)]  # two days of 15-min stamps
    raw = {
        "eu": {
            "unix_seconds": [t0 + 3600 * h for h in range(48)],
            "production_types": [
                {"name": "Solar", "data": [float(h) for h in range(48)]},
                {"name": "Load", "data": [1000.0 + h for h in range(48)]},
            ],
        },
        "prices": {"DE-LU": {"unix_seconds": q, "price": [float(k) for k in range(192)]}},
        "power": {
            "de": {
                "unix_seconds": q,
                "production_types": [
                    {"name": "Wind onshore", "data": [1.0] * 192},
                    {"name": "Wind offshore", "data": [2.0] * 192},
                    {"name": "Load", "data": [5.0] * 192},
                ],
            }
        },
        "cbpf": {"de": {"unix_seconds": q, "countries": [{"name": "France", "data": [0.5] * 192}]}},
    }
    second = day_payload(date(2026, 9, 25), raw)
    assert second["slots"] == 96
    assert second["prices"]["DE-LU"]["values"][0] == 96.0  # first slot of the second day
    assert second["countries"]["DE"]["generation"]["wind"][0] == 3.0  # onshore + offshore
    assert second["eu"]["generation"]["solar"][:4] == [24.0] * 4  # hourly value fills 4 slots
    assert second["borders"] == [{"a": "FR", "b": "DE", "values": [500.0] * 96}]
    assert second["highlights"]  # key moments computed for the day
