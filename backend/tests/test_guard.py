import pytest

from data.guard import GuardError, check

ALLOWED = ["/data/public/", "https://raw.githubusercontent.com/x/eu-days/eu/"]

ATTACKS = [
    "DROP TABLE app.eu_plants",
    "DELETE FROM app.eu_plants",
    "INSERT INTO app.eu_plants VALUES (1)",
    "UPDATE app.eu_plants SET mw = 0",
    "CREATE TABLE t AS SELECT 1",
    "ALTER TABLE app.eu_plants ADD COLUMN x INT",
    "ATTACH '/tmp/other.db' AS o",
    "DETACH lake",
    "COPY (SELECT 1) TO '/tmp/x.csv'",
    "INSTALL tpch",
    "LOAD httpfs",
    "SET enable_external_access = true",
    "PRAGMA database_list",
    "SELECT 1; SELECT 2",
    "SELECT 1; DROP TABLE x",
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT * FROM read_parquet('s3://other-bucket/x.parquet')",
    "SELECT * FROM read_parquet(['/data/public/x.parquet', '/etc/shadow'])",
    "SELECT * FROM read_text('/data/public/../../etc/passwd')",
    "SELECT * FROM read_json(concat('/etc/', 'passwd'))",
    "SELECT * FROM '/etc/passwd'",
    "SELECT * FROM 'https://evil.example/x.parquet'",
    "SELECT getenv('AWS_SECRET_ACCESS_KEY')",
    "SELECT * FROM duckdb_secrets()",
    "SELECT * FROM duckdb_settings()",
    "SELECT current_setting('s3_secret_access_key')",
    "SELECT * FROM query('DROP TABLE x')",
    "SELECT * FROM query_table('app.eu_plants')",
    "SELECT * FROM pragma_database_list()",
    "SELECT * FROM glob('/root/*')",
    "WITH x AS (SELECT 1) DELETE FROM app.eu_plants",
    "SELECT name, mw FROM gem_plants.units",
    "SELECT * FROM gem_plants.units",
    "",
]


@pytest.mark.parametrize("sql", ATTACKS)
def test_attacks_refused(sql):
    with pytest.raises(GuardError):
        check(sql, allowed_paths=ALLOWED, max_rows=100)


def test_select_passes_and_gets_a_limit():
    c = check(
        "SELECT fuel, sum(mw) FROM app.eu_plants GROUP BY 1", allowed_paths=ALLOWED, max_rows=100
    )
    assert c.limited and c.sql.endswith("LIMIT 100")
    assert c.tables == ["app.eu_plants"]


def test_small_limit_kept():
    c = check("SELECT * FROM app.eu_plants LIMIT 5;", allowed_paths=ALLOWED, max_rows=100)
    assert not c.limited and c.sql == "SELECT * FROM app.eu_plants LIMIT 5"


def test_large_limit_wrapped():
    c = check("SELECT * FROM app.eu_plants LIMIT 1000000", allowed_paths=ALLOWED, max_rows=100)
    assert c.limited


def test_with_and_union_pass():
    check(
        "WITH a AS (SELECT 1 AS x) SELECT x FROM a UNION ALL SELECT 2",
        allowed_paths=ALLOWED,
        max_rows=10,
    )


def test_allowed_file_passes():
    check(
        "SELECT * FROM read_json('/data/public/eu/plants.json')", allowed_paths=ALLOWED, max_rows=10
    )


def test_licensed_aggregate_passes():
    c = check(
        "SELECT type, sum(mw) AS mw FROM gem_plants.units GROUP BY type",
        allowed_paths=ALLOWED,
        max_rows=10,
    )
    assert c.tables == ["gem_plants.units"]
    check("SELECT count(*) FROM gem_plants.units", allowed_paths=ALLOWED, max_rows=10)
