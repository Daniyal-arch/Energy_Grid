"""Google Earth Engine: Sentinel-2 L2A (NDVI, BSI) + Sentinel-1 GRD (VH backscatter).

All reduction happens server-side in GEE — we store only per-site daily means + scene IDs
in `timeseries`. Backfill since 2021 with --since 2021-01-01, then weekly cron.

STATUS: implemented but UNTESTED until the GEE service account exists (docs/SETUP.md).
Geometry note: site polygons are fetched from Postgres as GeoJSON via the
`sites_geojson` select on the `sites` table using PostGIS; for Phase 1 we re-query
geometry here instead of carrying WKT through RunContext.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any

from app.config import get_settings
from app.models import Metric, Sensor, TimeseriesPoint

from ingestion.base import BaseSource, LoadStats, RawRecord, RunContext, SourceMeta
from ingestion.registry import register
from supabase import Client

S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
S1_COLLECTION = "COPERNICUS/S1_GRD"
# Sentinel-2 Scene Classification Layer classes to keep (vegetation, bare, water, unclassified
# excluded clouds/shadow/snow): 4 vegetation, 5 bare soils, 6 water, 7 unclassified
SCL_VALID = [4, 5, 6, 7]
MAX_CLOUD_PCT = 60


def _init_ee() -> Any:
    import ee

    settings = get_settings()
    credentials = ee.ServiceAccountCredentials(
        settings.gee_service_account_email, settings.gee_service_account_key_file
    )
    ee.Initialize(credentials)
    return ee


def _site_geometries(db: Client, site_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch site polygons as GeoJSON. PostgREST returns the PostGIS geom as a GeoJSON
    dict (with a `crs` member); we strip it to plain {type, coordinates} for Earth Engine.
    """
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(site_ids), 200):
        rows = (
            db.table("sites")
            .select("id, geojson:geom")
            .in_("id", site_ids[i : i + 200])
            .execute()
            .data
            or []
        )
        for row in rows:
            geo = row["geojson"]
            if isinstance(geo, str):
                geo = json.loads(geo)
            out[row["id"]] = {"type": geo["type"], "coordinates": geo["coordinates"]}
    return out


@register
class GEESource(BaseSource):
    meta = SourceMeta(
        name="gee",
        description="Sentinel-2 NDVI/BSI + Sentinel-1 VH per site polygon via Google Earth Engine",
        cadence="weekly",
        requires_credentials=("GEE_SERVICE_ACCOUNT_EMAIL", "GEE_SERVICE_ACCOUNT_KEY_FILE"),
        phase=1,
        site_scoped=True,
    )

    def fetch(self, ctx: RunContext) -> Iterable[RawRecord]:
        ee = _init_ee()
        since = (ctx.since or date(2021, 1, 1)).isoformat()
        until = (ctx.until or date.today() + timedelta(days=1)).isoformat()
        geoms = _site_geometries(ctx.db, [str(s.id) for s in ctx.sites])

        for site in ctx.sites:
            geojson = geoms.get(str(site.id))
            if not geojson:
                continue
            region = ee.Geometry(geojson)
            yield from self._fetch_s2(
                ee, site_id=str(site.id), region=region, since=since, until=until
            )
            yield from self._fetch_s1(
                ee, site_id=str(site.id), region=region, since=since, until=until
            )

    def _fetch_s2(
        self, ee: Any, site_id: str, region: Any, since: str, until: str
    ) -> Iterable[RawRecord]:
        def per_image(img: Any) -> Any:
            scl = img.select("SCL")
            mask = scl.remap(SCL_VALID, [1] * len(SCL_VALID), 0)
            img = img.updateMask(mask)
            ndvi = img.normalizedDifference(["B8", "B4"]).rename("ndvi")
            bsi = img.expression(
                "((swir + red) - (nir + blue)) / ((swir + red) + (nir + blue))",
                {
                    "swir": img.select("B11"),
                    "red": img.select("B4"),
                    "nir": img.select("B8"),
                    "blue": img.select("B2"),
                },
            ).rename("bsi")
            stats = ndvi.addBands(bsi).reduceRegion(
                reducer=ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e9
            )
            return ee.Feature(
                None,
                {
                    "scene_id": img.get("system:index"),
                    "date": img.date().format("YYYY-MM-dd"),
                    "ndvi": stats.get("ndvi"),
                    "bsi": stats.get("bsi"),
                },
            )

        coll = (
            ee.ImageCollection(S2_COLLECTION)
            .filterBounds(region)
            .filterDate(since, until)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUD_PCT))
        )
        features = coll.map(per_image).getInfo().get("features", [])
        for f in features:
            props = f["properties"]
            yield {"site_id": site_id, "sensor": "s2", **props}

    def _fetch_s1(
        self, ee: Any, site_id: str, region: Any, since: str, until: str
    ) -> Iterable[RawRecord]:
        def per_image(img: Any) -> Any:
            stats = img.select("VH").reduceRegion(
                reducer=ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e9
            )
            return ee.Feature(
                None,
                {
                    "scene_id": img.get("system:index"),
                    "date": img.date().format("YYYY-MM-dd"),
                    "vh_db": stats.get("VH"),
                },
            )

        coll = (
            ee.ImageCollection(S1_COLLECTION)
            .filterBounds(region)
            .filterDate(since, until)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        )
        features = coll.map(per_image).getInfo().get("features", [])
        for f in features:
            props = f["properties"]
            yield {"site_id": site_id, "sensor": "s1", **props}

    def transform(self, raw: Iterable[RawRecord]) -> Iterable[TimeseriesPoint]:
        for rec in raw:
            sensor = Sensor(rec["sensor"])
            metrics = (Metric.NDVI, Metric.BSI) if sensor is Sensor.S2 else (Metric.VH_DB,)
            for metric in metrics:
                value = rec.get(metric.value)
                if value is None:
                    continue
                yield TimeseriesPoint(
                    site_id=rec["site_id"],
                    date=date.fromisoformat(rec["date"]),
                    sensor=sensor,
                    metric=metric,
                    value=float(value),
                    scene_id=rec.get("scene_id"),
                )

    def load(self, records: Iterable[TimeseriesPoint], db: Client) -> LoadStats:
        # Several scenes can cover a site on the same day (overlapping Sentinel-2 tiles,
        # repeat Sentinel-1 passes). The unique key is (site_id, date, sensor, metric),
        # so collapse same-key observations by averaging before upserting — otherwise
        # PostgREST rejects the batch ("ON CONFLICT ... cannot affect row a second time").
        agg: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for r in records:
            key = (str(r.site_id), r.date.isoformat(), r.sensor.value, r.metric.value)
            entry = agg.setdefault(key, {"sum": 0.0, "n": 0, "scene_id": r.scene_id})
            entry["sum"] += r.value
            entry["n"] += 1
        rows = [
            {
                "site_id": sid,
                "date": d,
                "sensor": sensor,
                "metric": metric,
                "value": e["sum"] / e["n"],
                "scene_id": e["scene_id"],
            }
            for (sid, d, sensor, metric), e in agg.items()
        ]
        for i in range(0, len(rows), 1000):
            db.table("timeseries").upsert(
                rows[i : i + 1000], on_conflict="site_id,date,sensor,metric"
            ).execute()
        return LoadStats(loaded=len(rows))
