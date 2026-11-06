"""GET /api/report: the site report (brief 30 Track 6.1), HTML (printable) or JSON."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.deps import settings
from tools.context import ToolContext
from tools.report import TASKS, as_html, build_report

router = APIRouter()
Task = Literal["data_centre", "battery", "solar_wind", "offshore", "industrial"]


def _report(lon: float, lat: float, radius_km: int, task: str) -> dict[str, Any]:
    if task not in TASKS:
        raise HTTPException(404, f"tasks: {', '.join(TASKS)}")
    rep = build_report(ToolContext(settings()), lon, lat, radius_km, task)
    if "error" in rep:
        raise HTTPException(404, rep["error"])
    return rep


@router.get("/api/report.json")
def report_json(
    lon: float = Query(ge=-180, le=180),
    lat: float = Query(ge=-90, le=90),
    radius_km: Literal[5, 10, 25, 50, 100] = 25,
    task: Task = "data_centre",
) -> dict[str, Any]:
    return _report(lon, lat, radius_km, task)


@router.get("/api/report", response_class=HTMLResponse)
def report_html(
    lon: float = Query(ge=-180, le=180),
    lat: float = Query(ge=-90, le=90),
    radius_km: Literal[5, 10, 25, 50, 100] = 25,
    task: Task = "data_centre",
) -> str:
    return as_html(_report(lon, lat, radius_km, task))
