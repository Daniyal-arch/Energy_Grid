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
    # outlines (brief 27): two regions named Limburg, Oberbayern, a city and a neighbourhood
    (root / "shapes").mkdir(parents=True, exist_ok=True)
    (root / "outlines").mkdir(parents=True, exist_ok=True)
    try:
        con.load_extension("spatial")
    except duckdb.Error:
        con.install_extension("spatial")
        con.load_extension("spatial")
    con.execute(
        f"""COPY (SELECT * FROM (VALUES
          ('NL42', 2, 'Limburg', 'NL', 'NLD', ST_MakeEnvelope(5.6, 50.75, 6.2, 51.75)),
          ('BE22', 2, 'Limburg', 'BE', 'BEL', ST_MakeEnvelope(4.9, 50.7, 5.9, 51.3)),
          ('DE21', 2, 'Oberbayern', 'DE', 'DEU', ST_MakeEnvelope(10.7, 47.4, 13.1, 49.1))
        ) t(nuts_id, level, name, iso2, iso3, geometry))
        TO '{root}/shapes/nuts.parquet' (FORMAT parquet)"""
    )
    con.execute(
        f"""COPY (SELECT * FROM (VALUES
          ('fr-75056', 'Paris', 'locality', 'FRA', 'Ile-de-France', 2133111.0, ST_MakeEnvelope(2.22, 48.81, 2.47, 48.91)),
          ('us-4855893', 'Paris', 'us_place', 'USA', 'Texas', 24171.0, ST_MakeEnvelope(-95.62, 33.62, -95.48, 33.71)),
          ('nl-BU03630000', 'Burgwallen-Oude Zijde', 'nl_buurt', 'NLD', 'Amsterdam', 4200.0, ST_MakeEnvelope(4.893, 52.369, 4.902, 52.377))
        ) t(id, name, level, iso3, parent_name, population, geometry))
        TO '{root}/outlines/divisions.parquet' (FORMAT parquet)"""
    )
    (root / "_catalog.json").write_text('{"updated": "2026-10-27T00:00:00Z"}')


def write_fixture_rasters(root: Path) -> None:
    """A population grid of 0.01 degrees, one person per cell, over 10-14 E, 46-50 N."""
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    root.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        root / "ghsl_pop_e2025_3ss.tif", "w", driver="GTiff", width=400, height=400, count=1,
        dtype="float32", crs="EPSG:4326", transform=from_origin(10, 50, 0.01, 0.01), nodata=-200,
    ) as dst:  # fmt: skip
        dst.write(np.ones((1, 400, 400), dtype="float32"))


write_fixture_lake(LAKE)
write_fixture_rasters(TMP / "rasters")
os.environ.update(
    {
        "AGENT_MODEL": "fake",
        "AGENT_MODEL_FAST": "fake",
        "LAKE_DB": "",
        "LAKE_DIR": str(LAKE),
        "RASTERS_DIR": str(TMP / "rasters"),
        "LOCAL_STORE_DIR": str(TMP / "store"),
        "RESULTS_DIR": str(TMP / "results"),
        "ADMIN_API_KEY": "test-admin",
        "MCP_API_KEYS": "test-mcp",
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
