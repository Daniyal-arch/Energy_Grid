"""The lake writer: sorted row groups, partitions, metadata, catalogue (scripts/lake.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import lake  # noqa: E402


def test_write_sorts_partitions_and_catalogues(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(lake, "MAX_ROWS_PER_FILE", 40_000)
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE t AS SELECT lpad((i % 300)::VARCHAR, 5, '0') AS fips, i AS n "
        "FROM range(100000) r(i)"
    )
    lk = lake.Lake("test", tmp_path, source="unit test", licence="CC0", script="tests")
    files = lk.write(
        con,
        "rows",
        "SELECT * FROM t",
        sort=["fips", "n"],
        bloom=["fips"],
        partition={"year": "2024"},
    )
    assert [f.name for f in files] == ["part-0.parquet", "part-1.parquet", "part-2.parquet"]
    assert files[0].parent.name == "year=2024"
    # each file sorted and the files in order: the first file ends where the second begins
    first = con.execute(f"SELECT min(fips), max(fips) FROM '{files[0]}'").fetchone()
    second = con.execute(f"SELECT min(fips) FROM '{files[1]}'").fetchone()
    assert first[1] <= second[0]
    kv = dict(
        con.execute(
            f"SELECT key::VARCHAR, value::VARCHAR FROM parquet_kv_metadata('{files[0]}')"
        ).fetchall()
    )
    assert kv["source"] == "unit test" and kv["table"] == "rows"
    meta = con.execute(
        f"SELECT DISTINCT compression FROM parquet_metadata('{files[0]}')"
    ).fetchall()
    assert meta == [("ZSTD",)]
    cat = json.loads(lk.finish().read_text(encoding="utf-8"))
    t = cat["tables"]["rows"]
    assert t["rows"] == 100000 and t["partitions"] == ["year"]
    assert t["path"] == "lake/test/rows/year=*/part-*.parquet"
    assert t["files"][0] == "rows/year=2024/part-0.parquet"
