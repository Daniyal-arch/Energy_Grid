"""GET /api/places?q=: the gazetteer (countries, US states, zones, cities, coordinates)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.deps import settings
from tools.context import ToolContext
from tools.places import find_place

router = APIRouter()


@router.get("/api/places")
def places(q: str = Query(min_length=1, max_length=200)) -> dict[str, Any]:
    r = find_place(ToolContext(settings()), q)
    return {**r["data"], "sources": r["sources"]}
