"""Verify SMARD generation data: coverage, latest date, sample values."""

from collections import Counter

from app.db import get_db


def main() -> None:
    db = get_db()
    rows = (
        db.table("power_output")
        .select("plant_id, date, mwh")
        .eq("source", "smard")
        .order("date", desc=True)
        .limit(2000)
        .execute()
        .data
    )
    print(f"smard rows: {len(rows)}")
    print("by technology:", dict(Counter(r["plant_id"] for r in rows)))
    if rows:
        print(f"latest date: {rows[0]['date']}")
        print("\nmost recent German solar (DE-solar) daily generation:")
        for r in [x for x in rows if x["plant_id"] == "DE-solar"][:5]:
            print(f"  {r['date']}  {r['mwh'] / 1000:,.1f} GWh")


if __name__ == "__main__":
    main()
