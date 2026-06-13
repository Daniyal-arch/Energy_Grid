"""Sanity-check timeseries values for the most recently backfilled site."""

from collections import defaultdict

from app.db import get_db


def main() -> None:
    db = get_db()
    sid = db.table("timeseries").select("site_id").limit(1).execute().data[0]["site_id"]
    site = db.table("sites").select("name, technology, capacity_mw").eq("id", sid).execute().data[0]
    print(f"site: {site['name']} ({site['technology']}, {site['capacity_mw']} MW)\n")

    rows = (
        db.table("timeseries")
        .select("date, sensor, metric, value")
        .eq("site_id", sid)
        .order("date")
        .execute()
        .data
    )
    by_metric: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        by_metric[f"{r['sensor']}/{r['metric']}"].append(r["value"])
    for key, vals in sorted(by_metric.items()):
        print(
            f"  {key:10} n={len(vals):3}  min {min(vals):7.3f}  mean {sum(vals) / len(vals):7.3f}  max {max(vals):7.3f}"
        )

    print("\n  first 6 observations:")
    for r in rows[:6]:
        print(f"    {r['date']}  {r['sensor']:3} {r['metric']:5} {r['value']:.3f}")


if __name__ == "__main__":
    main()
