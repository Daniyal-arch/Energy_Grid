"""Probe: can we export a true-colour Sentinel-2 thumbnail of a site from GEE?

Builds before/after RGB composites for one built solar site, downloads the PNGs, and
saves them to data/ so we can confirm the approach before building the chips pipeline.

Run: uv run python scripts/probe_chip.py
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from app.db import get_db
from ingestion.sources.gee import _init_ee

DATA = Path(__file__).resolve().parent.parent / "data"


def _thumb(ee, region, start: str, end: str) -> str:  # noqa: ANN001
    coll = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
    )
    img = coll.median().select(["B4", "B3", "B2"])
    return img.getThumbURL(
        {"region": region, "dimensions": 384, "format": "png", "min": 0, "max": 3000}
    )


def main() -> None:
    db = get_db()
    site = (
        db.table("sites")
        .select("id, name, geojson:geom, commissioning_date, capacity_mw, status, aoi_method")
        .eq("technology", "solar")
        .eq("aoi_method", "osm_polygon")
        .eq("status", "complete")
        .order("capacity_mw", desc=True)
        .limit(1)
        .execute()
        .data[0]
    )
    print(
        f"site: {site['name']} ({site['capacity_mw']} MW, {site['status']}, "
        f"aoi={site['aoi_method']}, commissioned {site['commissioning_date']})"
    )
    geo = site["geojson"]
    if isinstance(geo, str):
        geo = json.loads(geo)

    ee = _init_ee()
    region = ee.Geometry({"type": geo["type"], "coordinates": geo["coordinates"]}).buffer(400).bounds()

    for label, start, end in [
        ("before", "2021-05-01", "2021-09-30"),
        ("after", "2025-05-01", "2025-09-30"),
    ]:
        url = _thumb(ee, region, start, end)
        png = httpx.get(url, timeout=120).content
        out = DATA / f"chip_{label}.png"
        out.write_bytes(png)
        print(f"  {label}: {len(png):,} bytes -> {out}")


if __name__ == "__main__":
    main()
