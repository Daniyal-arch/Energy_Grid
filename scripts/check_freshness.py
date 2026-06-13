"""How fresh is our satellite data? Latest observation date + recent volume."""

from datetime import date, timedelta

from app.db import get_db


def main() -> None:
    db = get_db()
    latest = (
        db.table("timeseries").select("date").order("date", desc=True).limit(1).execute().data
    )
    earliest = db.table("timeseries").select("date").order("date").limit(1).execute().data
    print(f"earliest observation: {earliest[0]['date'] if earliest else '—'}")
    print(f"latest observation:   {latest[0]['date'] if latest else '—'}")

    cutoff = (date.today() - timedelta(days=30)).isoformat()
    recent = (
        db.table("timeseries")
        .select("id", count="exact")
        .gte("date", cutoff)
        .limit(1)
        .execute()
    )
    print(f"observations in the last 30 days: {recent.count}")

    # latest detection (state change)
    det = (
        db.table("detections")
        .select("detected_at, to_state")
        .order("detected_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if det:
        print(f"most recent detected transition: {det[0]['detected_at']} -> {det[0]['to_state']}")


if __name__ == "__main__":
    main()
