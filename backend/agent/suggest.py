"""Follow-up suggestions computed from the data, not by the model (brief 30 Track 4.7).

After an answer about an area, the chips offer the instant answers (tools/quick.py) that have
data there: its profile, its largest plants, what is published, and its prices where the area's
countries have bidding zones in the prices table. Each chip is a question the quick router
matches, so it is answered at once and with no model call.
"""

from __future__ import annotations

from typing import Any

from tools.context import ToolContext
from tools.quick import ISO3_TO_ISO2, match


def suggestions(ctx: ToolContext, area_ids: list[str], asked: str) -> list[str]:
    out: list[str] = []
    for aid in area_ids[-2:]:
        a = ctx.area_store.get(aid)
        if a is None or not a.name:
            continue
        name = a.name
        qs = [
            f"Tell me about {name}",
            f"Top 10 power plants in {name}",
            f"What is published for {name}?",
        ]
        codes = [ISO3_TO_ISO2.get(i, i) for i in a.iso3]
        if codes and _has_prices(ctx, codes):
            qs.append(f"Prices in {name}")
        out += [q for q in qs if match(q) and q.lower() != asked.strip().lower()]
    return list(dict.fromkeys(out))[:4]


def _has_prices(ctx: ToolContext, codes: list[str]) -> bool:
    lst = ", ".join(f"'{c}'" for c in codes if c.isalpha() and len(c) == 2)
    if not lst:
        return False
    try:
        r = ctx.lake.run(
            f"SELECT count(*) FROM app.eu_prices WHERE country IN ({lst})", guard=False
        )
        return bool(r.rows and r.rows[0][0])
    except Exception:  # noqa: BLE001 - no prices table: no chip
        return False


def area_ids_of(state: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for t in state.get("tool_log") or []:
        data = (t.get("result") or {}).get("data")
        if isinstance(data, dict):
            a = data.get("area")
            for x in a if isinstance(a, list) else [a]:
                if isinstance(x, dict) and x.get("area_id"):
                    ids.append(x["area_id"])
    return list(dict.fromkeys(ids))
