"""CLI runner: python -m ingestion.run --source <name> [--since ...] [--until ...]

This is the only scheduler-facing entry point. Swapping to Celery / a cloud scheduler
later means replacing this file's __main__ wiring, nothing else.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from app.db import get_db
from app.models import Site

import ingestion.sources  # noqa: F401  (imports trigger adapter registration)
from ingestion.base import RunContext
from ingestion.registry import get_source, list_sources
from supabase import Client

log = logging.getLogger("ingestion")


def _load_sites(
    db: Client,
    site_id: str | None = None,
    technology: str | None = None,
    mastr_status: str | None = None,
    commissioned_after: date | None = None,
    limit: int | None = None,
) -> list[Site]:
    """Load sites for site-scoped adapters, with optional subset filters.

    Paginates past PostgREST's 1000-row cap so a full backfill sees every site.
    """
    rows: list[dict] = []
    page = 0
    while True:
        q = db.table("sites_with_centroid").select("*").order("commissioning_date", desc=True)
        if site_id:
            q = q.eq("id", site_id)
        if technology:
            q = q.eq("technology", technology)
        if mastr_status:
            q = q.eq("mastr_status", mastr_status)
        if commissioned_after:
            q = q.gte("commissioning_date", commissioned_after.isoformat())
        batch = q.range(page * 1000, page * 1000 + 999).execute().data or []
        rows.extend(batch)
        if limit and len(rows) >= limit:
            rows = rows[:limit]
            break
        if len(batch) < 1000:
            break
        page += 1
    return [
        Site(
            id=row["id"],
            mastr_id=row.get("mastr_id"),
            name=row["name"],
            geom_wkt="",  # geometry not needed in WKT form here; adapters use lat/lon or fetch geom
            capacity_mw=row["capacity_mw"],
            state=row["state"],
            owner=row.get("owner"),
            status=row.get("status", "unknown"),
            commissioning_date=row.get("commissioning_date"),
            planned_commissioning_date=row.get("planned_commissioning_date"),
            lat=row.get("lat"),
            lon=row.get("lon"),
        )
        for row in rows
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a gridwatch ingestion source.")
    parser.add_argument("--source", help="adapter name (see --list)")
    parser.add_argument("--list", action="store_true", help="list registered sources")
    parser.add_argument("--since", type=date.fromisoformat, default=None)
    parser.add_argument("--until", type=date.fromisoformat, default=None)
    parser.add_argument("--site-id", default=None, help="restrict to one site UUID")
    parser.add_argument("--technology", default=None, help="subset by technology (e.g. solar)")
    parser.add_argument("--mastr-status", default=None, help="subset by registry status")
    parser.add_argument("--commissioned-after", type=date.fromisoformat, default=None)
    parser.add_argument(
        "--limit", type=int, default=None, help="cap number of sites (backfill subset)"
    )
    parser.add_argument("--dry-run", action="store_true", help="fetch+transform, don't write")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    if args.list:
        for cls in list_sources():
            m = cls.meta
            creds = ", ".join(m.requires_credentials) or "none"
            print(f"{m.name:<16} phase {m.phase}  cadence={m.cadence:<10} creds={creds}")
            print(f"{'':<16} {m.description}")
        return 0

    if not args.source:
        parser.error("--source is required (or use --list)")

    source = get_source(args.source)
    db = get_db()
    sites = (
        _load_sites(
            db,
            site_id=args.site_id,
            technology=args.technology,
            mastr_status=args.mastr_status,
            commissioned_after=args.commissioned_after,
            limit=args.limit,
        )
        if source.meta.site_scoped
        else []
    )
    ctx = RunContext(db=db, since=args.since, until=args.until, sites=sites, dry_run=args.dry_run)

    log.info(
        "running source=%s sites=%d since=%s until=%s",
        args.source,
        len(sites),
        args.since,
        args.until,
    )
    stats = source.run(ctx)
    log.info("done source=%s %s", args.source, stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
