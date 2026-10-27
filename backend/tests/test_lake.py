import pytest

from data.duck import Lake
from data.guard import GuardError
from tests.conftest import LAKE, settings


@pytest.fixture(scope="module")
def lake():
    return Lake(settings(lake_dir=LAKE, sql_timeout_s=1.0))


def test_fixture_lake_views_and_app_tables(lake):
    tables = lake.tables()
    assert {
        "registers.gb",
        "eaglei.outages",
        "gem_plants.units",
        "app.eu_plants",
        "app.eu_prices",
    } <= set(tables)
    assert lake.catalog_date == "2026-10-27T00:00:00Z"


def test_catalogue_example_style_query(lake):
    r = lake.run(
        "SELECT sum(customers_out) * 0.25 FROM eaglei.outages WHERE fips = '48201' AND ts >= '2024-01-01' AND ts < '2025-01-01'"
    )
    assert r.rows == [[2007.0]]
    r = lake.run(
        """SELECT "group", round(sum(mw)) FROM registers.gb WHERE status = 'operating' GROUP BY 1 ORDER BY 1"""
    )
    assert r.rows[0] == ["solar", 50.0]


def test_hive_partition_column(lake):
    assert lake.run("SELECT DISTINCT year FROM eaglei.outages").rows == [[2024]]


def test_lockdown_blocks_files_even_without_the_guard(lake):
    for sql in (
        "SELECT * FROM read_csv('/etc/passwd')",
        "COPY (SELECT 1) TO '/tmp/atlas-x.csv'",
        "INSTALL tpch",
    ):
        with pytest.raises(Exception, match="(?i)permission|disabled"):
            lake.run(sql, guard=False)
    with pytest.raises(Exception, match="(?i)locked|configuration"):
        lake.run("SET enable_external_access = true", guard=False)


def test_guard_runs_first(lake):
    with pytest.raises(GuardError):
        lake.run("SELECT * FROM read_csv('/etc/passwd')")


def test_timeout(lake):
    with pytest.raises(TimeoutError):
        lake.run("SELECT count(*) FROM range(100000000000) a", timeout_s=0.3)


def test_rows_kept_cap():
    lk = Lake(settings(lake_dir=LAKE, sql_rows_kept=10))
    r = lk.run("SELECT * FROM range(50)")
    assert len(r.rows) == 10 and r.truncated
