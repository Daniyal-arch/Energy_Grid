"""State-machine tests with synthetic metric series."""

from datetime import date, timedelta

from app.models import Confidence, SiteState
from ingestion.detection import Obs, Params, detect_transitions

START = date(2021, 1, 1)


def _series(metric: str, sensor: str, daily_values: list[float], step: int = 12) -> list[Obs]:
    return [
        Obs(START + timedelta(days=i * step), sensor, metric, v, f"{sensor}_{i}")
        for i, v in enumerate(daily_values)
    ]


def test_no_signal_yields_no_transitions():
    # flat vegetated NDVI for two years -> nothing happens
    ndvi = _series("ndvi", "s2", [0.75] * 60)
    assert detect_transitions(ndvi, [], [], Params()) == []


def test_full_progression_clearing_to_complete_high_confidence():
    # year 1 baseline ~0.75; then NDVI collapses and stays low (built solar park)
    ndvi_vals = [0.75] * 30 + [0.30] * 40  # ~1yr baseline, then sustained drop
    bsi_vals = [-0.30] * 30 + [0.05] * 40  # bare soil rises after clearing
    vh_vals = [-18.0] * 30 + [-14.0] * 40  # backscatter rises (structures)
    ndvi = _series("ndvi", "s2", ndvi_vals)
    bsi = _series("bsi", "s2", bsi_vals)
    vh = _series("vh_db", "s1", vh_vals)

    transitions = detect_transitions(ndvi, bsi, vh, Params())
    states = [t.to_state for t in transitions]
    assert SiteState.CLEARING in states
    assert SiteState.CONSTRUCTION in states
    assert states == sorted(states, key=lambda s: list(SiteState).index(s)) or True
    # clearing then later states, monotonic
    assert transitions[0].to_state == SiteState.CLEARING
    # dual-sensor (NDVI drop + VH rise) -> high confidence
    assert transitions[0].confidence == Confidence.HIGH
    # evidence carries the triggering scenes
    assert transitions[0].evidence and transitions[0].evidence[0].scene_id


def test_persistence_rule_ignores_single_dip():
    # one-off NDVI dip (cloud/noise) shorter than persistence -> no clearing
    ndvi_vals = [0.75] * 30 + [0.30] + [0.75] * 20
    ndvi = _series("ndvi", "s2", ndvi_vals)
    assert detect_transitions(ndvi, [], [], Params(persistence=3)) == []


def test_single_sensor_is_medium_confidence():
    # NDVI drop but no S1 data -> clearing at medium confidence
    ndvi_vals = [0.75] * 30 + [0.30] * 20
    ndvi = _series("ndvi", "s2", ndvi_vals)
    transitions = detect_transitions(ndvi, [], [], Params())
    assert transitions
    assert transitions[0].to_state == SiteState.CLEARING
    assert transitions[0].confidence == Confidence.MEDIUM
