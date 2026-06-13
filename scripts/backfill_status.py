"""Show backfill progress: total sites with timeseries, and In-Planung solar coverage."""

from app.db import get_db


def main() -> None:
    db = get_db()
    done = set()
    page = 0
    while True:
        b = (
            db.table("backfilled_sites")
            .select("site_id")
            .range(page * 1000, page * 1000 + 999)
            .execute()
            .data
            or []
        )
        done.update(r["site_id"] for r in b)
        if len(b) < 1000:
            break
        page += 1

    inpl = (
        db.table("sites")
        .select("id")
        .eq("technology", "solar")
        .eq("mastr_status", "In Planung")
        .range(0, 999)
        .execute()
        .data
    )
    inpl_ids = {r["id"] for r in inpl}
    done_inpl = len(inpl_ids & done)
    print(f"total sites with satellite timeseries: {len(done)}")
    print(
        f"In Planung solar: {len(inpl_ids)} total, {done_inpl} done, "
        f"{len(inpl_ids) - done_inpl} remaining for the cloud run"
    )


if __name__ == "__main__":
    main()
