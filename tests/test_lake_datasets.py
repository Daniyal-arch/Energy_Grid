"""Helpers of scripts/build_lake_datasets.py."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_lake_datasets as bld  # noqa: E402


def test_snake() -> None:
    assert bld.snake("Plant ID") == "plant_id"
    assert bld.snake("pointKey") == "pointkey"
    assert bld.snake("respondent-name") == "respondent_name"


def test_load_rows_types_and_names(tmp_path: Path) -> None:
    con = duckdb.connect()
    names = bld.load_rows(
        con,
        "t",
        [{"Plant ID": 1, "MW": "2.5", "Name": 'a "quoted", name'}, {"Plant ID": 2, "Extra": "x"}],
        tmp_path,
    )
    assert names == ["plant_id", "mw", "name", "extra"]
    rows = con.execute("SELECT plant_id, mw, name, extra FROM t ORDER BY 1").fetchall()
    assert rows == [(1, 2.5, 'a "quoted", name', None), (2, None, None, "x")]
