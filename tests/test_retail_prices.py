"""Retail prices: JSON-stat cells from Eurostat (scripts/fetch_retail_prices.py)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_retail_prices import cells  # noqa: E402


def test_jsonstat_cells_are_row_major_with_flags() -> None:
    d = {
        "id": ["geo", "tax", "time"],
        "size": [2, 2, 2],
        "dimension": {
            "geo": {"category": {"index": {"DE": 0, "EL": 1}}},
            "tax": {"category": {"index": {"I_TAX": 0, "X_TAX": 1}}},
            "time": {"category": {"index": {"2025-S2": 0, "2026-S1": 1}}},
        },
        # flat index = geo * 4 + tax * 2 + time
        "value": {"0": 0.3869, "1": 0.3618, "3": 0.2388, "5": 0.25},
        "status": {"5": "p", "6": ":"},
    }
    c = cells(d)
    assert c[("DE", "I_TAX", "2025-S2")] == (0.3869, None)
    assert c[("DE", "I_TAX", "2026-S1")] == (0.3618, None)
    assert c[("DE", "X_TAX", "2026-S1")] == (0.2388, None)
    assert c[("EL", "I_TAX", "2026-S1")] == (0.25, "p")
    assert c[("EL", "X_TAX", "2025-S2")] == (None, ":")  # a flag without a value
    assert ("DE", "X_TAX", "2025-S2") not in c
