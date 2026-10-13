"""ENTSO-E lake table builders (scripts/build_lake_entsoe.py) on small XML documents."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_lake_entsoe as ble  # noqa: E402
import entsoe  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def _doc(name: str) -> ET.Element:
    return ET.fromstring((FIX / name).read_bytes())


def test_prices_at_published_resolution_with_a03_written_out() -> None:
    rows = ble.price_rows("DE-LU", "EIC", entsoe.points_of(_doc("entsoe_a44.xml"), "price.amount"))
    a03 = [r for r in rows if r[6] is None]
    # 8 quarter-hours: positions 1-2 hold 10.50, 3-5 hold -1.25, 6-8 hold 99.99
    assert [r[4] for r in a03] == [10.5, 10.5, -1.25, -1.25, -1.25, 99.99, 99.99, 99.99]
    assert a03[0][0] == "2024-12-31T23:00:00+00:00" and a03[0][3] == 15
    hourly = [r for r in rows if r[6] == "2"]
    assert hourly == [("2025-01-01T00:00:00+00:00", "DE-LU", "EIC", 60, 12.0, "EUR", "2")]


def test_generation_keeps_consumption_apart() -> None:
    rows = ble.generation_rows("AT", entsoe.points_of(_doc("entsoe_a75.xml"), "quantity"))
    assert rows == [
        ("2025-01-01T00:00:00+00:00", "AT", "B10", 15, 800.0, 300.0),
        ("2025-01-01T00:15:00+00:00", "AT", "B10", 15, 810.0, None),
    ]


def test_outage_rows() -> None:
    (row,) = ble.outage_rows("FR", [_doc("entsoe_a80.xml")])
    assert row[:9] == ("OUT-1", 3, "A05", "FR", "UNIT-EIC", "Unit 1", "PLANT-EIC", "Plant", "B14")
    assert row[10:14] == (
        "B18",
        "planned maintenance",
        "2025-03-01T06:00:00+00:00",
        "2025-03-02T06:00:00+00:00",
    )
    assert row[14:] == ("2025-03-01T06:00:00+00:00", 1, 0.0, 1300.0)


def test_write_tables_types_and_year(tmp_path: Path) -> None:
    sink = ble.Sink(tmp_path / "tmp")
    sink.add(
        "prices",
        ble.price_rows("DE-LU", "EIC", entsoe.points_of(_doc("entsoe_a44.xml"), "price.amount")),
    )
    sink.close()
    con = duckdb.connect()
    lk = ble.lake_of(tmp_path / "lake")
    ble.write_tables(con, lk, sink, 2025)
    t = lk.catalog()["tables"]["prices"]
    assert t["columns"]["price"] == "DECIMAL(9,2)" and t["columns"]["iso3"] == "VARCHAR"
    f = tmp_path / "lake" / "entsoe" / t["files"][0]
    # the 23:00 quarter-hour of 2024 is left to the 2024 file
    got = con.execute(f"SELECT count(*), min(price), any_value(iso3) FROM '{f}'").fetchone()
    assert got[0] == 8 - 4 + 1 and float(got[1]) == -1.25 and got[2] == "DEU"
