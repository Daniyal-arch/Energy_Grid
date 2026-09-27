"""Step 0 validation: does per-turbine PlanetScope NDVI actually show a usable signal?

Whole-farm-polygon NDVI averaging (the `gee.py` pattern) dilutes a turbine pad's tiny
disturbed footprint into noise across a multi-km2 convex hull — that's the literal
reason wind satellite-detection was ripped out before (see
supabase/migrations/20260617000012_solar_only_satellite.sql). Switching to PlanetScope's
3m pixels doesn't fix that unless we also switch the spatial unit: this script computes
NDVI in a small (~50m radius) buffer around each individual turbine instead of over the
whole farm hull, for one real site with a known commissioning date, comparing a
"before" window (well before any construction) against an "after" window (post
commissioning, turbines definitely standing) using real downloaded PlanetScope scenes.

This is the gate for the `planet` adapter: if the per-turbine NDVI drop isn't clearly
visible above noise here, building the full pipeline isn't worth it.

Site: Wind farm Vierlinden (commissioned 2025-02-04, 3 turbines) — picked because its
construction window is comfortably outside Planet's ~29-day download embargo in both
directions, so every scene we want is actually downloadable.
"""

from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path

# This machine has a user-level PROJ_LIB pointing at PostgreSQL/PostGIS's bundled
# (older) proj.db, which shadows rasterio's own and breaks every CRS lookup with
# "DATABASE.LAYOUT.VERSION.MINOR" errors. Force rasterio's bundled proj data dir
# before rasterio touches any CRS — must happen before the rasterio import below.
_rasterio_proj_data = Path(__file__).resolve().parents[1] / ".venv/Lib/site-packages/rasterio/proj_data"
if _rasterio_proj_data.exists():
    os.environ["PROJ_LIB"] = str(_rasterio_proj_data)
    os.environ["PROJ_DATA"] = str(_rasterio_proj_data)

import httpx  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from rasterio.warp import transform as warp_transform  # noqa: E402

load_dotenv()
KEY = os.environ["PLANET_API_KEY"]
BASE = "https://api.planet.com/data/v1"
AUTH = httpx.BasicAuth(KEY, "")

TURBINES = [
    {"id": "e419de48", "lat": 52.510653, "lon": 14.370253},
    {"id": "148acc26", "lat": 52.508567, "lon": 14.375233},
    {"id": "2f6b69aa", "lat": 52.506227, "lon": 14.364658},
]
BUFFER_DEG = 0.0005  # ~50m at this latitude
BEFORE_WINDOW = (date(2023, 10, 1), date(2023, 12, 31))  # well before construction
AFTER_WINDOW = (date(2025, 3, 1), date(2025, 5, 31))  # after commissioning 2025-02-04
ASSET_PREFERENCE = ["ortho_analytic_4b_sr", "ortho_analytic_4b"]


def turbine_bbox(lat: float, lon: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lon - BUFFER_DEG, lat - BUFFER_DEG],
                [lon + BUFFER_DEG, lat - BUFFER_DEG],
                [lon + BUFFER_DEG, lat + BUFFER_DEG],
                [lon - BUFFER_DEG, lat + BUFFER_DEG],
                [lon - BUFFER_DEG, lat - BUFFER_DEG],
            ]
        ],
    }


def best_downloadable_item(c: httpx.Client, geom: dict, window: tuple[date, date]) -> dict | None:
    body = {
        "item_types": ["PSScene"],
        "filter": {
            "type": "AndFilter",
            "config": [
                {"type": "GeometryFilter", "field_name": "geometry", "config": geom},
                {
                    "type": "DateRangeFilter",
                    "field_name": "acquired",
                    "config": {
                        "gte": f"{window[0].isoformat()}T00:00:00Z",
                        "lte": f"{window[1].isoformat()}T23:59:59Z",
                    },
                },
                {"type": "RangeFilter", "field_name": "cloud_cover", "config": {"lte": 0.1}},
            ],
        },
    }
    r = c.post(f"{BASE}/quick-search", json=body)
    r.raise_for_status()
    features = r.json().get("features", [])
    downloadable = [f for f in features if f.get("_permissions")]
    if not downloadable:
        return None
    downloadable.sort(key=lambda f: f["properties"].get("clear_percent", 0), reverse=True)
    return downloadable[0]


def activate_and_get_url(c: httpx.Client, item: dict) -> tuple[str, str] | None:
    item_id = item["id"]
    assets_url = item["_links"]["assets"]
    assets = c.get(assets_url).json()
    asset_type = next((t for t in ASSET_PREFERENCE if t in assets), None)
    if asset_type is None:
        print(f"    {item_id}: no preferred asset type available ({list(assets)})")
        return None
    asset = assets[asset_type]
    if "download" not in asset.get("_permissions", []):
        print(f"    {item_id}: {asset_type} not downloadable (_permissions={asset.get('_permissions')})")
        return None

    if asset["status"] != "active":
        act = c.post(asset["_links"]["activate"])
        print(f"    {item_id}: activate POST -> {act.status_code}, polling...")
        for i in range(60):  # up to ~10 min
            time.sleep(10)
            asset = c.get(assets_url).json()[asset_type]
            print(f"      [{i}] status={asset['status']}")
            if asset["status"] == "active":
                break
        else:
            print(f"    {item_id}: activation timed out")
            return None

    location = asset.get("location")
    if not location:
        print(f"    {item_id}: active but no 'location' key — keys={list(asset)}")
        return None
    return asset_type, location


def ndvi_at_point(location_url: str, lat: float, lon: float, window_px: int = 7) -> float | None:
    """Reads only a small pixel window via HTTP range requests (GDAL /vsicurl/) instead
    of downloading the whole multi-hundred-MB scene — that full download is what was
    timing out, and we only ever need a handful of pixels around one turbine."""
    with rasterio.Env(GDAL_HTTP_MAX_RETRY=3, GDAL_HTTP_TIMEOUT=60, CPL_VSIL_CURL_USE_HEAD=False):
        with rasterio.open(f"/vsicurl/{location_url}") as ds:
            xs, ys = warp_transform("EPSG:4326", ds.crs, [lon], [lat])
            row, col = ds.index(xs[0], ys[0])
            half = window_px // 2
            window = rasterio.windows.Window(col - half, row - half, window_px, window_px)
            blue, green, red, nir = (ds.read(b, window=window).astype("float32") for b in (1, 2, 3, 4))
            valid = (red + nir) > 0
            if not valid.any():
                return None
            ndvi = (nir - red) / (nir + red + 1e-9)
            return float(np.nanmean(ndvi[valid]))


def main() -> None:
    with httpx.Client(auth=AUTH, timeout=60) as c:
        print(f"{'turbine':<10} {'before NDVI':>12} {'after NDVI':>12} {'drop':>8}")
        for t in TURBINES:
            geom = turbine_bbox(t["lat"], t["lon"])
            before_item = best_downloadable_item(c, geom, BEFORE_WINDOW)
            after_item = best_downloadable_item(c, geom, AFTER_WINDOW)
            if not before_item or not after_item:
                print(f"{t['id']:<10} no downloadable scene in one or both windows "
                      f"(before={'yes' if before_item else 'no'}, after={'yes' if after_item else 'no'})")
                continue

            before_dl = activate_and_get_url(c, before_item)
            after_dl = activate_and_get_url(c, after_item)
            if not before_dl or not after_dl:
                print(f"{t['id']:<10} download failed")
                continue

            before_ndvi = ndvi_at_point(before_dl[1], t["lat"], t["lon"])
            after_ndvi = ndvi_at_point(after_dl[1], t["lat"], t["lon"])
            if before_ndvi is None or after_ndvi is None:
                print(f"{t['id']:<10} NDVI computation failed (no valid pixels)")
                continue

            drop = after_ndvi - before_ndvi
            print(f"{t['id']:<10} {before_ndvi:>12.3f} {after_ndvi:>12.3f} {drop:>8.3f}  "
                  f"(before={before_item['properties']['acquired'][:10]}, "
                  f"after={after_item['properties']['acquired'][:10]})")


if __name__ == "__main__":
    main()
