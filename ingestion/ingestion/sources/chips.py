"""Before/after satellite snapshot chips per site.

For each site, render two true-colour Sentinel-2 thumbnails (a pre-construction baseline
and a recent view) clipped to the site's AOI, upload them to the Storage `chips` bucket,
and store the public URLs + dates on the site. With the refined OSM/area AOIs these frame
the actual array, so the drawer shows a clear field→build transition.

Run AFTER the AOI refinement (osm) so the frame is the real footprint:
    python -m ingestion.run --source chips --technology solar --mastr-status "In Planung"
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable
from typing import Any

import httpx

from ingestion.base import BaseSource, LoadStats, RawRecord, RunContext, SourceMeta
from ingestion.registry import register
from ingestion.sources.gee import _init_ee, _site_geometries
from supabase import Client

BUCKET = "chips"
BEFORE = ("2021-05-01", "2021-09-30", "2021-07-01")
AFTER = ("2025-05-01", "2026-09-30", "2025-07-01")
DIM = 384


def _thumb_url(ee: Any, region: Any, start: str, end: str) -> str:
    coll = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
    )
    img = coll.median().select(["B4", "B3", "B2"])
    return img.getThumbURL(
        {"region": region, "dimensions": DIM, "format": "png", "min": 0, "max": 3000}
    )


@register
class ChipsSource(BaseSource):
    meta = SourceMeta(
        name="chips",
        description="Before/after Sentinel-2 snapshot images per site -> Storage + site URLs",
        cadence="on_demand",
        requires_credentials=("GEE_SERVICE_ACCOUNT_EMAIL", "GEE_SERVICE_ACCOUNT_KEY_FILE"),
        phase=2,
        site_scoped=True,
    )

    def fetch(self, ctx: RunContext) -> Iterable[RawRecord]:
        ee = _init_ee()
        geoms = _site_geometries(ctx.db, [str(s.id) for s in ctx.sites])
        with httpx.Client(timeout=120) as http:
            for site in ctx.sites:
                geojson = geoms.get(str(site.id))
                if not geojson:
                    continue
                region = ee.Geometry(geojson).buffer(300).bounds()
                try:
                    before = http.get(_thumb_url(ee, region, BEFORE[0], BEFORE[1])).content
                    after = http.get(_thumb_url(ee, region, AFTER[0], AFTER[1])).content
                except Exception:  # noqa: BLE001 — skip a site that fails to render
                    continue
                if not before or not after:
                    continue
                yield {"site_id": str(site.id), "before": before, "after": after}

    def transform(self, raw: Iterable[RawRecord]) -> Iterable[RawRecord]:
        return raw

    def load(self, records: Iterable[RawRecord], db: Client) -> LoadStats:
        with contextlib.suppress(Exception):
            db.storage.update_bucket(BUCKET, {"public": True})  # idempotent
        store = db.storage.from_(BUCKET)
        n = 0
        for rec in records:
            sid = rec["site_id"]
            urls = {}
            for label, png in (("before", rec["before"]), ("after", rec["after"])):
                path = f"{sid}/{label}.png"
                store.upload(path, png, {"content-type": "image/png", "upsert": "true"})
                urls[label] = store.get_public_url(path)
            db.table("sites").update(
                {
                    "chip_before_url": urls["before"],
                    "chip_after_url": urls["after"],
                    "chip_before_date": BEFORE[2],
                    "chip_after_date": AFTER[2],
                }
            ).eq("id", sid).execute()
            n += 1
        return LoadStats(loaded=n)
