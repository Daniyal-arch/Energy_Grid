"""Tier 0 of brief 32: prepared answers for the fixed questions (the area card and the `quick`
templates), built in Actions for the areas people ask most (`probes/build_prepared.py`) and
read before any query runs.

An answer is stored per area id (the hash of the area's outline, the same for every way the
area is resolved) and template key, with its build time and a fingerprint of the data it was
computed from (the app tables' retrieval dates and the lake catalogue's date). It is served only
while the fingerprint matches the data this service holds, so a new deploy or a new lake never
serves an old figure; otherwise the template runs as before.

Storage: the lake table `prepared.answers` (also copied into hot.duckdb, so a lookup is a local
index read) and one public JSON per area for the app (`answers/v1/<area_id>.json` in the
public bucket, behind Cloudflare's cache).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from tools.context import ToolContext

log = logging.getLogger(__name__)

# the template keys prepared per area (others always run)
PREPARED: list[tuple[str, int, str]] = [
    ("profile", 10, "plants"),
    ("top", 10, "plants"),
    ("top", 10, "substations"),
    ("top", 10, "data_centres"),
    ("totals", 10, "plants"),
]
_missing: set[int] = set()  # lakes (by id) without the table: not asked again


def key_of(template: str, n: int, kind: str) -> str:
    if template in ("profile", "totals"):  # n and kind do not change these answers
        n, kind = 10, "plants"
    return f"{template}:{n}:{kind}"


def fingerprint(ctx: ToolContext) -> str:
    """The data an answer depends on: the app tables' sources and the lake catalogue date."""
    lake = ctx.lake
    parts = sorted(f"{k}={v.retrieved}" for k, v in lake.sources.items())
    parts.append(f"lake={lake.catalog_date}")
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]  # noqa: S324 - a fingerprint


def lookup(
    ctx: ToolContext, template: str, area_id: str, n: int, kind: str
) -> dict[str, Any] | None:
    """The prepared answer, or None (not prepared, other data, or no hot copy to read it from)."""
    lake = ctx.lake
    if (
        id(lake) in _missing
        or not lake.hot_state.get("ready")
        or "prepared.answers" not in lake.hot_tables
    ):
        return None
    try:
        row = (
            lake.cursor()
            .execute(
                "SELECT payload, built, fingerprint FROM prepared.answers "
                "WHERE area_id = ? AND key = ?",
                [area_id, key_of(template, n, kind)],
            )
            .fetchone()
        )
    except Exception as e:  # noqa: BLE001 - the template answers instead
        log.warning("prepared answers not readable", extra={"error": str(e)[:200]})
        _missing.add(id(lake))
        return None
    if row is None or row[2] != fingerprint(ctx):
        return None
    payload = json.loads(row[0])
    payload["data"]["prepared"] = {
        "built": row[1],
        "how": "prepared in advance from the same data and SQL",
    }
    return payload
