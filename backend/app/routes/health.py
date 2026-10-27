"""GET /api/health: version, git sha, lake catalogue date, model ids (the readiness check)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.deps import lake, settings

router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, Any]:
    s = settings()
    lk = lake()
    return {
        "status": "ok",
        "version": s.version,
        "git_sha": s.git_sha,
        "environment": s.environment,
        "lake": {"mode": lk.lake_mode, "catalog_updated": lk.catalog_date},
        "models": {"main": s.agent_model, "fast": s.agent_model_fast},
        "sources": [],
    }
