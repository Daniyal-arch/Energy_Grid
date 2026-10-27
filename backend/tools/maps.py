"""make_map and make_chart: validate a spec, store it with its data, send it to the browser."""

from __future__ import annotations

import re
import secrets
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from agent.mapspec import ChartSpec, MapSpec
from tools.context import ToolContext, result


class MakeMapArgs(BaseModel):
    spec: dict[str, Any] = Field(description="A MapSpec (agent/mapspec.schema.json)")


class MakeChartArgs(BaseModel):
    spec: dict[str, Any] = Field(description="A ChartSpec (agent/mapspec.schema.json)")


@lru_cache
def known_layers(root: str) -> frozenset[str]:
    """LayerId values of the app (frontend/src/app/store.ts LAYERS)."""
    p = Path(root) / "frontend" / "src" / "app" / "store.ts"
    if not p.exists():
        return frozenset()
    text = p.read_text()
    start = text.find("export const LAYERS")
    end = text.find("];", start)
    return frozenset(re.findall(r'\{\s*id:\s*"([A-Za-z0-9_]+)"', text[start:end]))


def errors_text(e: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()[:8]
    )


def check_map(
    ctx: ToolContext, spec: dict[str, Any]
) -> tuple[MapSpec | None, str | None, dict[str, Any]]:
    """Validate a MapSpec and its data references; returns (spec, error, results by id)."""
    try:
        m = MapSpec.model_validate(spec)
    except ValidationError as e:
        return None, errors_text(e), {}
    layers = known_layers(str(ctx.settings.atlas_root))
    if m.app and layers:
        bad = [x for x in m.app.layers if x not in layers]
        if bad:
            return None, f"unknown app layers {bad}; known: {sorted(layers)}", {}
    data: dict[str, Any] = {}
    for o in m.overlays:
        if o.data.result_id:
            r = ctx.results.get(o.data.result_id)
            if r is None:
                return None, f"overlay {o.id}: unknown result_id {o.data.result_id}", {}
            cols = set(r["columns"])
            data[o.data.result_id] = r
        else:
            rows = o.data.inline or []
            cols = set(rows[0].keys()) if rows else set()
        needed = [
            c
            for c in (
                o.data.key,
                o.data.lon,
                o.data.lat,
                o.data.from_lon,
                o.data.from_lat,
                o.data.to_lon,
                o.data.to_lat,
                o.label,
                o.value.column if o.value else None,
                o.size.column if o.size else None,
                *o.tooltip,
            )
            if c
        ]
        missing = [c for c in needed if c not in cols]
        if missing:
            return (
                None,
                f"overlay {o.id}: columns {missing} not in the data (has {sorted(cols)})",
                {},
            )
    return m, None, data


def make_map(ctx: ToolContext, spec: dict[str, Any]) -> dict[str, Any]:
    m, err, data = check_map(ctx, spec)
    if m is None:
        return result({"error": f"invalid MapSpec: {err}"}, [])
    map_id = "m_" + secrets.token_hex(6)
    sources = [s for r in data.values() for s in r.get("sources", [])]
    record = {
        "id": map_id,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "spec": m.model_dump(exclude_none=True),
        "data": {rid: {"columns": r["columns"], "rows": r["rows"]} for rid, r in data.items()},
        "sources": sources,
    }
    ctx.store.put_json(f"agent/maps/{map_id}.json", record)
    ctx.emit("map", {"id": map_id, "spec": record["spec"]})
    return result({"map_id": map_id, "link": f"?map={map_id}"}, sources)


def make_chart(ctx: ToolContext, spec: dict[str, Any]) -> dict[str, Any]:
    try:
        c = ChartSpec.model_validate(spec)
    except ValidationError as e:
        return result({"error": f"invalid ChartSpec: {errors_text(e)}"}, [])
    rows: list[dict[str, Any]]
    sources: list[dict[str, str]] = []
    if c.data.result_id:
        r = ctx.results.get(c.data.result_id)
        if r is None:
            return result({"error": f"unknown result_id {c.data.result_id}"}, [])
        if len(r["rows"]) > 2000:
            return result({"error": "a chart takes at most 2,000 points; aggregate first"}, [])
        rows = [dict(zip(r["columns"], row, strict=False)) for row in r["rows"]]
        sources = r.get("sources", [])
    else:
        rows = list(c.data.inline or [])
    cols = set(rows[0].keys()) if rows else set()
    missing = [x for x in (c.x.column, *(s.column for s in c.series)) if x not in cols]
    if missing:
        return result({"error": f"columns {missing} not in the data"}, [])
    chart = {"spec": c.model_dump(exclude_none=True), "rows": rows}
    ctx.emit("chart", chart)
    return result({"chart": "sent", "points": len(rows)}, sources)
