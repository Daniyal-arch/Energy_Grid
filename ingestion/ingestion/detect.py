"""Detection pipeline: read stored timeseries -> run the state machine -> write
`detections` + `evidence` rows (provenance the agent later cites) and update site status.

Not a data source (no external fetch) — it is the analysis step between ingestion and
the agent. CLI mirrors run.py's site selection.

    python -m ingestion.detect --technology solar --limit 50
    python -m ingestion.detect --site-id <uuid>
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta

from app.db import get_db

from ingestion.detection import Obs, Params, Transition, detect_transitions
from ingestion.run import _load_sites
from supabase import Client

log = logging.getLogger("detect")

_METRIC_SENSOR = {"ndvi": "s2", "bsi": "s2", "vh_db": "s1"}


def _obs(db: Client, site_id: str, metric: str) -> list[Obs]:
    rows = (
        db.table("timeseries")
        .select("date, value, scene_id")
        .eq("site_id", site_id)
        .eq("metric", metric)
        .order("date")
        .execute()
        .data
    )
    sensor = _METRIC_SENSOR[metric]
    return [
        Obs(date.fromisoformat(r["date"]), sensor, metric, r["value"], r.get("scene_id"))
        for r in rows
    ]


def _snow_days(db: Client, site_id: str) -> set[date]:
    rows = (
        db.table("weather")
        .select("date, snow")
        .eq("site_id", site_id)
        .eq("snow", True)
        .execute()
        .data
    )
    return {date.fromisoformat(r["date"]) for r in rows}


def _write(db: Client, site_id: str, transitions: list[Transition]) -> None:
    # idempotent: replace any prior detection output for this site
    db.table("detections").delete().eq("site_id", site_id).execute()
    db.table("evidence").delete().eq("site_id", site_id).execute()
    if not transitions:
        # analysed but no construction signal -> no_activity (distinct from unanalysed 'unknown')
        db.table("sites").update({"status": "no_activity", "status_since": None}).eq(
            "id", site_id
        ).execute()
        return

    for t in transitions:
        ev_rows = [
            {
                "site_id": site_id,
                "scene_id": o.scene_id or f"{o.sensor}:{o.date.isoformat()}",
                "sensor": o.sensor,
                "acquired_at": o.date.isoformat(),
                "metrics": {o.metric: o.value},
            }
            for o in t.evidence
        ]
        ev_ids: list[str] = []
        if ev_rows:
            inserted = db.table("evidence").insert(ev_rows).execute().data
            ev_ids = [r["id"] for r in inserted]
        db.table("detections").insert(
            {
                "site_id": site_id,
                "detected_at": t.detected_at.isoformat(),
                "from_state": t.from_state.value,
                "to_state": t.to_state.value,
                "confidence": t.confidence.value,
                "evidence_ids": ev_ids,
            }
        ).execute()

    last = transitions[-1]
    db.table("sites").update(
        {"status": last.to_state.value, "status_since": last.detected_at.isoformat()}
    ).eq("id", site_id).execute()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run construction detection over stored timeseries."
    )
    parser.add_argument("--site-id", default=None)
    parser.add_argument("--technology", default=None)
    parser.add_argument("--mastr-status", default=None)
    parser.add_argument("--commissioned-after", type=date.fromisoformat, default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    db = get_db()
    sites = _load_sites(
        db,
        site_id=args.site_id,
        technology=args.technology,
        mastr_status=args.mastr_status,
        commissioned_after=args.commissioned_after,
        limit=args.limit,
    )
    params = Params()
    n_sites = n_detected = n_transitions = 0
    for site in sites:
        sid = str(site.id)
        ndvi, bsi, vh = (_obs(db, sid, m) for m in ("ndvi", "bsi", "vh_db"))
        if not ndvi:
            continue
        n_sites += 1
        snow = _snow_days(db, sid)
        if snow:
            ndvi = [o for o in ndvi if o.date not in snow]
            bsi = [o for o in bsi if o.date not in snow]
        # Construction precedes operation: for a commissioned site, ignore observations
        # well past commissioning so a later vegetation shift can't be mistaken for a build.
        if site.commissioning_date:
            bound = site.commissioning_date + timedelta(days=180)
            ndvi = [o for o in ndvi if o.date <= bound]
            bsi = [o for o in bsi if o.date <= bound]
            vh = [o for o in vh if o.date <= bound]
        transitions = detect_transitions(ndvi, bsi, vh, params)
        _write(db, sid, transitions)
        if transitions:
            n_detected += 1
            n_transitions += len(transitions)
            log.info("%s: %s", site.name, " -> ".join(t.to_state.value for t in transitions))
    log.info(
        "done: %d sites analysed, %d with detections, %d transitions",
        n_sites,
        n_detected,
        n_transitions,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
