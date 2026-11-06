"""The result cache (brief 30 Track 4.3): tool results keyed by the tool, its normalised
arguments (SQL with whitespace and case of keywords folded) and the lake catalogue's date, kept
locally (`results_dir/cache/`) and in the object store (`agent/cache/<key>.json`, R2 in Lambda),
with a size cap and an expiry. A new lake catalogue date changes every key, so old entries are
never read again (they expire). A hit restores the result's rows under the same result id, so
maps and charts built from it still work, and the trace marks the call "cached".

Only deterministic reads are cached; `live` (the newest interval) and the map and skill tools
are not.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from tools.context import ToolContext

CACHEABLE = {"run_sql", "quick", "area_stats", "describe_table", "search_catalog", "site_figures"}
TTL_S = 7 * 24 * 3600
MAX_BYTES = 512_000  # one entry, serialised; larger results are not cached
MAX_LOCAL = 2_000  # entries on local disk; the oldest go first


def _norm_sql(sql: str) -> str:
    """Whitespace and case folded, a trailing semicolon dropped; string literals and quoted
    identifiers kept as written."""
    parts = re.split(r"('(?:[^']|'')*'|\"(?:[^\"]|\"\")*\")", sql.strip().rstrip(";"))
    return "".join(
        p if p[:1] in ("'", '"') else re.sub(r"\s+", " ", p).lower() for p in parts
    ).strip()


def key_of(name: str, args: dict[str, Any], catalog_date: str | None) -> str:
    a = dict(args)
    if "sql" in a and isinstance(a["sql"], str):
        a["sql"] = _norm_sql(a["sql"])
    raw = json.dumps([name, a, catalog_date or ""], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class ResultCache:
    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx
        self.dir = Path(ctx.settings.results_dir) / "cache"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _date(self) -> str | None:
        return getattr(self.ctx.lake, "catalog_date", None)

    def get(self, name: str, args: dict[str, Any]) -> dict[str, Any] | None:
        if name not in CACHEABLE:
            return None
        k = key_of(name, args, self._date())
        p = self.dir / f"{k}.json"
        entry = None
        if p.exists():
            entry = json.loads(p.read_text(encoding="utf-8"))
        else:
            try:
                entry = self.ctx.store.get_json(f"agent/cache/{k}.json")
            except Exception:  # noqa: BLE001 - a store miss or outage is a cache miss
                entry = None
            if entry:
                p.write_text(json.dumps(entry, default=str), encoding="utf-8")
        if not entry or time.time() - entry.get("at", 0) > TTL_S:
            return None
        res = entry["result"]
        if res.get("result_id") and entry.get("record"):
            self.ctx.results.put(res["result_id"], entry["record"])
        return res

    def put(self, name: str, args: dict[str, Any], res: dict[str, Any]) -> None:
        if name not in CACHEABLE:
            return
        data = res.get("data")
        if isinstance(data, dict) and "error" in data:
            return  # failures are not cached: the next try may work
        record = self.ctx.results.get(res["result_id"]) if res.get("result_id") else None
        entry = {"at": time.time(), "tool": name, "result": res, "record": record}
        raw = json.dumps(entry, default=str)
        if len(raw) > MAX_BYTES:
            return
        k = key_of(name, args, self._date())
        (self.dir / f"{k}.json").write_text(raw, encoding="utf-8")
        with contextlib.suppress(Exception):  # the local copy still serves this instance
            self.ctx.store.put_json(f"agent/cache/{k}.json", entry)
        files = sorted(self.dir.glob("*.json"), key=lambda f: f.stat().st_mtime)
        for f in files[: max(0, len(files) - MAX_LOCAL)]:
            f.unlink(missing_ok=True)
