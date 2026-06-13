"""Verify detection output: status distribution, a sample timeline, evidence linkage."""

from collections import Counter

from app.db import get_db


def main() -> None:
    db = get_db()
    n_det = db.table("detections").select("id", count="exact").execute().count
    n_ev = db.table("evidence").select("id", count="exact").execute().count
    print(f"detections: {n_det}   evidence rows: {n_ev}\n")

    # site status distribution (satellite-derived construction state)
    statuses = Counter(
        r["status"]
        for r in db.table("sites").select("status").neq("status", "unknown").execute().data
    )
    print("site construction status (non-unknown):")
    for s, n in statuses.most_common():
        print(f"  {s:14} {n}")

    # one site's full timeline with evidence
    sid = db.table("detections").select("site_id").limit(1).execute().data[0]["site_id"]
    site = db.table("sites").select("name, capacity_mw, commissioning_date").eq("id", sid).execute().data[0]
    print(f"\nexample timeline — {site['name']} ({site['capacity_mw']} MW, "
          f"commissioned {site['commissioning_date']}):")
    dets = (
        db.table("detections")
        .select("detected_at, from_state, to_state, confidence, evidence_ids")
        .eq("site_id", sid)
        .order("detected_at")
        .execute()
        .data
    )
    for d in dets:
        ev_ids = d["evidence_ids"]
        ev = db.table("evidence").select("scene_id, sensor, metrics").in_("id", ev_ids).execute().data
        cites = "; ".join(f"{e['sensor']}:{e['scene_id'][:18]} {e['metrics']}" for e in ev[:2])
        print(f"  {d['detected_at']}  {d['from_state']:11} -> {d['to_state']:12} [{d['confidence']}]")
        print(f"       evidence: {cites}")


if __name__ == "__main__":
    main()
