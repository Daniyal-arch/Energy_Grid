# ruff: noqa: E501 - HTML and SQL strings read best on one line
"""The site report (brief 30 Track 6.1, spec docs/product/site-report.md): a point (or an area)
and a task; the task skill's checklist, in order, each step with the figures the service can
compute there (each with its source, method and as-of date) and the coverage cells the step
names (what is published in the country, or why not). No score, no ranking, no weighting.

GET /api/report?lon=&lat=&radius_km=&task= (HTML, printable: the browser's "Save as PDF") and
/api/report.json (the same as data).
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from tools.area_stats import area_stats
from tools.areas import resolve_area
from tools.context import ToolContext
from tools.more import coverage_cells
from tools.quick import profile
from tools.site import site_figures

TASKS = {
    "data_centre": "datacentre-siting",
    "battery": "battery-siting",
    "solar_wind": "solar-wind-siting",
    "offshore": "offshore-wind",
    "industrial": "industrial-decarbonisation",
}
STEP = re.compile(r"^\d+\.\s+\*\*(?P<title>[^*]+)\*\*\s*(?P<body>.*)$")
FAMILY = re.compile(r"family `([a-z_0-9]+)`")
# words in a step that call for a computed figure, and which (profile titles, area_stats measures)
PROFILE_WORDS = {
    "substation": "substations", "lines": "line length", "eu_lines": "line length",
    "plants": "plants", "data_centres": "data centres", "data centres": "data centres",
}  # fmt: skip
STATS_WORDS = {"flood": "flood", "slope": "slope", "land cover": "land_cover", "solar": "solar",
               "wind": "wind", "people": "people", "pvout": "solar"}  # fmt: skip


def checklist(agent_dir: Path, skill: str) -> list[dict[str, str]]:
    text = (agent_dir / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    steps = []
    for line in text.splitlines():
        m = STEP.match(line.strip())
        if m:
            steps.append({"title": m.group("title").strip(" ."), "body": m.group("body").strip()})
    return steps


def build_report(
    ctx: ToolContext, lon: float, lat: float, radius_km: float, task: str
) -> dict[str, Any]:
    skill = TASKS[task]
    r = resolve_area(
        ctx,
        point=(lon, lat),
        radius_km=radius_km,
        name=f"{radius_km:g} km around {lat:.4f}, {lon:.4f}",
    )["data"]
    area = r.get("area")
    if not area:
        return {"error": r.get("error") or r.get("note") or "no area"}
    tables = profile(ctx, area)
    site = site_figures(ctx, lon=lon, lat=lat, radius_km=int(radius_km))
    steps = []
    for st in checklist(ctx.settings.agent_dir, skill):
        text = f"{st['title']} {st['body']}".lower()
        figures = [
            t
            for t in tables
            if any(w in text and PROFILE_WORDS[w] in t["title"].lower() for w in PROFILE_WORDS)
        ]
        measures = sorted({m for w, m in STATS_WORDS.items() if w in text})
        stats = area_stats(ctx, area["area_id"], measures)["data"] if measures else None
        cov = []
        for fam in dict.fromkeys(FAMILY.findall(st["body"])):
            cov += coverage_cells(ctx, area.get("iso3") or [], fam)
        steps.append({**st, "figures": figures, "stats": stats, "coverage": cov})
    return {
        "task": task, "skill": skill, "point": [lon, lat], "radius_km": radius_km, "area": area,
        "site": site["data"], "site_sources": site["sources"], "steps": steps,
        "rule": "each criterion on its own with its source and date; no score, ranking or weighting",
    }  # fmt: skip


def _table(t: dict[str, Any]) -> str:
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in t["columns"])
    rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in r) + "</tr>"
        for r in t["rows"][:30]
    )
    srcs = "; ".join(
        f"{s.get('dataset')} ({s.get('licence')})"
        for s in t.get("sources", [])
        if not str(s.get("table", "")).startswith("area ")
    )
    return (f"<h4>{html.escape(t['title'])}</h4><table><tr>{head}</tr>{rows or '<tr><td>none in this area</td></tr>'}</table>"
            f"<p class=m>{html.escape(t['method'])}; as of {html.escape(t.get('as_of') or 'n/a')}. {html.escape(srcs)}</p>")  # fmt: skip


def as_html(rep: dict[str, Any]) -> str:
    if "error" in rep:
        return f"<p>No report: {html.escape(rep['error'])}</p>"
    a = rep["area"]
    parts = [
        f"<h1>Site report: {html.escape(rep['task'].replace('_', ' '))}</h1>",
        f"<p class=m>{html.escape(a['name'])} ({a['area_km2']:,.0f} km², {', '.join(a.get('iso3') or [])}). "
        f"The checklist of the {html.escape(rep['skill'])} skill, in order. {html.escape(rep['rule'])}.</p>",
    ]
    for i, st in enumerate(rep["steps"], 1):
        parts.append(
            f"<h2>{i}. {html.escape(st['title'])}</h2><p class=m>{html.escape(st['body'])}</p>"
        )
        for t in st["figures"]:
            parts.append(_table(t))
        if st["stats"]:
            if "error" in st["stats"]:
                parts.append(f"<p class=w>Rasters: {html.escape(str(st['stats']['error']))}</p>")
            else:
                for k, v in (st["stats"].get("measures") or st["stats"]).items():
                    parts.append(
                        f"<p><b>{html.escape(str(k))}</b>: {html.escape(str(v))[:400]}</p>"
                    )
        for c in st["coverage"]:
            what = c.get("source") or c.get("note") or ""
            parts.append(f"<p class=c><b>{html.escape(c['family'])}, {c['country']}</b>: {html.escape(str(c.get('status')))}. "
                         f"{html.escape(what)} <span class=m>(checked {html.escape(str(c.get('checked') or ''))})</span></p>")  # fmt: skip
        if not (st["figures"] or st["stats"] or st["coverage"]):
            parts.append(
                "<p class=w>No figure is computed for this step here; ask the agent (Ask) to run it.</p>"
            )
    style = ("body{font:13px/1.45 system-ui,sans-serif;background:#0b0f16;color:#dce3ee;max-width:900px;margin:24px auto;padding:0 16px}"
             "h1{font-size:20px}h2{font-size:15px;margin-top:22px;border-top:1px solid #222a36;padding-top:10px}h4{margin:10px 0 4px}"
             "table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #263041;padding:2px 6px;text-align:left}"
             ".m{color:#8d94a1;font-size:11.5px}.w{color:#d9a35b}.c{font-size:12px}"
             "@media print{body{background:#fff;color:#000}.m{color:#444}td,th{border-color:#999}button{display:none}}")  # fmt: skip
    return (f"<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>Site report</title><style>{style}</style><button onclick='print()'>Print or save as PDF</button>"
            + "".join(parts) + "</html>")  # fmt: skip
