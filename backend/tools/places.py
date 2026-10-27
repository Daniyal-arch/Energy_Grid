"""find_place: a country, US state, bidding zone, city or coordinates -> codes, centre, bbox."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from tools.context import ToolContext, result


class FindPlaceArgs(BaseModel):
    text: str = Field(
        description="A place name or code ('Texas', 'NL', 'DK1', 'Lyon') or coordinates "
        "('52.37 N, 4.90 E')"
    )


def find_place(ctx: ToolContext, text: str) -> dict[str, Any]:
    places = ctx.gazetteer.find(text)
    if not places:
        return result({"places": [], "note": "no match in the map's outlines and gazetteer"}, [])
    sources = []
    for p in places:
        src = {"dataset": "places", "table": p.kind, "licence": "see source", "retrieved": p.source}
        if src not in sources:
            sources.append(src)
    return result({"places": [p.as_dict() for p in places]}, sources)
