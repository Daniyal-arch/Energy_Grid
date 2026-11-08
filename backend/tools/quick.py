# ruff: noqa: E501 - the templates' SQL reads best on one line each
"""Instant answers without a model (brief 30 Track 4.2): SQL templates over the app tables for
the questions most people ask, each figure with its source, method and "as of" date.

Templates (`TEMPLATES`): profile, top, totals, compare, published, prices. Each takes an area
by name (resolve_area) and runs its queries through `run_sql`, so a template's numbers are the
SQL's numbers by construction (evals check them against hand-written SQL). Served as
`GET /api/quick/{template}`, as the agent's `quick` tool, and by the graph's quick node for
questions `match()` recognises (no model call).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from data.areas import ISO2_TO_ISO3
from tools import prepared
from tools.areas import resolve_area
from tools.context import ToolContext, result
from tools.sql import run_sql

Template = Literal["profile", "top", "totals", "compare", "published", "prices"]
TEMPLATES: dict[str, str] = {
    "profile": "the area card's figures: plants by fuel, substations, line length, data centres",
    "top": "the largest N plants (or substations by voltage, or data centres) in the area",
    "totals": "plant capacity totals by fuel (Europe, world) or by status (US)",
    "compare": "the profile figures of two to six areas side by side",
    "published": "what is published for the area's countries, family by family (coverage)",
    "prices": "day-ahead price figures of the bidding zones in the area's countries",
}
ISO3_TO_ISO2 = {v: k for k, v in ISO2_TO_ISO3.items() if k not in ("UK", "EL")}
WHOLE = ("country", "group", "nuts0", "world")


class QuickArgs(BaseModel):
    template: Template
    area: str = Field(
        description="a place name: country, region, city, zone; for compare "
        "several names separated by ';'"
    )
    n: int = Field(default=10, ge=1, le=50, description="top: how many")
    kind: Literal["plants", "substations", "data_centres"] = "plants"


class QuickError(ValueError):
    pass


def _as_of(src: dict[str, str]) -> str:
    m = re.search(r"(\d{4}-\d\d-\d\d)", src.get("retrieved", ""))
    return m.group(1) if m else src.get("retrieved", "")


def _area(ctx: ToolContext, name: str) -> dict[str, Any]:
    r = resolve_area(ctx, names=[name])["data"]
    if not r.get("area") and re.match(r"(?i)the ", name):  # "the Benelux", "the Netherlands"
        r = resolve_area(ctx, names=[name[4:]])["data"]
    if not r.get("area"):
        raise QuickError(r.get("error") or r.get("note") or f"no area named {name!r}")
    return r["area"]


def _where(area: dict[str, Any], lon: str = "lon", lat: str = "lat", key: str = "country") -> str:
    """A whole country or group: its country codes (outlines leave coastal and offshore plants
    outside); anything smaller: the outline."""
    if area["level"] in WHOLE and area.get("iso3"):
        codes = ", ".join(f"'{ISO3_TO_ISO2.get(i, i)}'" for i in area["iso3"])
        return f"{key} IN ({codes})"
    return f"in_area({lon}, {lat}, '{area['area_id']}')"


def _table(ctx: ToolContext, title: str, sql: str, method: str) -> dict[str, Any]:
    r = run_sql(ctx, sql)
    d = r["data"]
    if "error" in d:
        raise QuickError(f"{title}: {d['error']}")
    srcs = [s for s in r["sources"] if not s["table"].startswith("area ")]
    return {
        "title": title,
        "columns": d["columns"],
        "rows": d["rows"],
        "method": method,
        "sql": sql,
        "sources": r["sources"],
        "as_of": ", ".join(sorted({_as_of(s) for s in srcs if _as_of(s)})),
        "result_id": r.get("result_id"),
    }


def _region(area: dict[str, Any]) -> str:
    iso = set(area.get("iso3") or [])
    if iso == {"USA"}:
        return "us"
    eu = {ISO2_TO_ISO3[k] for k in ISO2_TO_ISO3} - {"USA"}
    return "eu" if iso and iso <= eu else "world"


def profile(ctx: ToolContext, area: dict[str, Any]) -> list[dict[str, Any]]:
    w, reg = _where(area), _region(area)
    out = []
    if reg == "eu":
        out.append(_table(ctx, "Power plants of 20 MW and more by fuel",
            f"SELECT fuel, count(*) AS plants, round(sum(mw), 1) AS mw FROM app.eu_plants WHERE {w} "
            "GROUP BY fuel ORDER BY mw DESC", "count and sum of MW as published, per fuel"))  # fmt: skip
        out.append(_table(ctx, "Transmission substations (220 kV and more) by voltage",
            f"SELECT kv, count(*) AS substations FROM app.eu_substations WHERE {w} GROUP BY kv "
            "ORDER BY kv DESC", "count per highest voltage"))  # fmt: skip
        if area["level"] not in WHOLE:
            out.append(_table(ctx, "Transmission line length inside the area",
                f"SELECT kv, round(sum(km_inside(geometry, '{area['area_id']}')), 1) AS km "
                f"FROM app.eu_lines WHERE intersects_area(geometry, '{area['area_id']}') GROUP BY kv ORDER BY kv DESC",
                "length of each line inside the outline, summed per voltage (geodesic km)"))  # fmt: skip
    elif reg == "us":
        out.append(_table(ctx, "Generators of 1 MW and more by type (operating)",
            f"SELECT type, count(*) AS plants, round(sum(mw), 1) AS mw FROM app.us_plants WHERE "
            f"status = 'operating' AND {_where(area, key='state') if area['level'] != 'country' else 'true'} "
            "GROUP BY type ORDER BY mw DESC", "count and sum of MW (net summer) per type"))  # fmt: skip
    else:
        out.append(_table(ctx, "Power plants by type",
            f"SELECT type, count(*) AS plants, round(sum(mw), 1) AS mw FROM app.world_plants WHERE "
            f"in_area(lon, lat, '{area['area_id']}') GROUP BY type ORDER BY mw DESC",
            "count and sum of MW as published, per type"))  # fmt: skip
    out.append(_table(ctx, "Data centres",
        f"SELECT count(*) AS data_centres FROM app.data_centres WHERE in_area(lon, lat, '{area['area_id']}')",
        "count of sites inside the outline"))  # fmt: skip
    return out


def top(ctx: ToolContext, area: dict[str, Any], n: int, kind: str) -> list[dict[str, Any]]:
    w, reg = _where(area), _region(area)
    if kind == "substations":
        return [_table(ctx, f"The {n} highest-voltage substations",
            f"SELECT kv, lon, lat, country FROM app.eu_substations WHERE {w} ORDER BY kv DESC LIMIT {n}",
            "ordered by highest voltage")]  # fmt: skip
    if kind == "data_centres":
        return [_table(ctx, "Data centres",
            f"SELECT * FROM app.data_centres WHERE in_area(lon, lat, '{area['area_id']}') LIMIT {n}",
            "sites inside the outline (no size is published, so no order)")]  # fmt: skip
    if reg == "us":
        sql = (f"SELECT name, state, type, mw, year FROM app.us_plants WHERE status = 'operating' AND "
               f"in_area(lon, lat, '{area['area_id']}') ORDER BY mw DESC LIMIT {n}")  # fmt: skip
    elif reg == "eu":
        sql = f"SELECT name, country, fuel, mw, year FROM app.eu_plants WHERE {w} ORDER BY mw DESC LIMIT {n}"
    else:
        # the world plants file carries no names (GEM trackers: type, status, MW, year, position)
        sql = (f"SELECT type, status, mw, year, lon, lat FROM app.world_plants WHERE in_area(lon, lat, "
               f"'{area['area_id']}') ORDER BY mw DESC LIMIT {n}")  # fmt: skip
    return [_table(ctx, f"The {n} largest power plants", sql, "ordered by MW as published")]


def totals(ctx: ToolContext, area: dict[str, Any]) -> list[dict[str, Any]]:
    if _region(area) == "us":
        cond = "true" if area["level"] == "country" else f"in_area(lon, lat, '{area['area_id']}')"
        return [_table(ctx, "Capacity by status",
            f"SELECT status, count(*) AS plants, round(sum(mw), 1) AS mw FROM app.us_plants WHERE {cond} "
            "GROUP BY status ORDER BY mw DESC", "count and sum of MW per status (EIA-860M)")]  # fmt: skip
    return profile(ctx, area)[:1]


@lru_cache
def _coverage(root: str) -> dict[str, Any]:
    p = Path(root) / "frontend" / "public" / "data" / "eu" / "coverage.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def published(ctx: ToolContext, area: dict[str, Any]) -> list[dict[str, Any]]:
    cov = _coverage(str(ctx.settings.atlas_root))
    if not cov:
        raise QuickError("the coverage registry is not in this service")
    names = {f["id"]: f["name"] for f in cov["families"]}
    rows = []
    for i3 in area.get("iso3") or []:
        cc = "US" if i3 == "USA" else "GB" if i3 == "GBR" else ISO3_TO_ISO2.get(i3, "")
        for fam, c in (cov["countries"].get(cc) or {}).items():
            rows.append([cc, names.get(fam, fam), c.get("status"), c.get("source") or c.get("note") or "",
                         c.get("checked") or cov.get("checked", "")])  # fmt: skip
    return [{
        "title": "What is published, family by family",
        "columns": ["country", "family", "status", "source or reason", "checked"],
        "rows": rows,
        "method": "the coverage registry (data/coverage.yaml): one cell per family and country",
        "sql": "",
        "sources": [{"dataset": "coverage registry", "table": "data/coverage.yaml",
                     "licence": "facts", "retrieved": cov.get("checked", "")}],
        "as_of": cov.get("checked", ""),
    }]  # fmt: skip


def prices(ctx: ToolContext, area: dict[str, Any]) -> list[dict[str, Any]]:
    codes = ", ".join(f"'{ISO3_TO_ISO2.get(i, i)}'" for i in area.get("iso3") or []) or "''"
    return [_table(ctx, "Day-ahead prices per bidding zone",
        f"SELECT zone, mean_eur_mwh, min_eur_mwh, max_eur_mwh, negative_hours, period_start, period_end "
        f"FROM app.eu_prices WHERE country IN ({codes}) ORDER BY zone",
        "as published per zone over the period shown (ENTSO-E day-ahead)")]  # fmt: skip


def answer_for(
    ctx: ToolContext, template: str, a: dict[str, Any], n: int = 10, kind: str = "plants"
) -> list[dict[str, Any]]:
    """One template's tables for a resolved area (also what build_prepared.py stores)."""
    fn = {"profile": lambda: profile(ctx, a), "top": lambda: top(ctx, a, n, kind),
          "totals": lambda: totals(ctx, a), "published": lambda: published(ctx, a),
          "prices": lambda: prices(ctx, a)}[template]  # fmt: skip
    return fn()


def quick(
    ctx: ToolContext, template: str, area: str, n: int = 10, kind: str = "plants"
) -> dict[str, Any]:
    try:
        if template == "compare":
            names = [x.strip() for x in re.split(r";|\bvs\.?\b|\band\b", area) if x.strip()]
            if not 2 <= len(names) <= 6:
                raise QuickError("compare takes two to six areas, separated by ';'")
            areas = [_area(ctx, x) for x in names]
            tables = [{**t, "area": a["name"]} for a in areas for t in profile(ctx, a)]
            summary: Any = [{k: a[k] for k in ("area_id", "name", "level", "iso3")} for a in areas]
        else:
            a = _area(ctx, area)
            hit = prepared.lookup(ctx, template, a["area_id"], n, kind)  # brief 32 Tier 0
            if hit is not None:
                return result(hit["data"], hit["sources"])
            tables = answer_for(ctx, template, a, n, kind)
            summary = {k: a[k] for k in ("area_id", "name", "level", "iso3")}
    except QuickError as e:
        return result({"error": str(e), "template": template}, [])
    sources: list[dict[str, str]] = []
    for t in tables:
        for s in t.pop("sources"):
            if s not in sources:
                sources.append(s)
    data = {"template": template, "area": summary, "tables": tables}
    rid = next((t.get("result_id") for t in tables if t.get("result_id")), None)
    return result(data, sources, rid)


def as_text(data: dict[str, Any]) -> str:
    """The instant answer in words: each table as lines, with its method and as-of date."""
    if "error" in data:
        return f"No instant answer: {data['error']}"
    head = data["area"]
    name = head["name"] if isinstance(head, dict) else " vs ".join(a["name"] for a in head)
    lines = [f"**{name}** ({TEMPLATES[data['template']]})"]
    for t in data["tables"]:
        where = f" - {t['area']}" if t.get("area") else ""
        lines.append(f"\n{t['title']}{where} ({t['method']}; as of {t['as_of'] or 'n/a'}):")
        if not t["rows"]:
            lines.append("- none in this area")
        for r in t["rows"][:15]:
            lines.append(
                "- " + ", ".join(f"{c} {v}" for c, v in zip(t["columns"], r, strict=False))
            )
        if len(t["rows"]) > 15:
            lines.append(f"- ... {len(t['rows']) - 15} more rows in the table")
    return "\n".join(lines)


# ---------------------------------------------------------------- the router rule
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("compare", re.compile(r"^compare (?P<area>.+?)(?: on .*)?\??$", re.I)),
    (
        "top",
        re.compile(
            r"^(?:what are |show |list )?(?:the )?(?:top|largest|biggest) (?P<n>\d+)? ?"
            r"(?P<kind>power plants|plants|substations|data cent(?:re|er)s) in (?P<area>.+?)\??$",
            re.I,
        ),
    ),  # fmt: skip
    (
        "totals",
        re.compile(
            r"^(?:what is the )?(?:total )?(?:capacity|plants) by (?:fuel|status|type) in (?P<area>.+?)\??$",
            re.I,
        ),
    ),
    (
        "published",
        re.compile(r"^what(?: data)? is published (?:for|in|about) (?P<area>.+?)\??$", re.I),
    ),
    (
        "prices",
        re.compile(r"^(?:what are )?(?:the )?(?:day-ahead )?prices in (?P<area>.+?)\??$", re.I),
    ),
    (
        "profile",
        re.compile(
            r"^(?:profile of|area profile:?|tell me about|what is in|what's in) (?P<area>.+?)\??$",
            re.I,
        ),
    ),
]


def match(question: str) -> dict[str, Any] | None:
    """A question one template answers as asked: its arguments, else None (the agent answers)."""
    q = " ".join(question.strip().split())
    if re.search(r"(?i)\b(map|maps|chart|plot|graph|draw)\b", q):  # the cartographer's work
        return None
    for name, rx in PATTERNS:
        m = rx.match(q)
        if not m:
            continue
        g = m.groupdict()
        args: dict[str, Any] = {"template": name, "area": g["area"].strip(" .")}
        if name == "compare":
            args["area"] = ";".join(
                x.strip()
                for x in re.split(r",|;|\bvs\.?\b|\band\b|\bwith\b", g["area"])
                if x.strip()
            )
        if g.get("n"):
            args["n"] = min(int(g["n"]), 50)
        if g.get("kind"):
            k = g["kind"].lower()
            args["kind"] = (
                "substations" if "sub" in k else "data_centres" if "data" in k else "plants"
            )
        return args
    return None
