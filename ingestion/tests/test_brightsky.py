"""Bright Sky adapter smoke test with the HTTP call mocked (respx)."""

from datetime import date
from uuid import uuid4

import respx
from app.models import Site
from httpx import Response
from ingestion.base import RunContext
from ingestion.sources.brightsky import API_URL, BrightSkySource

PAYLOAD = {
    "weather": [
        {
            "timestamp": "2026-06-01T00:00:00+00:00",
            "temperature": 10.0,
            "precipitation": 0.0,
            "icon": "clear-night",
            "condition": "dry",
        },
        {
            "timestamp": "2026-06-01T12:00:00+00:00",
            "temperature": 20.0,
            "precipitation": 1.5,
            "icon": "rain",
            "condition": "rain",
        },
        {
            "timestamp": "2026-06-02T12:00:00+00:00",
            "temperature": -1.0,
            "precipitation": 0.4,
            "icon": "snow",
            "condition": "snow",
        },
    ]
}


def _site() -> Site:
    return Site(
        id=uuid4(),
        name="Test Park",
        geom_wkt="",
        capacity_mw=10.0,
        state="Bayern",
        lat=48.1,
        lon=11.5,
    )


@respx.mock
def test_fetch_and_transform_daily_aggregation():
    respx.get(API_URL).mock(return_value=Response(200, json=PAYLOAD))
    source = BrightSkySource()
    ctx = RunContext(db=None, since=date(2026, 6, 1), until=date(2026, 6, 2), sites=[_site()])

    raw = list(source.fetch(ctx))
    assert len(raw) == 1

    days = list(source.transform(raw))
    assert len(days) == 2

    day1 = days[0]
    assert day1.date == date(2026, 6, 1)
    assert day1.rain_mm == 1.5
    assert day1.temp_c == 15.0
    assert day1.snow is False

    day2 = days[1]
    assert day2.snow is True


def test_sites_without_centroid_are_skipped():
    site = _site()
    site.lat = None
    ctx = RunContext(db=None, sites=[site])
    assert list(BrightSkySource().fetch(ctx)) == []
