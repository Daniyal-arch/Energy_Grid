"""Areas (brief 27 A6): GET /api/areas/resolve?q=, GET /api/areas/{area_id},
GET /api/shapes/{set}/{iso3}."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.deps import settings
from data.areas import AreaError, shapes_of
from tools.areas import resolve_area
from tools.context import ToolContext

router = APIRouter()


@router.get("/api/areas/resolve")
def resolve(
    q: str = Query(min_length=1, max_length=200),
    level: str | None = Query(default=None, max_length=40),
) -> dict[str, Any]:
    r = resolve_area(ToolContext(settings()), names=[q], level=level)
    return {**r["data"], "sources": r["sources"]}


@router.get("/api/areas/{area_id}")
def area(area_id: str) -> dict[str, Any]:
    a = ToolContext(settings()).area_store.get(area_id)
    if a is None:
        raise HTTPException(404, "no such area")
    return {
        **a.summary(),
        "geometry": a.display or a.geometry,
        "simplified": a.display is not None,
        "type": "Feature",
    }


@router.get("/api/shapes/{name}/{iso3}")
def shapes(name: str, iso3: str) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z]{3}|all", iso3):
        raise HTTPException(422, "iso3 is an ISO alpha-3 code or 'all'")
    ctx = ToolContext(settings())
    key = f"agent/shapes/{name.replace(':', '_')}/{iso3.upper()}.json"
    hit = ctx.store.get_json(key)
    if hit is not None:
        return hit
    try:
        out = shapes_of(ctx.areas, name, iso3=None if iso3 == "all" else iso3)
    except AreaError as e:
        raise HTTPException(404, str(e)) from e
    ctx.store.put_json(key, out)
    return out
