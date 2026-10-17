"""The lake catalogue (scripts/lake_catalog.py): totals and topic-view column picks."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import lake_catalog as lc  # noqa: E402


def test_summary_sums_tables() -> None:
    out = {"path": "lake/eaglei/outages/year=*/*.parquet", "rows": 10, "bytes": 100, "columns": {}}
    cty = {"path": "lake/eaglei/counties/*.parquet", "rows": 2, "bytes": 5, "columns": {}}
    cats = {
        "eaglei": {
            "source": "s",
            "licence": "l",
            "updated": "u",
            "tables": {"outages": out, "counties": cty},
        }
    }
    s = lc.summary(cats)
    assert s["rows"] == 12 and s["bytes"] == 105
    assert s["datasets"]["eaglei"]["tables"]["outages"]["rows"] == 10


def test_pick() -> None:
    cols = {"Plant_Name": "VARCHAR", "gross_kw": "DOUBLE", "start": "TIMESTAMP"}
    assert lc.pick(cols, ["name", "plant_name"]) == '"Plant_Name"'
    assert lc.pick(cols, ["gross_kw / 1000"]) == "gross_kw / 1000"
    assert lc.pick(cols, ['"start"']) == '"start"'
    assert lc.pick(cols, ["missing"]) == "NULL"
    assert lc.pick(cols, ["'t CO2e'"]) == "'t CO2e'"
