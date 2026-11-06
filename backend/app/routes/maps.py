"""Saved maps: POST /api/maps (a MapSpec and its data) -> id; GET /api/maps/{id}."""

from __future__ import annotations

import json
import re
import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
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


@router.get("/api/exports/{name}")
def export_file(name: str) -> FileResponse:
    """A file the export tool wrote (brief 30): CSV, GeoJSON or Parquet with sources and terms."""
    if not re.fullmatch(r"x_[0-9a-f]{12}\.(csv|geojson|parquet)", name):
        raise HTTPException(404, "no such export")
    p = settings().results_dir / name
    if not p.exists():
        raise HTTPException(404, "no such export (exports are kept on the instance that made them)")
    return FileResponse(p, filename=name)


@router.get("/api/export")
def export_result(result_id: str, format: str = "csv") -> FileResponse:
    """A stored result as a file with its sources and terms (the export tool, brief 30)."""
    from tools.more import ExportArgs, export

    try:
        args = ExportArgs.model_validate({"result_id": result_id, "format": format})
    except Exception as e:
        raise HTTPException(422, "result_id r_... and format csv, geojson or parquet") from e
    r = export(ToolContext(settings()), args.result_id, args.format)
    if "error" in r["data"]:
        raise HTTPException(404, r["data"]["error"])
    return FileResponse(settings().results_dir / r["data"]["file"], filename=r["data"]["file"])


class SavedTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str = Field(max_length=20_000)
    maps: list[str] = Field(default_factory=list, max_length=10)
    sources: list[dict[str, str]] = Field(default_factory=list, max_length=30)


class SaveConversation(BaseModel):
    turns: list[SavedTurn] = Field(min_length=1, max_length=40)


@router.post("/api/conversations")
def save_conversation(body: SaveConversation) -> dict[str, Any]:
    """A permalink to a conversation (brief 30): the questions, the answers as shown, their
    sources and the ids of their saved maps; `?chat=<id>` opens it read-only."""
    cid = "k_" + secrets.token_hex(6)
    ToolContext(settings()).store.put_json(
        f"agent/conversations/{cid}.json",
        {
            "id": cid,
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "turns": [t.model_dump() for t in body.turns],
        },  # fmt: skip
    )
    return {"id": cid, "link": f"?chat={cid}"}


@router.get("/api/conversations/{cid}")
def get_conversation(cid: str) -> dict[str, Any]:
    if not re.fullmatch(r"k_[0-9a-f]{12}", cid):
        raise HTTPException(404, "no such conversation")
    rec = ToolContext(settings()).store.get_json(f"agent/conversations/{cid}.json")
    if rec is None:
        raise HTTPException(404, "no such conversation")
    return rec
