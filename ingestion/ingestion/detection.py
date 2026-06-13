"""Rule-based per-site construction state machine.

Pure logic (no I/O) so it is unit-testable. Reads merged satellite observations and
emits state transitions with evidence:

    no_activity -> clearing -> earthworks -> construction -> complete

Signals (vs. a same-month seasonal baseline from the first year of data):
  * clearing      NDVI drops (vegetation removed)              [Sentinel-2]
  * earthworks    BSI rises (bare soil exposed)                [Sentinel-2]
  * construction  VH backscatter rises (structures/panels)     [Sentinel-1]
  * complete      NDVI low + VH elevated, stable for months    [S2 + S1]

Guards against false alarms: a same-season baseline (not raw year-vs-recent), a
persistence rule (N consecutive confirming observations), optional weather masking
of optical scenes (handled by the caller), and dual-sensor confidence.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.models import Confidence, SiteState

# Ordered states for monotonic forward progression.
STATE_ORDER = [
    SiteState.NO_ACTIVITY,
    SiteState.CLEARING,
    SiteState.EARTHWORKS,
    SiteState.CONSTRUCTION,
    SiteState.COMPLETE,
]


@dataclass(frozen=True)
class Obs:
    """One satellite observation of a single metric."""

    date: date
    sensor: str  # 's2' | 's1'
    metric: str  # 'ndvi' | 'bsi' | 'vh_db'
    value: float
    scene_id: str | None = None


@dataclass
class Transition:
    detected_at: date
    from_state: SiteState
    to_state: SiteState
    confidence: Confidence
    evidence: list[Obs] = field(default_factory=list)


@dataclass(frozen=True)
class Params:
    baseline_days: int = 365  # first year defines the seasonal baseline
    persistence: int = 3  # consecutive confirming observations required
    ndvi_drop: float = 0.10  # NDVI anomaly <= -this => clearing
    bsi_rise: float = 0.08  # BSI anomaly >= this => earthworks
    vh_rise: float = 1.5  # VH anomaly (dB) >= this => construction
    dual_window_days: int = 90  # S2/S1 agreement window for high confidence
    complete_days: int = 180  # sustained settled signal => complete


def _seasonal_baseline(obs: list[Obs], baseline_days: int) -> dict[int, float] | None:
    """Per-calendar-month median over the first `baseline_days` of a metric series."""
    if not obs:
        return None
    start = obs[0].date
    cutoff = start + timedelta(days=baseline_days)
    by_month: dict[int, list[float]] = {}
    for o in obs:
        if o.date < cutoff:
            by_month.setdefault(o.date.month, []).append(o.value)
    if not by_month:
        return None
    overall = statistics.median([v for vs in by_month.values() for v in vs])
    # fall back to the overall median for months with no baseline sample
    return {m: (statistics.median(by_month[m]) if m in by_month else overall) for m in range(1, 13)}


def _first_sustained(
    obs: list[Obs],
    baseline: dict[int, float],
    predicate,  # noqa: ANN001 — callable(anomaly) -> bool
    persistence: int,
    after: date | None = None,
) -> tuple[date, list[Obs]] | None:
    """First date where `predicate(anomaly)` holds for `persistence` consecutive obs."""
    run: list[Obs] = []
    for o in obs:
        if after and o.date < after:
            continue
        anomaly = o.value - baseline[o.date.month]
        if predicate(anomaly):
            run.append(o)
            if len(run) >= persistence:
                return run[0].date, list(run[:persistence])
        else:
            run = []
    return None


DEFAULT_PARAMS = Params()


def detect_transitions(
    ndvi: list[Obs],
    bsi: list[Obs],
    vh: list[Obs],
    params: Params | None = None,
) -> list[Transition]:
    """Run the state machine over one site's metric series (each sorted by date)."""
    params = params or DEFAULT_PARAMS
    ndvi = sorted(ndvi, key=lambda o: o.date)
    bsi = sorted(bsi, key=lambda o: o.date)
    vh = sorted(vh, key=lambda o: o.date)

    ndvi_base = _seasonal_baseline(ndvi, params.baseline_days)
    bsi_base = _seasonal_baseline(bsi, params.baseline_days)
    vh_base = _seasonal_baseline(vh, params.baseline_days)
    if ndvi_base is None:
        return []

    clearing = _first_sustained(
        ndvi, ndvi_base, lambda a: a <= -params.ndvi_drop, params.persistence
    )
    clearing_date = clearing[0] if clearing else None

    earthworks = (
        _first_sustained(
            bsi, bsi_base, lambda a: a >= params.bsi_rise, params.persistence, after=clearing_date
        )
        if bsi_base and clearing_date
        else None
    )
    construction = (
        _first_sustained(
            vh, vh_base, lambda a: a >= params.vh_rise, params.persistence, after=clearing_date
        )
        if vh_base and clearing_date
        else None
    )

    # complete: after construction, NDVI stays low and VH stays elevated, stable for
    # complete_days. Approximated as a sustained low-NDVI run whose span >= complete_days.
    complete_date: date | None = None
    complete_ev: list[Obs] = []
    anchor = (construction or earthworks or clearing or (None, None))[0]
    if anchor:
        low_run: list[Obs] = []
        for o in ndvi:
            if o.date < anchor:
                continue
            if o.value - ndvi_base[o.date.month] <= -params.ndvi_drop:
                low_run.append(o)
                if (low_run[-1].date - low_run[0].date).days >= params.complete_days:
                    complete_date = low_run[-1].date
                    complete_ev = [low_run[0], low_run[-1]]
                    break
            else:
                low_run = []

    # assemble candidate (to_state, date, evidence) in detection order
    candidates: list[tuple[SiteState, date, list[Obs]]] = []
    if clearing:
        candidates.append((SiteState.CLEARING, clearing[0], clearing[1]))
    if earthworks:
        candidates.append((SiteState.EARTHWORKS, earthworks[0], earthworks[1]))
    if construction:
        candidates.append((SiteState.CONSTRUCTION, construction[0], construction[1]))
    if complete_date:
        candidates.append((SiteState.COMPLETE, complete_date, complete_ev))

    # emit monotonic forward transitions (never regress past states)
    transitions: list[Transition] = []
    current = SiteState.NO_ACTIVITY
    has_s1 = construction is not None
    for to_state, when, ev in sorted(candidates, key=lambda c: STATE_ORDER.index(c[0])):
        if STATE_ORDER.index(to_state) <= STATE_ORDER.index(current):
            continue
        # high confidence when both an optical and a radar signal support the build
        confidence = Confidence.HIGH if has_s1 and clearing else Confidence.MEDIUM
        transitions.append(Transition(when, current, to_state, confidence, ev))
        current = to_state
    return transitions
