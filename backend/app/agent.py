"""The gridwatch agent — answers questions by RETRIEVING stored rows and narrating
them with citations. It never computes or guesses facts (CLAUDE.md rule 1): every
claim about a site's status, dates, or measurements comes from a tool result, and the
response carries a structured `sources` array referencing the evidence/detections/sites
that grounded it.

Provider-agnostic: uses the OpenAI-compatible chat API, so DeepSeek, Groq (Llama), or
Gemini all work via the LLM_PROVIDER env var. Manual tool-call loop so we can collect
exactly which stored rows were retrieved → the citations.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

from openai import OpenAI

from app.config import Settings, get_settings
from app.db import get_db
from supabase import Client

MAX_ITERATIONS = 8

SYSTEM = """You are the analyst for gridwatch, a satellite construction-monitoring \
platform for German energy infrastructure (utility-scale generation ≥5 MW, nationwide).

You answer questions about energy projects' construction progress. The construction \
state machine is: no_activity → clearing → earthworks → construction → complete, \
detected from Sentinel-2 (NDVI vegetation, BSI bare-soil) and Sentinel-1 (VH radar) \
satellite signals compared against seasonal baselines.

ABSOLUTE RULE — you never compute, estimate, infer, or guess facts. You state ONLY \
facts returned by your tools. Every claim about a site's status, a date, a capacity, a \
measurement, or a detected transition MUST come from a tool result you actually \
received. If the tools don't return the data, say plainly that it isn't available — \
never fabricate. Do not do arithmetic on values to produce new facts.

Always call a tool before making factual claims. Most sites in the registry are not \
yet analysed (status 'unknown' = no satellite history processed); only a subset has \
detected construction states. When relevant, say how many matched sites are actually \
analysed versus not yet processed.

When you describe a site's progress, ground it: give the detected state, the date it \
was detected, the confidence, and that it is backed by specific satellite scenes \
(which get_site_detail / get_evidence return). Prefer citing detections and evidence \
over raw numbers.

Deadlines: EEG-auction solar sites have a legal completion deadline — the plant must be \
commissioned within 24 months of the award (§55 EEG). These are derived from the auction \
round encoded in the award number (Zuschlagsnummer), so they are month-precision estimates; \
say so when citing one. A site is 'behind schedule' when its legal deadline has passed and \
satellite analysis has NOT detected it as complete. Use find_overdue_sites for \
'behind schedule / behind deadline' questions; get_site_detail returns a site's deadlines. \
Only analysed sites (status != unknown) can be judged behind schedule.

Be concise, specific, and useful to a professional (project developer, grid operator, \
or lender). Expand jargon."""

# OpenAI-compatible tool/function schemas (retrieve-only)
TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "find_sites",
            "description": "Find energy sites by filters; returns registry facts plus current "
            "detected construction status. Use first to locate sites a question is about.",
            "parameters": {
                "type": "object",
                "properties": {
                    "technology": {
                        "type": "string",
                        "enum": [
                            "solar",
                            "wind",
                            "biomass",
                            "hydro",
                            "geothermal",
                            "combustion",
                            "storage",
                        ],
                    },
                    "construction_state": {
                        "type": "string",
                        "enum": [
                            "unknown",
                            "no_activity",
                            "clearing",
                            "earthworks",
                            "construction",
                            "complete",
                        ],
                    },
                    "mastr_status": {
                        "type": "string",
                        "description": "Registry status, e.g. 'In Betrieb' or 'In Planung'.",
                    },
                    "region": {
                        "type": "string",
                        "description": "German federal state, e.g. 'Bayern'.",
                    },
                    "min_capacity_mw": {"type": "number"},
                    "analysed_only": {
                        "type": "boolean",
                        "description": "Only sites with satellite analysis (status != unknown).",
                    },
                    "limit": {"type": "integer", "description": "Max sites (default 25)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_site_detail",
            "description": "Full detail for one site: registry facts plus detected construction "
            "transitions (state changes with dates, confidence, evidence scene IDs).",
            "parameters": {
                "type": "object",
                "properties": {"site_id": {"type": "string"}},
                "required": ["site_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_evidence",
            "description": "Retrieve evidence rows by ID — the satellite scenes (scene id, sensor, "
            "acquisition date, metric values) backing a detected transition.",
            "parameters": {
                "type": "object",
                "properties": {"evidence_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["evidence_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_overdue_sites",
            "description": "Find sites that are behind schedule: their legal EEG completion "
            "deadline has passed and satellite analysis has NOT detected them complete. "
            "Optionally filter by region or technology.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "description": "German federal state, e.g. 'Bayern'.",
                    },
                    "technology": {
                        "type": "string",
                        "enum": [
                            "solar",
                            "wind",
                            "biomass",
                            "hydro",
                            "geothermal",
                            "combustion",
                            "storage",
                        ],
                    },
                    "limit": {"type": "integer", "description": "Max sites (default 25)."},
                },
            },
        },
    },
]

_SITE_COLS = (
    "id,name,technology,status,mastr_status,capacity_mw,unit_count,state,district,"
    "commissioning_date,planned_commissioning_date,owner,lat,lon"
)

_PROVIDERS = {
    "deepseek": ("https://api.deepseek.com", "deepseek_api_key", "deepseek_model"),
    "groq": ("https://api.groq.com/openai/v1", "groq_api_key", "groq_model"),
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        "gemini_api_key",
        "gemini_model",
    ),
}


def _client(settings: Settings) -> tuple[OpenAI, str]:
    provider = settings.llm_provider
    if provider not in _PROVIDERS:
        raise RuntimeError(f"unknown LLM_PROVIDER '{provider}' (use deepseek | groq | gemini)")
    base_url, key_attr, model_attr = _PROVIDERS[provider]
    api_key = getattr(settings, key_attr)
    if not api_key:
        raise RuntimeError(f"{key_attr.upper()} is not set — add it to .env to use the agent.")
    return OpenAI(api_key=api_key, base_url=base_url), getattr(settings, model_attr)


class _Collector:
    """Accumulates the stored rows the tools retrieved → the response's citations."""

    def __init__(self) -> None:
        self.sources: dict[tuple[str, str], dict[str, Any]] = {}
        self.site_ids: set[str] = set()

    def add(self, kind: str, row: dict[str, Any], label: str) -> None:
        self.sources[(kind, row["id"])] = {"type": kind, "id": row["id"], "label": label}

    def as_list(self) -> list[dict[str, Any]]:
        return list(self.sources.values())


def _find_sites(db: Client, args: dict[str, Any], col: _Collector) -> list[dict[str, Any]]:
    q = db.table("sites_with_centroid").select(_SITE_COLS)
    if t := args.get("technology"):
        q = q.eq("technology", t)
    if s := args.get("construction_state"):
        q = q.eq("status", s)
    if m := args.get("mastr_status"):
        q = q.eq("mastr_status", m)
    if r := args.get("region"):
        q = q.eq("state", r)
    if (c := args.get("min_capacity_mw")) is not None:
        q = q.gte("capacity_mw", c)
    if args.get("analysed_only"):
        q = q.neq("status", "unknown")
    rows = q.limit(int(args.get("limit", 25))).execute().data or []
    for row in rows:
        col.add("site", row, row["name"])
        col.site_ids.add(row["id"])
    return rows


def _resolve_site_id(db: Client, sid: str) -> str | None:
    """Accept a UUID or a MaStR id (e.g. the model echoing a site's name) -> UUID."""
    try:
        uuid.UUID(str(sid))
        return str(sid)
    except (ValueError, TypeError):
        pass
    name = str(sid).split()[-1]  # tolerate "solar SEE123"
    row = db.table("sites").select("id").eq("mastr_id", name).execute().data
    return row[0]["id"] if row else None


def _get_site_detail(db: Client, args: dict[str, Any], col: _Collector) -> dict[str, Any]:
    sid = _resolve_site_id(db, args.get("site_id", ""))
    if not sid:
        return {"error": f"no site matches {args.get('site_id')!r} — use the id from find_sites"}
    site = db.table("sites_with_centroid").select(_SITE_COLS).eq("id", sid).execute().data
    if not site:
        return {"error": "site not found"}
    detections = (
        db.table("detections").select("*").eq("site_id", sid).order("detected_at").execute().data
    )
    deadlines = (
        db.table("deadlines").select("*").eq("site_id", sid).order("deadline_date").execute().data
    )
    col.add("site", site[0], site[0]["name"])
    col.site_ids.add(sid)
    for d in detections:
        col.add("detection", d, f"{d['from_state']}→{d['to_state']} {d['detected_at']}")
    for dl in deadlines:
        col.add("deadline", dl, f"{dl['type']} {dl['deadline_date']}")
    return {"site": site[0], "detections": detections, "deadlines": deadlines}


def _find_overdue(db: Client, args: dict[str, Any], col: _Collector) -> dict[str, Any]:
    today = date.today().isoformat()
    # Start from analysed, not-yet-complete sites (a small set) — "behind schedule" is
    # only meaningful where satellite analysis exists.
    q = (
        db.table("sites_with_centroid")
        .select(_SITE_COLS)
        .neq("status", "unknown")
        .neq("status", "complete")
    )
    if r := args.get("region"):
        q = q.eq("state", r)
    if t := args.get("technology"):
        q = q.eq("technology", t)
    sites = {s["id"]: s for s in (q.execute().data or [])}
    if not sites:
        return {"overdue_count": 0, "sites": []}
    # their legal deadlines that have already passed
    past = (
        db.table("deadlines")
        .select("site_id,deadline_date,source")
        .eq("type", "legal_completion")
        .lt("deadline_date", today)
        .in_("site_id", list(sites))
        .order("deadline_date")
        .execute()
        .data
        or []
    )
    earliest: dict[str, dict[str, Any]] = {}
    for d in past:
        earliest.setdefault(d["site_id"], d)  # ordered asc → earliest kept
    out = []
    for sid, dl in earliest.items():
        s = sites[sid]
        col.add("site", s, s["name"])
        col.site_ids.add(sid)
        out.append(
            {
                "id": sid,
                "name": s["name"],
                "technology": s["technology"],
                "detected_state": s["status"],
                "capacity_mw": s["capacity_mw"],
                "region": s["state"],
                "legal_deadline": dl["deadline_date"],
                "deadline_basis": dl["source"],
            }
        )
    out.sort(key=lambda x: x["legal_deadline"])
    return {"overdue_count": len(out), "sites": out[: int(args.get("limit", 25))]}


def _get_evidence(db: Client, args: dict[str, Any], col: _Collector) -> list[dict[str, Any]]:
    ids = args.get("evidence_ids", [])
    if not ids:
        return []
    rows = db.table("evidence").select("*").in_("id", ids).execute().data or []
    for e in rows:
        col.add("evidence", e, f"{e['sensor']} {e['scene_id']} {e['acquired_at']}")
    return rows


def _dispatch(name: str, args: dict[str, Any], db: Client, col: _Collector) -> Any:
    if name == "find_sites":
        return _find_sites(db, args, col)
    if name == "get_site_detail":
        return _get_site_detail(db, args, col)
    if name == "get_evidence":
        return _get_evidence(db, args, col)
    if name == "find_overdue_sites":
        return _find_overdue(db, args, col)
    return {"error": f"unknown tool {name}"}


def _suggest_followups(client: OpenAI, model: str, question: str, answer_text: str) -> list[str]:
    """Three short follow-up questions a user might ask next (best-effort)."""
    try:
        r = client.chat.completions.create(
            model=model,
            temperature=0.4,
            messages=[
                {
                    "role": "system",
                    "content": "You suggest follow-up questions for a German energy "
                    "construction-monitoring analyst. Reply with ONLY a JSON array of exactly 3 "
                    "short questions (each under 12 words), no prose, no code fences.",
                },
                {"role": "user", "content": f"Q: {question}\nA: {answer_text[:1500]}"},
            ],
        )
        text = (r.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[4:] if text.lower().startswith("json") else text
        arr = json.loads(text)
        return [str(x) for x in arr][:3]
    except Exception:  # noqa: BLE001 — suggestions are optional
        return []


def answer(question: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Run the retrieval loop with optional prior turns (memory). Returns
    {answer, sources, site_ids, provider, follow_ups}."""
    settings = get_settings()
    client, model = _client(settings)
    db = get_db()
    col = _Collector()
    # prior user/assistant turns give multi-turn memory; keep only text turns
    prior = [
        {"role": m["role"], "content": m["content"]}
        for m in (history or [])
        if m.get("role") in ("user", "assistant") and m.get("content")
    ][-8:]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM},
        *prior,
        {"role": "user", "content": question},
    ]

    final = ""
    for _ in range(MAX_ITERATIONS):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            final = msg.content or ""
            break
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        )
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                out = _dispatch(tc.function.name, args, db, col)
            except Exception as e:  # noqa: BLE001 — surface tool errors to the model, never 500
                out = {"error": f"{type(e).__name__}: {e}"}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(out, default=str),
                }
            )

    return {
        "answer": final,
        "sources": col.as_list(),
        "site_ids": sorted(col.site_ids),
        "provider": settings.llm_provider,
        "follow_ups": _suggest_followups(client, model, question, final) if final else [],
    }
