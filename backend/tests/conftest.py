"""Test setup: the scripted fake model, a fixture lake of small Parquet files written here, and
local stores in a temporary directory. No network, no keys."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import duckdb

TMP = Path(tempfile.mkdtemp(prefix="atlas-tests-"))
LAKE = TMP / "lake"


def write_fixture_lake(root: Path) -> None:
    con = duckdb.connect()
    (root / "registers").mkdir(parents=True, exist_ok=True)
    (root / "gem_plants").mkdir(parents=True, exist_ok=True)
    (root / "eaglei" / "outages" / "year=2024").mkdir(parents=True, exist_ok=True)
    con.execute(
        f"""COPY (SELECT * FROM (VALUES ('wind', 10.5, 'operating'), ('wind_offshore', 400.0, 'operating'),
        ('solar', 49.9, 'operating'), ('wind', 7.0, 'planned')) t("group", mw, status))
        TO '{root}/registers/gb.parquet' (FORMAT parquet)"""
    )
    con.execute(
        f"""COPY (SELECT * FROM (VALUES ('Unit A', 'coal', 'CN', 600.0), ('Unit B', 'coal', 'CN', 300.0),
        ('Unit C', 'solar', 'IN', 50.0)) t(name, type, iso3, mw)) TO '{root}/gem_plants/units.parquet' (FORMAT parquet)"""
    )
    con.execute(
        f"""COPY (SELECT '48201' AS fips, TIMESTAMP '2024-07-08 12:00:00' + INTERVAL (i * 15) MINUTE AS ts,
        1000 + i AS customers_out FROM range(8) r(i)) TO '{root}/eaglei/outages/year=2024/part-0.parquet' (FORMAT parquet)"""
    )
    (root / "_catalog.json").write_text('{"updated": "2026-10-27T00:00:00Z"}')


write_fixture_lake(LAKE)
os.environ.update(
    {
        "AGENT_MODEL": "fake",
        "AGENT_MODEL_FAST": "fake",
        "LAKE_DB": "",
        "LAKE_DIR": str(LAKE),
        "LOCAL_STORE_DIR": str(TMP / "store"),
        "RESULTS_DIR": str(TMP / "results"),
        "ADMIN_API_KEY": "test-admin",
        "MCP_API_KEYS": '["test-mcp"]',
        "IP_REQUESTS_PER_HOUR": "1000",
        "ENVIRONMENT": "test",
    }
)
for k in (
    "ANTHROPIC_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "R2_ACCESS_KEY_ID",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "DYNAMODB_TABLE",
    "REQUIRE_PROXY",
):
    os.environ.pop(k, None)

from app.settings import Settings, get_settings  # noqa: E402
from obs.tracing import setup_tracing  # noqa: E402

setup_tracing(get_settings(), in_memory=True)


def settings(**kw: object) -> Settings:
    return Settings(**kw)  # type: ignore[arg-type]
