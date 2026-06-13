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

Be concise, specific, and useful to a professional (project developer, grid operator, \
or lender). Expand jargon. Deadline data is not loaded yet — do not invent deadlines."""

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


def _get_site_detail(db: Client, args: dict[str, Any], col: _Collector) -> dict[str, Any]:
    sid = args["site_id"]
    site = db.table("sites_with_centroid").select(_SITE_COLS).eq("id", sid).execute().data
    if not site:
        return {"error": "site not found"}
    detections = (
        db.table("detections").select("*").eq("site_id", sid).order("detected_at").execute().data
    )
    col.add("site", site[0], site[0]["name"])
    col.site_ids.add(sid)
    for d in detections:
        col.add("detection", d, f"{d['from_state']}→{d['to_state']} {d['detected_at']}")
    return {"site": site[0], "detections": detections}


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
    return {"error": f"unknown tool {name}"}


def answer(question: str) -> dict[str, Any]:
    """Run the retrieval loop and return {answer, sources, site_ids, provider}."""
    settings = get_settings()
    client, model = _client(settings)
    db = get_db()
    col = _Collector()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM},
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
            out = _dispatch(tc.function.name, args, db, col)
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
    }
