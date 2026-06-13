"""Verify deadlines: counts by type, a sample, and which analysed sites are overdue."""

from collections import Counter
from datetime import date

from app.db import get_db


def _all(table, select, **eq):
    db = get_db()
    rows, page = [], 0
    while True:
        q = db.table(table).select(select)
        for k, v in eq.items():
            q = q.eq(k, v)
        batch = q.range(page * 1000, page * 1000 + 999).execute().data or []
        rows.extend(batch)
        if len(batch) < 1000:
            break
        page += 1
    return rows


def main() -> None:
    db = get_db()
    deadlines = _all("deadlines", "site_id,type,deadline_date,source")
    print(f"deadline rows: {len(deadlines)}")
    print("by type:", dict(Counter(d["type"] for d in deadlines)))

    legal = [d for d in deadlines if d["type"] == "legal_completion"]
    print(f"\nsample legal deadlines:")
    for d in sorted(legal, key=lambda x: x["deadline_date"])[:4]:
        print(f"  {d['deadline_date']}  {d['source']}")

    # overdue among analysed sites (status detected, not complete)
    sites = {
        s["id"]: s
        for s in _all("sites", "id,name,status,capacity_mw")
        if s["status"] not in ("unknown",)
    }
    today = date.today().isoformat()
    overdue = [
        (sites[d["site_id"]], d)
        for d in legal
        if d["site_id"] in sites
        and d["deadline_date"] < today
        and sites[d["site_id"]]["status"] != "complete"
    ]
    print(f"\nanalysed sites with a legal deadline: "
          f"{len({d['site_id'] for d in legal if d['site_id'] in sites})}")
    print(f"BEHIND legal deadline (past due, not detected complete): {len(overdue)}")
    for s, d in overdue[:6]:
        print(f"  {s['name']} [{s['status']}] — due {d['deadline_date']}")


if __name__ == "__main__":
    main()
