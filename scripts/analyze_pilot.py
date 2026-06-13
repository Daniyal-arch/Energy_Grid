"""Validate that the pilot backfill captured a construction signal.

For each backfilled solar site, compare the NDVI/BSI level well before vs. after its
commissioning date. A real ground-mounted build should show NDVI fall and BSI rise
around construction. Prints the clearest examples and flags sites with no signal.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, timedelta

from app.db import get_db


def _series(db, site_id: str, metric: str) -> list[tuple[date, float]]:
    rows = (
        db.table("timeseries")
        .select("date, value")
        .eq("site_id", site_id)
        .eq("metric", metric)
        .order("date")
        .execute()
        .data
    )
    return [(date.fromisoformat(r["date"]), r["value"]) for r in rows]


def _mean_window(series: list[tuple[date, float]], lo: date, hi: date) -> float | None:
    vals = [v for d, v in series if lo <= d < hi]
    return statistics.mean(vals) if vals else None


def main() -> None:
    db = get_db()
    # the same 50 sites the pilot backfilled: recent solar, newest first
    sites = [
        s
        for s in (
            db.table("sites_with_centroid")
            .select("id, name, commissioning_date, capacity_mw")
            .eq("technology", "solar")
            .gte("commissioning_date", "2022-01-01")
            .order("commissioning_date", desc=True)
            .limit(50)
            .execute()
            .data
        )
        if s["commissioning_date"]
    ]

    results = []
    for s in sites:
        comm = date.fromisoformat(s["commissioning_date"])
        ndvi = _series(db, s["id"], "ndvi")
        bsi = _series(db, s["id"], "bsi")
        # baseline: 12-24 months before commissioning; built: 0-12 months after
        pre = _mean_window(ndvi, comm - timedelta(days=730), comm - timedelta(days=365))
        post = _mean_window(ndvi, comm, comm + timedelta(days=365))
        pre_bsi = _mean_window(bsi, comm - timedelta(days=730), comm - timedelta(days=365))
        post_bsi = _mean_window(bsi, comm, comm + timedelta(days=365))
        if None in (pre, post):
            continue
        results.append(
            {
                "name": s["name"][:32],
                "mw": s["capacity_mw"],
                "comm": comm.isoformat(),
                "ndvi_drop": pre - post,
                "bsi_rise": (post_bsi - pre_bsi) if None not in (pre_bsi, post_bsi) else None,
                "n": len(ndvi),
            }
        )

    results.sort(key=lambda r: r["ndvi_drop"], reverse=True)
    print(f"{len(results)} pilot sites with NDVI before+after their commissioning date\n")
    print(f"{'site':34}{'MW':>6}{'commissioned':>14}{'NDVI drop':>11}{'BSI rise':>10}")
    for r in results[:12]:
        bsi = f"{r['bsi_rise']:+.3f}" if r["bsi_rise"] is not None else "  n/a"
        print(f"{r['name']:34}{r['mw']:6.0f}{r['comm']:>14}{r['ndvi_drop']:+11.3f}{bsi:>10}")
    print("  ...")
    drops = [r["ndvi_drop"] for r in results]
    signal = sum(1 for d in drops if d > 0.1)
    print(f"\n{signal}/{len(results)} sites show a clear NDVI drop (>0.10) after commissioning")
    print(f"median NDVI change: {statistics.median(drops):+.3f}")


if __name__ == "__main__":
    main()
