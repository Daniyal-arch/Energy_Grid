"""resolve_area (docs/tasks/27, A1): any area a question means, as one record with an id.

From the view (the drawn polygon or circle, the countries, the map on screen), from text (the
gazetteer and the outline sets, ranked by level and population; ambiguous names come back as
candidates with their parents), named groups (agent/areas/groups.yaml), unions of several
names, a circle around a point or a place, a buffer around an area, an intersection with
another area. Every area gets its own figures (geodesic area; people inside from the GHSL
raster when area_stats can read it) and is kept under its `area_id` for run_sql's `in_area`,
area_stats and maps.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from data.areas import LEVEL_CLASS, LEVEL_WORDS, Area, AreaError, Candidate
from tools.context import ToolContext, result


class ResolveAreaArgs(BaseModel):
    names: list[str] = Field(
        default_factory=list,
        max_length=30,
        description="One place ('Bavaria', 'Paris, Texas', 'Limburg (NL)', 'Nordics', 'world') "
        "or several for their union; a candidate's ref ('nuts:DE21') picks it exactly",
    )
    level: str | None = Field(
        default=None,
        description="The level meant: country, region, county, city, neighbourhood, or an exact "
        "one (nuts2, us_tract, lsoa, iris, nl_buurt, urban_centre, bidding_zone ...)",
    )
    from_view: Literal["drawn", "screen", "countries"] | None = Field(
        default=None,
        description="'drawn': the polygon or circle the user drew; 'screen': the map on screen; "
        "'countries': the countries selected in the app",
    )
    point: tuple[float, float] | None = Field(default=None, description="[lon, lat] of a circle")
    radius_km: float | None = Field(
        default=None,
        gt=0,
        le=2000,
        description="a circle of this radius around `point` or around the named place's centre",
    )
    buffer_km: float | None = Field(
        default=None, gt=0, le=500, description="grow the resolved area by this distance"
    )
    intersect_with: str | None = Field(
        default=None, pattern=r"^a_[0-9a-f]{12}$", description="clip to another area's outline"
    )
    name: str | None = Field(default=None, max_length=120, description="label for the result")


def _people(ctx: ToolContext, area: Area) -> None:
    """The area's population from the GHSL raster, when area_stats can read it (A4)."""
    try:
        from tools.area_stats import people_in

        fig = people_in(ctx, area)
    except Exception as e:  # the outline stands without it
        fig = {"value": None, "note": f"population not computed: {str(e)[:160]}"}
    if fig:
        area.figures["people"] = fig
        ctx.area_store.put(area)


def _from_view(ctx: ToolContext, which: str) -> Area:
    v = ctx.view or {}
    A = ctx.areas
    if which == "drawn":
        d = v.get("drawn")
        if not d:
            raise AreaError("nothing is drawn on the map; ask the user to draw an area")
        if d.get("kind") == "circle":
            return A.circle(d["at"][0], d["at"][1], float(d["r"]), d.get("name"))
        if d.get("kind") == "shape" and d.get("area_id"):
            a = ctx.area_store.get(str(d["area_id"]))
            if a is not None:
                return a
        if d.get("kind") == "shape":
            polys = [
                [[[r[i], r[i + 1]] for i in range(0, len(r), 2)] for r in p] for p in d["polygons"]
            ]
            return A.polygon(polys, d.get("name") or "Drawn area")
        ring = [list(p) for p in d["ring"]]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        return A.polygon([[ring]], d.get("name") or "Drawn area")
    if which == "countries":
        codes = v.get("area") or []
        if not codes:
            raise AreaError("no countries are selected in the app")
        return A.union([A.country(c) for c in codes], name=", ".join(codes), level="group")
    b = (v.get("camera") or {}).get("bounds")
    if not b:
        raise AreaError("the view sent no camera bounds")
    x0, y0, x1, y1 = b
    ring = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
    return A.polygon([[ring]], "The map on screen", level="bbox")


def resolve_area(
    ctx: ToolContext,
    names: list[str] | None = None,
    level: str | None = None,
    from_view: str | None = None,
    point: tuple[float, float] | None = None,
    radius_km: float | None = None,
    buffer_km: float | None = None,
    intersect_with: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    A = ctx.areas
    names = [n for n in (names or []) if n.strip()]
    candidates: list[Candidate] = []
    notes: list[str] = []
    ambiguous = False
    try:
        if from_view:
            area = _from_view(ctx, from_view)
        elif point and radius_km:
            area = A.circle(point[0], point[1], radius_km, name)
        elif names:
            parts: list[Area] = []
            for n in names:
                ref = n if ":" in n and " " not in n else None
                found = A.search(n, level=level, view=ctx.view) if ref is None else []
                if ref:
                    kind, _, key = ref.partition(":")
                    pick = Candidate(
                        ref, key, kind, [], None, None, None, {"dataset": kind, "licence": ""}
                    )
                    pick = next((c for c in A.search(key, view=ctx.view) if c.ref == ref), pick)
                elif not found:
                    notes.append(
                        f"no outline or place named {n!r} in the gazetteer or outline sets"
                    )
                    continue
                else:
                    pick = found[0]
                    exact = [c for c in found if c.match == 0]
                    cls = LEVEL_CLASS.get(pick.level, 3)
                    others = {
                        (tuple(c.iso3), c.parent)
                        for c in exact
                        if LEVEL_CLASS.get(c.level, 3) == cls
                    }
                    if len(names) == 1:
                        candidates = found
                    if len(others) > 1:
                        ambiguous = True
                        notes.append(
                            f"{n!r} matches {len(others)} places of this level in different "
                            "countries or "
                            f"regions; picked {pick.name} ({', '.join(pick.iso3)}"
                            f"{', ' + pick.parent if pick.parent else ''}) by view and population. "
                            "Name the other with its ref if it was meant."
                        )
                    want = LEVEL_WORDS.get(level or "", LEVEL_CLASS.get(level or "", -1))
                    if want >= 0 and LEVEL_CLASS.get(pick.level, 5) != want and pick.outline:
                        notes.append(
                            f"no outline at level {level!r} for {n!r}; the nearest is "
                            f"{pick.name} as {pick.level}"
                        )
                if not pick.outline:
                    if radius_km and pick.point:
                        parts.append(A.circle(pick.point[0], pick.point[1], radius_km, pick.name))
                        continue
                    notes.append(
                        f"{pick.name} is a point in {pick.source['dataset']}: no outline at this "
                        "level in the lake; offer its municipality or urban centre (outline "
                        "sets) or a circle around it (radius_km)"
                    )
                    continue
                if radius_km:
                    area0 = A.from_candidate(pick)
                    cx = (area0.bbox[0] + area0.bbox[2]) / 2
                    cy = (area0.bbox[1] + area0.bbox[3]) / 2
                    parts.append(A.circle(cx, cy, radius_km, pick.name))
                    notes.append(
                        f"circle centred on the middle of {pick.name}'s bounding box "
                        f"[{cx:.4f}, {cy:.4f}]"
                    )
                    continue
                parts.append(A.from_candidate(pick))
            if not parts:
                return result(
                    {
                        "area": None,
                        "candidates": [c.as_dict() for c in candidates],
                        "note": " ".join(notes),
                    },
                    [],
                )
            label = name or (
                parts[0].name if len(parts) == 1 else " + ".join(p.name for p in parts)
            )
            area = A.union(parts, name=label, level="group" if len(parts) > 1 else parts[0].level)
        else:
            raise AreaError("give names, a point with radius_km, or from_view")
        if buffer_km:
            gj = A.buffer(json.dumps(area.geometry), buffer_km)
            area = A.make(
                gj,
                name=name or f"{area.name} and {buffer_km:g} km around it",
                level="polygon",
                iso3=area.iso3,
                parents=[area.name, *area.parents],
                source=area.source,
                how=f"{area.how}; grown by {buffer_km:g} km (azimuthal equidistant projection "
                "centred on the area)",
            )
        if intersect_with:
            other = ctx.area_store.get(intersect_with)
            if other is None:
                raise AreaError(f"unknown area {intersect_with}; resolve it first")
            area = A.intersect(area, other)
        if name and area.name != name and not buffer_km:
            area.name = name
            ctx.area_store.put(area)
    except AreaError as e:
        return result(
            {"area": None, "candidates": [c.as_dict() for c in candidates], "error": str(e)}, []
        )
    if "people" not in area.figures:
        _people(ctx, area)
    if area.area_id not in ctx.turn_areas:
        ctx.turn_areas.append(area.area_id)
    ctx.emit("area", {"area_id": area.area_id, "name": area.name, "level": area.level})
    data: dict[str, Any] = {
        "area": area.summary(),
        "use": f"run_sql: WHERE in_area(lon, lat, '{area.area_id}'); "
        f"area_stats(area_id='{area.area_id}'); MapSpec area: {{'area_id': '{area.area_id}'}}",
    }
    if area.level in ("country", "group", "nuts0"):
        data["use"] += (
            "; tables with a country key: filter by the area's iso3 codes instead (generalised "
            "outlines leave coastal and offshore records outside)"
        )
    data["datasets_at_level"] = ctx.areas.datasets_at(area.level)
    if candidates and (ambiguous or len(candidates) > 1):
        data["candidates"] = [c.as_dict() for c in candidates[:6]]
    if ambiguous:
        data["ambiguous"] = True
    if notes:
        data["note"] = " ".join(notes)
    src = {
        "dataset": area.source.get("dataset", "area"),
        "table": f"area {area.area_id}",
        "licence": area.source.get("licence", ""),
        "retrieved": area.how[:200],
    }
    return result(data, [src])
