"""gridwatch API. Phase 1: health + sites read endpoints; agent module lands in Phase 2."""

from typing import Any

from fastapi import FastAPI, HTTPException

from app.db import get_db

app = FastAPI(title="gridwatch", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/sites")
def list_sites() -> list[dict[str, Any]]:
    res = get_db().table("sites_with_centroid").select("*").execute()
    return res.data


@app.get("/sites/{site_id}/timeseries")
def site_timeseries(site_id: str, metric: str | None = None) -> list[dict[str, Any]]:
    q = get_db().table("timeseries").select("*").eq("site_id", site_id).order("date")
    if metric:
        q = q.eq("metric", metric)
    res = q.execute()
    if res.data is None:
        raise HTTPException(404, "site not found")
    return res.data


@app.get("/sites/{site_id}/detections")
def site_detections(site_id: str) -> list[dict[str, Any]]:
    res = (
        get_db()
        .table("detections")
        .select("*")
        .eq("site_id", site_id)
        .order("detected_at")
        .execute()
    )
    return res.data
