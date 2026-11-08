"""Brief 32 Tier 1: hot.duckdb attached in the background; queries read its tables (same rows
as the lake) and the lake for the rest; a missing file leaves the lake answering."""

from __future__ import annotations

import duckdb

from data.duck import Lake
from tests.conftest import LAKE, TMP, settings


def _hot_file() -> str:
    path = TMP / "hot" / "hot.duckdb"
    path.parent.mkdir(exist_ok=True)
    path.unlink(missing_ok=True)
    con = duckdb.connect(str(path))
    con.execute("CREATE SCHEMA registers")
    con.execute(
        f"CREATE TABLE registers.gb AS SELECT * FROM read_parquet('{LAKE}/registers/gb.parquet')"
    )
    con.close()
    return str(path)


def test_hot_tables_answer_and_the_rest_reads_the_lake():
    lake = Lake(settings(hot_db=_hot_file()))
    assert lake.wait_hot(30) and lake.hot_state["tables"] == 1
    r = lake.run('SELECT "group", sum(mw) FROM registers.gb GROUP BY 1 ORDER BY 1')
    cold = Lake(settings(hot_db=""))
    want = cold.run('SELECT "group", sum(mw) FROM registers.gb GROUP BY 1 ORDER BY 1')
    assert r.rows == want.rows and r.tier == "hot" and want.tier == "lake"
    other = lake.run("SELECT count(*) FROM gem_plants.units")
    assert other.rows == [[3]] and other.tier == "lake"


def test_missing_hot_file_keeps_the_lake():
    lake = Lake(settings(hot_db=str(TMP / "hot" / "nope.duckdb")))
    assert not lake.wait_hot(30) and "error" in lake.hot_state
    assert lake.run("SELECT count(*) FROM registers.gb").rows == [[4]]
