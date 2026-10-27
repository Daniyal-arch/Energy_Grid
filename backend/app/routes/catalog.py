"""The catalogue without the agent: search and one dataset's entry."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.deps import settings
from tools.context import get_catalogue

router = APIRouter()
SOURCE = {
    "dataset": "catalog",
    "table": "agent/catalog",
    "licence": "InfraAtlas",
    "retrieved": "agent/catalog/*.yaml, datasets.json",
}


@router.get("/api/catalog/search")
def search(q: str = Query(min_length=1, max_length=200)) -> dict[str, Any]:
    return {"matches": get_catalogue(settings()).search(q), "sources": [SOURCE]}


@router.get("/api/catalog/{dataset}")
def dataset(dataset: str) -> dict[str, Any]:
    cat = get_catalogue(settings())
    entry = cat.table_entry(dataset) or next(
        (d for d in cat.map_datasets if d["id"] == dataset), None
    )
    if entry is None:
        raise HTTPException(404, f"no catalogue entry {dataset!r}")
    return {"entry": entry, "sources": [SOURCE]}
