"""Cost of a model call: usage x the registry's prices (agent/models.yaml), in US dollars."""

from __future__ import annotations

from typing import Any


def usage_of(message: Any) -> dict[str, int]:
    """Input, output, cache-read and cache-write tokens from a LangChain AIMessage."""
    um = getattr(message, "usage_metadata", None) or {}
    details = um.get("input_token_details") or {}
    return {
        "input": int(um.get("input_tokens") or 0),
        "output": int(um.get("output_tokens") or 0),
        "cache_read": int(details.get("cache_read") or 0),
        "cache_write": int(details.get("cache_creation") or 0),
    }


def cost_usd(usage: dict[str, int], prices: dict[str, Any] | None) -> float | None:
    """`input` counts every prompt token (LangChain's convention: cached ones included)."""
    if not prices:
        return None
    m = 1e-6
    read = usage.get("cache_read", 0)
    write = usage.get("cache_write", 0)
    fresh = max(0, usage.get("input", 0) - read - write)
    total = (
        fresh * float(prices.get("input") or 0) * m
        + read * float(prices.get("cache_read") or prices.get("input") or 0) * m
        + write * float(prices.get("cache_write") or prices.get("input") or 0) * m
        + usage.get("output", 0) * float(prices.get("output") or 0) * m
    )
    return round(total, 6)
