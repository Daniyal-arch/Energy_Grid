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
        "prices": {"DE-LU": {"unix_seconds": q, "price": [float(k) for k in range(192)]}},
        "power": {
            "DE": {
                "unix_seconds": q,
                "production_types": [
                    {"name": "Wind onshore", "data": [1.0] * 192},
                    {"name": "Wind offshore", "data": [2.0] * 192},
                    {"name": "Load", "data": [5.0] * 192},
                ],
            }
        },
        "flows": {"FR>DE": {"unix_seconds": q, "values": [500.0] * 192}},
    }
    second = day_payload(date(2026, 9, 25), raw)
    assert second["slots"] == 96
    assert second["prices"]["DE-LU"]["values"][0] == 96.0  # first slot of the second day
    assert second["countries"]["DE"]["generation"]["wind"][0] == 3.0  # onshore + offshore
    assert second["eu"]["sum_of"] == ["DE"]  # the EU members with data that day, summed
    assert second["eu"]["generation"]["wind"][:2] == [3.0, 3.0]
    assert second["borders"] == [{"a": "FR", "b": "DE", "values": [500.0] * 96}]
    assert second["highlights"]  # key moments computed for the day


def test_series_of_fills_a03_curves_and_coarse_resolutions():
    import xml.etree.ElementTree as ET
    from datetime import UTC, datetime

    from entsoe import Grid, series_of

    doc = """<GL_MarketDocument xmlns="urn:x"><TimeSeries><curveType>A03</curveType>
      <Period><timeInterval><start>2026-10-01T00:00Z</start><end>2026-10-01T02:00Z</end></timeInterval>
      <resolution>PT60M</resolution>
      <Point><position>1</position><quantity>10</quantity></Point>
      </Period></TimeSeries><TimeSeries><curveType>A01</curveType>
      <Period><timeInterval><start>2026-10-01T00:00Z</start><end>2026-10-01T00:30Z</end></timeInterval>
      <resolution>PT15M</resolution>
      <Point><position>1</position><quantity>1</quantity></Point>
      <Point><position>2</position><quantity>2</quantity></Point>
      </Period></TimeSeries></GL_MarketDocument>"""
    t0 = datetime(2026, 10, 1, tzinfo=UTC)
    grid = Grid(t0, t0.replace(hour=3))
    (_, hourly), (_, quarter) = series_of(ET.fromstring(doc), "quantity", grid)
    # one A03 point holds to the period end; an hourly value fills four 15-min slots
    assert hourly == [10.0] * 8 + [None] * 4
    assert quarter == [1.0, 2.0] + [None] * 10


def test_eu_sum_waits_for_every_member():
    from datetime import UTC, datetime

    from entsoe import eu_sum

    t0 = int(datetime(2026, 10, 1, tzinfo=UTC).timestamp())

    def country(load, solar, gas):
        return {
            "unix_seconds": [t0, t0 + 900, t0 + 1800],
            "production_types": [
                {"name": "Solar", "data": solar},
                {"name": "Fossil gas", "data": gas},
                {"name": "Load", "data": load},
            ],
        }

    eu = eu_sum(
        {
            "DE": country([10.0, 10.0, 10.0], [3.0, 3.0, 3.0], [1.0, 1.0, 1.0]),
            "FR": country([20.0, 20.0, None], [1.0, None, 1.0], [3.0, 3.0, 3.0]),
            "PL": country([None, None, None], [None, None, None], [None, None, None]),
        }
    )
    assert eu is not None and eu["sum_of"] == ["DE", "FR"]  # PL has no load: not a member
    cols = {t["name"]: t["data"] for t in eu["production_types"]}
    assert cols["Load"] == [30.0, 30.0, None]  # FR has no load in slot 3
    assert cols["Solar"] == [4.0, 3.0, None]  # FR reports no solar in slot 2: adds nothing
    assert cols["Renewable share of generation"] == [50.0, 42.9, None]
