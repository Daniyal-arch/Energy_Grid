"""GET /api/site?lon=&lat=&radius_km=: the "Check a site" figures, each with its source."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.deps import settings
from tools.context import ToolContext
from tools.site import site_figures

router = APIRouter()


@router.get("/api/site")
def site(
    lon: float = Query(ge=-180, le=180),
    lat: float = Query(ge=-90, le=90),
    radius_km: int = Query(default=50),
) -> dict[str, Any]:
    r = site_figures(ToolContext(settings()), lon, lat, radius_km)
    return {**r["data"], "sources": r["sources"]}
