"""Query results kept server-side under a `result_id` (in /tmp; copied into a saved map's
record on R2 when a map uses it). The model sees at most `sql_rows_returned` rows; maps and
charts read the full result by id.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any


class ResultStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self, columns: list[str], rows: list[list[Any]], *, sql: str, sources: list[dict]
    ) -> str:
        rid = "r_" + secrets.token_hex(6)
        (self.root / f"{rid}.json").write_text(
            json.dumps(
                {"columns": columns, "rows": rows, "sql": sql, "sources": sources}, default=str
            )
        )
        return rid

    def get(self, rid: str) -> dict[str, Any] | None:
        if not rid.startswith("r_") or not rid[2:].isalnum():
            return None
        p = self.root / f"{rid}.json"
        return json.loads(p.read_text()) if p.exists() else None

    def summary(self, rid: str) -> dict[str, Any] | None:
        r = self.get(rid)
        if r is None:
            return None
        return {
            "result_id": rid,
            "columns": r["columns"],
            "rows": len(r["rows"]),
            "sample": r["rows"][:5],
            "sources": r["sources"],
        }
