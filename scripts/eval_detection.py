"""Evaluate detection-date plausibility against registry commissioning dates.

For the 50 pilot solar sites, a real construction clearing should land in the months
before commissioning (build typically 6-24 months). Reports the gap distribution and
the share of plausible detections. Run before/after tuning to see the effect.

Run: uv run python scripts/eval_detection.py
"""

from __future__ import annotations

import statistics
from datetime import date

from app.db import get_db


def _months(a: date, b: date) -> float:
    return (a.year - b.year) * 12 + (a.month - b.month) + (a.day - b.day) / 30.0


def main() -> None:
    db = get_db()
    sites = (
        db.table("sites_with_centroid")
        .select("id, name, commissioning_date")
        .eq("technology", "solar")
        .gte("commissioning_date", "2022-01-01")
        .order("commissioning_date", desc=True)
        .limit(50)
        .execute()
        .data
    )
    gaps: list[float] = []
    plausible = early = late = no_clearing = 0
    for s in sites:
        if not s["commissioning_date"]:
            continue
        comm = date.fromisoformat(s["commissioning_date"])
        dets = (
            db.table("detections")
            .select("detected_at, to_state")
            .eq("site_id", s["id"])
            .eq("to_state", "clearing")
            .order("detected_at")
            .execute()
            .data
        )
        if not dets:
            no_clearing += 1
            continue
        clearing = date.fromisoformat(dets[0]["detected_at"])
        gap = _months(comm, clearing)  # +ve = clearing before commissioning (expected)
        gaps.append(gap)
        if 0 <= gap <= 30:
            plausible += 1
        elif gap > 30:
            early += 1  # clearing implausibly long before commissioning
        else:
            late += 1  # clearing after commissioning

    n = len(gaps)
    print(f"sites evaluated: {len(sites)} | with clearing: {n} | no clearing: {no_clearing}")
    if n:
        print(f"gap commissioning - clearing (months): "
              f"median {statistics.median(gaps):.1f}, "
              f"min {min(gaps):.1f}, max {max(gaps):.1f}")
        print(f"  plausible (0-30 mo before commissioning): {plausible}/{n} "
              f"({100 * plausible / n:.0f}%)")
        print(f"  implausibly early (>30 mo): {early}")
        print(f"  after commissioning (<0): {late}")


if __name__ == "__main__":
    main()
