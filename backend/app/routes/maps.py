"""Saved maps: POST /api/maps (a MapSpec and its data) -> id; GET /api/maps/{id}."""

from __future__ import annotations

import json
import re
import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.deps import settings
from tools.context import ToolContext
from tools.maps import check_map, map_extras

router = APIRouter()


class SavedData(BaseModel):
    columns: list[str] = Field(max_length=100)
    rows: list[list[Any]] = Field(max_length=5000)


class SaveMap(BaseModel):
    spec: dict[str, Any]
    data: dict[str, SavedData] = Field(default_factory=dict)
    sources: list[dict[str, str]] = Field(default_factory=list, max_length=20)


@router.post("/api/maps")
def save_map(body: SaveMap) -> dict[str, Any]:
    ctx = ToolContext(settings())
    # data sent with the spec stands in for server-side results of the same id
    for rid, d in body.data.items():
        if not re.fullmatch(r"r_[0-9a-f]{12}", rid):
            raise HTTPException(422, f"bad result id {rid!r}")
        if ctx.results.get(rid) is None:
            (ctx.results.root / f"{rid}.json").write_text(
                json.dumps(
                    {"columns": d.columns, "rows": d.rows, "sql": "", "sources": body.sources}
                ),
                encoding="utf-8",
            )
    m, err, data = check_map(ctx, body.spec)
    if m is None:
        raise HTTPException(422, f"invalid MapSpec: {err}")
    map_id = "m_" + secrets.token_hex(6)
    sources = body.sources or [s for r in data.values() for s in r.get("sources", [])]
    ctx.store.put_json(
        f"agent/maps/{map_id}.json",
        {
            "id": map_id,
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "spec": m.model_dump(exclude_none=True),
            "data": {rid: {"columns": r["columns"], "rows": r["rows"]} for rid, r in data.items()},
            "sources": sources,
            **map_extras(ctx, m, data),
        },
    )
    return {"id": map_id, "link": f"?map={map_id}", "sources": sources}


@router.get("/api/maps/{map_id}")
def get_map(map_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"m_[0-9a-f]{12}", map_id):
        raise HTTPException(404, "no such map")
    rec = ToolContext(settings()).store.get_json(f"agent/maps/{map_id}.json")
    if rec is None:
        raise HTTPException(404, "no such map")
    return rec
