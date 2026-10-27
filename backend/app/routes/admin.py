"""POST /api/admin/sql: the guarded SQL for the owner and the evals (X-Admin-Key)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.deps import require_admin, settings
from tools.context import ToolContext
from tools.sql import run_sql

router = APIRouter()


class SqlBody(BaseModel):
    sql: str = Field(max_length=20_000)


@router.post("/api/admin/sql", dependencies=[Depends(require_admin)])
def admin_sql(body: SqlBody) -> dict[str, Any]:
    r = run_sql(ToolContext(settings()), body.sql)
    return {**r["data"], "result_id": r.get("result_id"), "sources": r["sources"]}
