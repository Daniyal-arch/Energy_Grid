"""GET /api/feed/{area}.json and .rss: what changed in a watched area (brief 30 Track 6.2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.deps import settings
from tools.context import ToolContext
from tools.feeds import as_rss, feed

router = APIRouter()


def _feed(area: str) -> dict[str, Any]:
    if not 1 <= len(area) <= 200:
        raise HTTPException(422, "an area name of 1-200 characters")
    f = feed(ToolContext(settings()), area)
    if "error" in f:
        raise HTTPException(404, f["error"])
    return f


@router.get("/api/feed/{area}.json")
def feed_json(area: str) -> dict[str, Any]:
    return _feed(area)


@router.get("/api/feed/{area}.rss")
def feed_rss(area: str, request: Request) -> Response:
    f = _feed(area)
    link = str(request.base_url) + f"?watch={area}"
    return Response(as_rss(f, link), media_type="application/rss+xml")
