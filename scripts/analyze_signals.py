"""Empirical signal characterisation per technology, to ground per-type detection.

For a sample of In-Planung sites per technology, compare the first-year baseline to
the recent year for each metric (NDVI / BSI / VH). Shows which signal actually moves
during construction for each tech — e.g. is wind NDVI-clearing or VH-driven?
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, timedelta

from app.db import get_db

db = get_db()
TECHS = ["solar", "wind", "storage", "combustion", "biomass", "hydro"]
N = 30


def sample(tech: str) -> list[dict]:
    return (
        db.table("sites_with_centroid")
        .select("id,status")
        .eq("technology", tech)
        .eq("mastr_status", "In Planung")
        .limit(N)
        .execute()
        .data
        or []
    )


def series(sid: str, metric: str) -> list[tuple[date, float]]:
    rows = (
        db.table("timeseries").select("date,value")
        .eq("site_id", sid).eq("metric", metric).order("date").execute().data
        or []
    )
    return [(date.fromisoformat(r["date"]), r["value"]) for r in rows]


print(f"{'tech':11} {'n':>3}  {'ΔNDVI':>8} {'ΔBSI':>8} {'ΔVH(dB)':>8}   (recent-year median − first-year median)")
for tech in TECHS:
    deltas: dict[str, list[float]] = defaultdict(list)
    sites = sample(tech)
    for s in sites:
        for metric in ("ndvi", "bsi", "vh_db"):
            ser = series(s["id"], metric)
            if len(ser) < 25:
                continue
            t0, tN = ser[0][0], ser[-1][0]
            base = [v for d, v in ser if d < t0 + timedelta(days=365)]
            recent = [v for d, v in ser if d > tN - timedelta(days=365)]
            if len(base) >= 5 and len(recent) >= 5:
                deltas[metric].append(statistics.median(recent) - statistics.median(base))

    def med(m: str) -> str:
        return f"{statistics.median(deltas[m]):+.3f}" if deltas[m] else "   —  "

    n = max((len(deltas[m]) for m in deltas), default=0)
    print(f"{tech:11} {n:>3}  {med('ndvi'):>8} {med('bsi'):>8} {med('vh_db'):>8}")
