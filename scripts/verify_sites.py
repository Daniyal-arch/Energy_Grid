"""Verify the loaded sites: counts by technology and registry status, capacity range."""

from collections import Counter

from app.db import get_db


def main() -> None:
    db = get_db()
    total = db.table("sites").select("id", count="exact").execute().count
    print(f"total sites: {total}\n")

    rows = []
    page = 0
    while True:
        batch = (
            db.table("sites")
            .select("technology, mastr_status, capacity_mw, unit_count")
            .range(page * 1000, page * 1000 + 999)
            .execute()
            .data
        )
        rows.extend(batch)
        if len(batch) < 1000:
            break
        page += 1
    by_tech = Counter(r["technology"] for r in rows)
    print("by technology:")
    for tech, n in by_tech.most_common():
        caps = [r["capacity_mw"] for r in rows if r["technology"] == tech]
        print(f"  {tech:12} {n:>5}   capacity MW: min {min(caps):.1f}  max {max(caps):.0f}")

    print("\nby registry status:")
    for status, n in Counter(r["mastr_status"] for r in rows).most_common():
        print(f"  {str(status):28} {n:>5}")

    windfarms = [r for r in rows if r["technology"] == "wind"]
    if windfarms:
        turbines = sum(r["unit_count"] for r in windfarms)
        print(
            f"\nwind: {len(windfarms)} farms from {turbines} turbines "
            f"(avg {turbines / len(windfarms):.1f} turbines/farm)"
        )


if __name__ == "__main__":
    main()
