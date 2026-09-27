"""Energy-Charts adapter smoke test with the three API calls mocked (respx).

The one thing a regression here would be invisible without a test: the
emission-factor weighted-average math in transform().
"""

from datetime import UTC, date, datetime

import respx
from httpx import Response
from ingestion.base import RunContext
from ingestion.sources.energycharts import EMISSION_FACTORS, EnergyChartsSource

SEC = int(datetime(2026, 6, 1, 12, tzinfo=UTC).timestamp())


def _mock_power(production_types: list[dict]) -> None:
    respx.get(url__regex=r".*/public_power.*").mock(
        return_value=Response(
            200, json={"unix_seconds": [SEC], "production_types": production_types}
        )
    )
    respx.get(url__regex=r".*/price.*").mock(
        return_value=Response(
            200, json={"unix_seconds": [SEC], "price": [80.0], "unit": "EUR / MWh"}
        )
    )
    respx.get(url__regex=r".*/cbpf.*").mock(
        return_value=Response(
            200,
            json={
                "unix_seconds": [SEC],
                # "sum" is a total-flow pseudo-row the live API includes, not a real
                # neighbor — regression-tested below since it's invisible otherwise.
                "countries": [{"name": "France", "data": [0.5]}, {"name": "sum", "data": [0.5]}],
            },
        )
    )


@respx.mock
def test_all_lignite_mix_yields_high_carbon_intensity():
    _mock_power([{"name": "Fossil brown coal / lignite", "data": [1000.0]}])
    source = EnergyChartsSource()
    ctx = RunContext(db=None, since=date(2026, 6, 1), until=date(2026, 6, 1))

    rows = list(source.transform(source.fetch(ctx)))
    ci = next(r for r in rows if getattr(r, "metric", None) == "carbon_intensity")
    assert ci.value == EMISSION_FACTORS["lignite"]
    assert ci.source == "energy-charts:computed"
    renewable = next(r for r in rows if getattr(r, "metric", None) == "renewable_share")
    carbon_free = next(r for r in rows if getattr(r, "metric", None) == "carbon_free_share")
    assert renewable.value == 0.0
    assert carbon_free.value == 0.0


@respx.mock
def test_all_wind_mix_yields_low_carbon_intensity():
    _mock_power([{"name": "Wind onshore", "data": [1000.0]}])
    source = EnergyChartsSource()
    ctx = RunContext(db=None, since=date(2026, 6, 1), until=date(2026, 6, 1))

    rows = list(source.transform(source.fetch(ctx)))
    ci = next(r for r in rows if getattr(r, "metric", None) == "carbon_intensity")
    assert ci.value == EMISSION_FACTORS["wind"]
    renewable = next(r for r in rows if getattr(r, "metric", None) == "renewable_share")
    carbon_free = next(r for r in rows if getattr(r, "metric", None) == "carbon_free_share")
    assert renewable.value == 100.0
    assert carbon_free.value == 100.0


@respx.mock
def test_mixed_fuel_renewable_and_carbon_free_diverge_on_nuclear():
    _mock_power(
        [
            {"name": "Nuclear", "data": [500.0]},
            {"name": "Wind onshore", "data": [500.0]},
            {"name": "Fossil gas", "data": [1000.0]},
        ]
    )
    source = EnergyChartsSource()
    ctx = RunContext(db=None, since=date(2026, 6, 1), until=date(2026, 6, 1))

    rows = list(source.transform(source.fetch(ctx)))
    renewable = next(r for r in rows if getattr(r, "metric", None) == "renewable_share")
    carbon_free = next(r for r in rows if getattr(r, "metric", None) == "carbon_free_share")
    assert renewable.value == 25.0  # 500 wind / 2000 total
    assert carbon_free.value == 50.0  # (500 nuclear + 500 wind) / 2000 total


@respx.mock
def test_price_and_flow_rows_pass_through():
    _mock_power([{"name": "Solar", "data": [500.0]}])
    source = EnergyChartsSource()
    ctx = RunContext(db=None, since=date(2026, 6, 1), until=date(2026, 6, 1))

    rows = list(source.transform(source.fetch(ctx)))
    price = next(r for r in rows if getattr(r, "metric", None) == "price_eur_mwh")
    assert price.value == 80.0 and price.source == "energy-charts"

    flows = [r for r in rows if hasattr(r, "neighbor_zone")]
    assert [f.neighbor_zone for f in flows] == ["France"]  # "sum" pseudo-row excluded
    assert flows[0].value_mw == 500.0  # 0.5 GW -> 500 MW


def test_published_renewable_share_passes_through():
    ts = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)
    rows = list(EnergyChartsSource().transform([{"kind": "share", "ts": ts, "pct": 87.1}]))
    assert len(rows) == 1
    assert rows[0].metric == "renewable_share_of_generation"
    assert rows[0].value == 87.1
    assert rows[0].source == "energy-charts"
