"""Scorers for one evaluated question: the expected numbers within the source's precision, every
number grounded, sources listed, the MapSpec valid with the expected kind and key, latency, cost."""

from __future__ import annotations

from typing import Any

from agent.grounding import numbers_in_text
from agent.mapspec import MapSpec


def _value(raw: str) -> tuple[float, int]:
    clean = raw.replace(",", "")
    return float(clean), (len(clean.split(".")[1]) if "." in clean else 0)


def number_correct(expected: list[str], answer: str) -> float:
    """Share of expected numbers found in the answer at the expected number's precision (an answer
    may show more decimals; GW for MW and per cent for shares are accepted)."""
    if not expected:
        return 1.0
    shown = [v for _, v, _ in numbers_in_text(answer)] + [
        _value(r)[0] for r in expected if r in answer
    ]
    hits = 0
    for raw in expected:
        e, dec = _value(raw)
        tol = 0.5 * 10**-dec + 1e-9
        if any(abs(round(v * k, dec) - e) <= tol for v in shown for k in (1, 1e3, 1e-3, 0.01, 100)):
            hits += 1
    return round(hits / len(expected), 3)


def map_correct(expected: dict[str, str], maps: list[dict[str, Any]]) -> float:
    """1 when a valid MapSpec has an overlay of the expected kind placed by the expected key."""
    for m in maps:
        try:
            spec = MapSpec.model_validate(m["spec"])
        except Exception:
            continue
        for o in spec.overlays:
            placed = "lon/lat" if (o.data.lon and o.data.lat) else (o.data.key or "")
            if o.kind == expected["kind"] and (
                placed == expected["key"] or expected["key"] in placed
            ):
                return 1.0
        if spec.app and spec.app.layers and expected["kind"] == "points":
            return 0.5  # an existing layer switched on: right idea, not checkable here
    return 0.0


def score(question: dict[str, Any], out: dict[str, Any]) -> dict[str, Any]:
    run = out.get("run", {})
    g = run.get("grounding", {})
    s: dict[str, Any] = {
        "id": question["id"],
        "grounded": g.get("score", 1.0 if not g.get("numbers") else 0.0),
        "sources": 1.0 if run.get("sources") else 0.0,
        "latency_ms": run.get("latency_ms"),
        "cost_usd": run.get("cost_usd"),
        "tool_calls": len(run.get("tool_calls", [])),
        "stop": run.get("stop"),
    }
    if "numbers" in question:
        s["correct"] = number_correct(question["numbers"], out.get("answer", ""))
    if "map" in question:
        s["map"] = map_correct(question["map"], out.get("maps", []))
    return s
