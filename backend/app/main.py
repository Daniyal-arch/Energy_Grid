"""gridwatch API — data layer for the dashboard (and, in Phase 2, the agent).

The frontend never touches Supabase directly: it calls this API, which holds the
service-role key. That keeps data access server-side (future auth / rate limiting /
the agent all attach here) and lets us paginate past PostgREST's 1000-row cap.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import agent
from app.db import get_db

app = FastAPI(title="gridwatch", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# lean field set that drives the map, KPI header, and filters
_SITE_FIELDS = (
    "id,name,technology,status,mastr_status,capacity_mw,unit_count,"
    "state,district,municipality,owner,commissioning_date,planned_commissioning_date,lat,lon"
)


def _paginate(table: str, select: str, **eq: Any) -> list[dict[str, Any]]:
    db = get_db()
    rows: list[dict[str, Any]] = []
    page = 0
    while True:
        q = db.table(table).select(select)
        for k, v in eq.items():
            q = q.eq(k, v)
        batch = q.range(page * 1000, page * 1000 + 999).execute().data or []
        rows.extend(batch)
        if len(batch) < 1000:
            break
        page += 1
    return rows


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/sites")
def list_sites() -> list[dict[str, Any]]:
    """Every site with map-ready fields (lat/lon from the centroid view)."""
    rows = _paginate("sites_with_centroid", _SITE_FIELDS)
    return [r for r in rows if r.get("lat") is not None]


@app.get("/sites/{site_id}")
def site_detail(site_id: str) -> dict[str, Any]:
    db = get_db()
    site = db.table("sites_with_centroid").select("*").eq("id", site_id).execute().data
    if not site:
        raise HTTPException(404, "site not found")
    detections = (
        db.table("detections")
        .select("*")
        .eq("site_id", site_id)
        .order("detected_at")
        .execute()
        .data
    )
    # resolve evidence referenced by the detections
    ev_ids = sorted({e for d in detections for e in (d.get("evidence_ids") or [])})
    evidence = {}
    if ev_ids:
        rows = db.table("evidence").select("*").in_("id", ev_ids).execute().data
        evidence = {r["id"]: r for r in rows}
    for d in detections:
        d["evidence"] = [evidence[i] for i in (d.get("evidence_ids") or []) if i in evidence]
    return {"site": site[0], "detections": detections}


@app.get("/sites/{site_id}/timeseries")
def site_timeseries(site_id: str) -> dict[str, list[dict[str, Any]]]:
    """NDVI/BSI/VH series grouped by metric, ascending by date."""
    rows = _paginate("timeseries", "date,sensor,metric,value", site_id=site_id)
    series: dict[str, list[dict[str, Any]]] = {"ndvi": [], "bsi": [], "vh_db": []}
    for r in sorted(rows, key=lambda x: x["date"]):
        series.setdefault(r["metric"], []).append({"date": r["date"], "value": r["value"]})
    return series


@app.get("/detections/recent")
def recent_detections(limit: int = 50) -> list[dict[str, Any]]:
    """Latest state transitions across the portfolio — the monitoring feed."""
    db = get_db()
    dets = (
        db.table("detections")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    site_ids = sorted({d["site_id"] for d in dets})
    sites = {}
    if site_ids:
        rows = (
            db.table("sites_with_centroid")
            .select("id,name,technology,capacity_mw,lat,lon,state")
            .in_("id", site_ids)
            .execute()
            .data
        )
        sites = {r["id"]: r for r in rows}
    for d in dets:
        d["site"] = sites.get(d["site_id"])
    return [d for d in dets if d["site"]]


class AgentQuery(BaseModel):
    question: str


@app.post("/agent/query")
def agent_query(body: AgentQuery) -> dict[str, Any]:
    """Ask the cited agent. Returns {answer, sources, site_ids, provider}.

    The agent only retrieves stored rows and narrates them with citations — it never
    computes facts (see app/agent.py / CLAUDE.md rule 1).
    """
    try:
        return agent.answer(body.question)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
