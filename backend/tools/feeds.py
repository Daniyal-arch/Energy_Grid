# ruff: noqa: E501 - feed text reads best on one line
"""Watchlists and change feeds (brief 30 Track 6.2, spec docs/product/watchlists.md).

A watched area has a feed: GET /api/feed/{area}.json or .rss. Each call computes the area's
instant-answer profile (tools/quick.py: plants by fuel, substations by voltage, line length, data
centres) and keeps one snapshot a day in the object store (`agent/feeds/<key>/<date>.json`);
the feed lists what changed between consecutive snapshots, row by row (a new fuel, a count or a
MW sum that moved), each change with both dates and the tables' sources. A scheduled run of the
same code (wave-refresh or a cron) keeps the snapshots going for areas nobody opened.

Changes are differences of published values between two dates: nothing estimated.
"""

from __future__ import annotations

import hashlib
import html
import time
from datetime import UTC, datetime
from typing import Any

from tools.context import ToolContext
from tools.quick import QuickError, _area, profile

KEEP = 60  # snapshots listed per area


def key_of(area_name: str) -> str:
    return hashlib.sha256(area_name.strip().lower().encode()).hexdigest()[:16]


def _snapshot(ctx: ToolContext, area: dict[str, Any]) -> dict[str, Any]:
    tables = profile(ctx, area)
    return {
        "date": datetime.now(UTC).date().isoformat(),
        "area": {k: area.get(k) for k in ("area_id", "name", "level", "iso3")},
        "tables": [
            {"title": t["title"], "columns": t["columns"], "rows": t["rows"], "as_of": t["as_of"],
             "sources": [s for s in t["sources"] if not str(s.get("table", "")).startswith("area ")]}
            for t in tables
        ],
    }  # fmt: skip


def _diff(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    before = {t["title"]: t for t in old["tables"]}
    for t in new["tables"]:
        o = before.get(t["title"])
        if o is None:
            continue
        rows_o = {str(r[0]): r for r in o["rows"]}
        rows_n = {str(r[0]): r for r in t["rows"]}
        for k in sorted(set(rows_o) | set(rows_n)):
            a, b = rows_o.get(k), rows_n.get(k)
            if a == b:
                continue
            parts = []
            for i, c in enumerate(t["columns"][1:], 1):
                va, vb = (a[i] if a else None), (b[i] if b else None)
                if va != vb:
                    parts.append(
                        f"{c} {va if va is not None else 'none'} to {vb if vb is not None else 'none'}"
                    )
            out.append({
                "table": t["title"], "key": k, "change": "; ".join(parts),
                "from": old["date"], "to": new["date"], "as_of": t["as_of"], "sources": t["sources"],
            })  # fmt: skip
    return out


def feed(ctx: ToolContext, area_name: str) -> dict[str, Any]:
    try:
        area = _area(ctx, area_name)
    except QuickError as e:
        return {"error": str(e)}
    k = key_of(area_name)
    index_key = f"agent/feeds/{k}/index.json"
    index: list[str] = ctx.store.get_json(index_key) or []
    snap = _snapshot(ctx, area)
    if snap["date"] not in index:
        ctx.store.put_json(f"agent/feeds/{k}/{snap['date']}.json", snap)
        index = sorted([*index, snap["date"]])[-KEEP:]
        ctx.store.put_json(index_key, index)
    snaps = [ctx.store.get_json(f"agent/feeds/{k}/{d}.json") for d in index]
    snaps = [s for s in snaps if s]
    changes: list[dict[str, Any]] = []
    for old, new in zip(snaps, snaps[1:], strict=False):
        changes += _diff(old, new)
    return {
        "area": snap["area"], "key": k, "snapshots": [s["date"] for s in snaps],
        "changes": list(reversed(changes)), "now": snap,
        "how": "the instant-answer profile kept once a day; a change is a row whose published values differ between two snapshots",
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }  # fmt: skip


def as_rss(f: dict[str, Any], link: str) -> str:
    items = "".join(
        f"<item><title>{html.escape(c['table'] + ': ' + c['key'])}</title>"
        f"<description>{html.escape(c['change'] + ' (' + c['from'] + ' to ' + c['to'] + '; as of ' + (c['as_of'] or 'n/a') + ')')}</description>"
        f"<guid isPermaLink=\"false\">{f['key']}-{c['to']}-{html.escape(c['table'])}-{html.escape(c['key'])}</guid></item>"
        for c in f["changes"][:100]
    )  # fmt: skip
    title = html.escape(f"InfraAtlas: changes in {f['area']['name']}")
    return (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{title}</title>'
            f"<link>{html.escape(link)}</link><description>{html.escape(f['how'])}</description>{items}</channel></rss>")  # fmt: skip
