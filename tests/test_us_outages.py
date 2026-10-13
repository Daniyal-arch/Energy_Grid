"""EAGLE-I year builder and combine (scripts/build_us_outages.py) on a small synthetic year."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_us_outages as bo  # noqa: E402

HEAD = "fips_code,county,state,sum,run_start_time\n"


def _year_csv(tmp_path: Path) -> Path:
    rows = []
    # Harris, Texas: 12,000 out for 2 h (an event), then 5 out for 15 min
    for k in range(8):
        rows.append(f"48201,Harris,Texas,12000,2023-07-08 {k // 4 + 10:02d}:{k % 4 * 15:02d}:00")
    rows.append("48201,Harris,Texas,5,2023-07-09 00:00:00")
    # Autauga, Alabama (no leading zero, as some years publish it): 4 out at two times
    rows += ["1001,Autauga,Alabama,4,2023-07-08 10:00:00", "1001,Autauga,Alabama,4,2023-12-31 23:45:00"]
    # Puerto Rico
    rows.append("72001,Adjuntas,Puerto Rico,100,2023-12-31 23:30:00")
    path = tmp_path / "eaglei_outages_2023.csv"
    path.write_text(HEAD + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_year_part_and_lake(tmp_path: Path) -> None:
    con = duckdb.connect()
    bo.load_year(con, _year_csv(tmp_path))
    part = bo.year_part(con, 2023)
    assert part["step_min"] == 15
    # customer-hours = customers out x 0.25 h per row
    assert part["counties"]["48201"] == round(12000 * 8 * 0.25 + 5 * 0.25)
    assert part["counties"]["01001"] == 2
    assert part["events"] == [["Texas", "2023-07-08 10:00", "2023-07-08 12:00", 12000, "2023-07-08 10:00"]]
    assert part["month"]["month"] == "2023-12"
    assert part["month"]["values"][-1] == 4 and part["month"]["values"][-2] == 100
    cat = json.loads(bo.year_lake(con, 2023, tmp_path / "lake").read_text(encoding="utf-8"))
    t = cat["tables"]["outages"]
    assert t["rows"] == 12 and t["columns"]["customers_out"] == "INTEGER"
    f = tmp_path / "lake" / "eaglei" / t["files"][0]
    assert con.execute(f"SELECT DISTINCT iso3 FROM '{f}' WHERE fips = '72001'").fetchall() == [("PRI",)]
    assert con.execute(f"SELECT fips FROM '{f}' LIMIT 1").fetchone() == ("01001",)


def test_combine(tmp_path: Path) -> None:
    con = duckdb.connect()
    bo.load_year(con, _year_csv(tmp_path))
    part = bo.year_part(con, 2023)
    out = bo.combine([part], {"48201": 1_900_000})
    assert out["years"] == [2023] and out["national"] == [sum(part["counties"].values())]
    assert out["events"][0][0] == "Texas" and out["month"]["month"] == "2023-12"
    assert out["names"]["48201"] == "Harris, Texas"
