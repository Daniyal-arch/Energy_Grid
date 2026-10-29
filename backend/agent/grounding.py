"""The deterministic grounding check: every number in the answer must be in this turn's tool
results, within the precision the answer shows.

A number in the text (1,234.5 / -3 / 12.3 % / 4.2k) matches a value v when v rounded to the
text's decimals equals it, also after a factor of 1,000, 1,000,000 or 1/1,000 (MW shown as GW,
...) or 100 (shares shown as per cent). Left out: years (1900-2100 without decimals), dates,
integers up to 12 (counts like "top 5", months), numbers in the question, and numbers inside
table or code names.
"""

from __future__ import annotations

import contextlib
import json
import re
from typing import Any

NUM = re.compile(
    r"(?<![\w.])-?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\w])|(?<![\w.,])-?\d+(?:\.\d+)?(?![\w])"
)
# thousands written with a space (plain, no-break, thin or narrow no-break): "65 690" is 65690
GROUPS = re.compile(r"(?<=\d)[ \u00a0\u2009\u202f](?=\d{3}(?!\d))")
DATE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b")
CODE = re.compile(r"`[^`]*`|\b[A-Za-z_]+\d+[A-Za-z_\d]*\b|\b[A-Za-z_]\w*\.\w+\b")
SCALES = (1.0, 1e3, 1e-3, 1e6, 1e-6, 100.0, 0.01)


def numbers_in_text(text: str) -> list[tuple[str, float, int]]:
    """(as written, value, decimals) for each number that needs grounding."""
    clean = DATE.sub(" ", GROUPS.sub("", text))
    clean = CODE.sub(" ", clean)
    out = []
    for m in NUM.finditer(clean):
        raw = m.group(0)
        v = float(raw.replace(",", ""))
        dec = len(raw.split(".")[1]) if "." in raw else 0
        if dec == 0 and (1900 <= abs(v) <= 2100 or abs(v) <= 12):
            continue
        out.append((raw, v, dec))
    return out


def values_in(obj: Any, acc: set[float] | None = None) -> set[float]:
    acc = set() if acc is None else acc
    if isinstance(obj, bool):
        return acc
    if isinstance(obj, int | float):
        acc.add(float(obj))
    elif isinstance(obj, str):
        for raw in NUM.findall(obj):
            with contextlib.suppress(ValueError):
                acc.add(float(raw.replace(",", "")))
    elif isinstance(obj, dict):
        for v in obj.values():
            values_in(v, acc)
    elif isinstance(obj, list | tuple):
        for v in obj:
            values_in(v, acc)
    return acc


def matches(n: float, dec: int, values: set[float]) -> bool:
    tol = 0.5 * 10**-dec + 1e-9
    for v in values:
        for k in SCALES:
            if abs(v / k - n) <= tol or abs(round(v / k, dec) - n) <= 1e-9:
                return True
    return False


def check(answer: str, tool_results: list[Any], question: str = "") -> dict[str, Any]:
    values = values_in(tool_results)
    asked = {v for _, v, _ in numbers_in_text(question)}
    found, missing = [], []
    for raw, v, dec in numbers_in_text(answer):
        if v in asked or matches(v, dec, values):
            found.append(raw)
        else:
            missing.append(raw)
    total = len(found) + len(missing)
    return {
        "numbers": total,
        "grounded": len(found),
        "ungrounded": missing,
        "score": 1.0 if total == 0 else round(len(found) / total, 3),
    }


def tool_payloads(tool_log: list[dict[str, Any]]) -> list[Any]:
    """Each tool result's data and sources (a source line may hold numbers too)."""
    return [
        json.loads(
            json.dumps({k: t.get("result", {}).get(k) for k in ("data", "sources")}, default=str)
        )
        for t in tool_log
    ]
