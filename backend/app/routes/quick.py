"""GET /api/quick/{template}?area=...: instant answers from SQL templates (brief 30 Track 4.2),
no model call. Each table carries its source, method and as-of date; `text` is the answer in
words as the Ask chat shows it."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from app.deps import settings
from tools.context import ToolContext
from tools.quick import TEMPLATES, as_text, quick

router = APIRouter()


@router.get("/api/quick")
def templates() -> dict[str, Any]:
    return {"templates": TEMPLATES}


@router.get("/api/quick/{template}")
def quick_route(
    template: str,
    area: str = Query(min_length=1, max_length=400),
    n: int = Query(default=10, ge=1, le=50),
    kind: Literal["plants", "substations", "data_centres"] = "plants",
) -> dict[str, Any]:
    if template not in TEMPLATES:
        raise HTTPException(404, f"no template {template!r}; templates: {', '.join(TEMPLATES)}")
    r = quick(ToolContext(settings()), template, area, n=n, kind=kind)
    if "error" in r["data"]:
        raise HTTPException(404, r["data"]["error"])
    return {**r["data"], "sources": r["sources"], "text": as_text(r["data"])}
