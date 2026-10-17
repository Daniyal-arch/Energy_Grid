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
    assert t["path"] == "lake/test/rows/year=*/*.parquet"
    assert t["files"][0] == "rows/year=2024/part-0.parquet"


def test_partial_runs_merge_into_one_catalogue(tmp_path: Path) -> None:
    con = duckdb.connect()
    parts = []
    for year in (2023, 2024):
        root = tmp_path / str(year)
        lk = lake.Lake("test", root, source="unit test", licence="CC0", script="tests")
        lk.write(
            con,
            "rows",
            f"SELECT {year} AS y, i FROM range({year - 2020}) r(i)",
            sort=["i"],
            partition={"year": str(year)},
        )
        parts.append(lk.finish())
    final = lake.Lake("test", tmp_path / "all", source="unit test", licence="CC0", script="tests")
    final.write(con, "dim", "SELECT 1 AS id", sort=["id"])
    cat = json.loads(final.finish(partials=parts).read_text(encoding="utf-8"))
    rows = cat["tables"]["rows"]
    assert rows["files"] == ["rows/year=2023/part-0.parquet", "rows/year=2024/part-0.parquet"]
    assert rows["rows"] == 3 + 4
    assert rows["bytes"] == sum(v[1] for v in rows["file_stats"].values())
    assert cat["tables"]["dim"]["rows"] == 1
    # a re-run of one year replaces that year's entry
    again = lake.Lake("test", tmp_path / "all", source="unit test", licence="CC0", script="tests")
    again.write(con, "rows", "SELECT 2024 AS y, 1 AS i", sort=["i"], partition={"year": "2024"})
    cat = json.loads(again.finish().read_text(encoding="utf-8"))
    assert cat["tables"]["rows"]["rows"] == 3 + 1


def test_geoparquet_with_bbox_covering(tmp_path: Path) -> None:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    lk = lake.Lake("test", tmp_path, source="unit test", licence="CC0", script="tests")
    (path,) = lk.write(
        con,
        "shapes",
        "SELECT i AS id, ST_Buffer(ST_Point(i, i), 0.5) AS geometry FROM range(5) r(i)",
        sort=["id"],
        geometry="geometry",
    )
    kv = dict(
        con.execute(
            f"SELECT key::VARCHAR, decode(value) FROM parquet_kv_metadata('{path}')"
        ).fetchall()
    )
    geo = json.loads(kv["geo"])
    assert geo["version"] == "1.1.0"
    assert geo["columns"]["geometry"]["geometry_types"] == ["Polygon"]
    assert geo["columns"]["geometry"]["covering"]["bbox"]["xmin"] == ["bbox", "xmin"]
    xmin = con.execute(f"SELECT bbox.xmin FROM '{path}' WHERE id = 2").fetchone()[0]
    assert abs(xmin - 1.5) < 1e-9


def test_merge_catalogs_sums_parallel_jobs() -> None:
    a = {
        "updated": "2026-10-13T09:00:00+00:00",
        "tables": {"lines": {"rows": 2, "bytes": 10, "files": ["lines/a.parquet"]}},
    }
    b = {
        "updated": "2026-10-13T09:05:00+00:00",
        "tables": {"lines": {"rows": 3, "bytes": 5, "files": ["lines/b.parquet"]}},
    }
    m = lake.merge_catalogs([a, b])
    assert m["tables"]["lines"]["rows"] == 5 and m["tables"]["lines"]["bytes"] == 15
    assert m["tables"]["lines"]["files"] == ["lines/a.parquet", "lines/b.parquet"]
    assert m["updated"] == "2026-10-13T09:05:00+00:00"


def test_merge_does_not_widen_the_upload(tmp_path: Path) -> None:
    con = duckdb.connect()
    old = lake.Lake("test", tmp_path, source="s", licence="l", script="t")
    old.write(con, "rows", "SELECT 1 AS i", sort=["i"], partition={"year": "2025"})
    old.finish()
    new = lake.Lake("test", tmp_path, source="s", licence="l", script="t")
    new.write(con, "rows", "SELECT 2 AS i", sort=["i"], partition={"year": "2026"})
    cat = json.loads(new.finish().read_text(encoding="utf-8"))
    assert len(cat["tables"]["rows"]["files"]) == 2
    assert new.tables["rows"].files == ["rows/year=2026/part-0.parquet"]


def test_write_splits_files_over_the_byte_limit(tmp_path: Path, monkeypatch) -> None:
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE t AS SELECT i AS id, md5(i::VARCHAR) || md5((i * 7)::VARCHAR) AS s "
        "FROM range(200000) r(i)"
    )
    lk = lake.Lake("test", tmp_path, source="unit test", licence="CC0", script="tests")
    whole = lk.write(con, "one", "SELECT * FROM t", sort=["id"])
    assert len(whole) == 1
    monkeypatch.setattr(lake, "MAX_BYTES_PER_FILE", whole[0].stat().st_size // 3)
    files = lk.write(con, "split", "SELECT * FROM t", sort=["id"])
    assert len(files) >= 3
    assert all(f.stat().st_size <= lake.MAX_BYTES_PER_FILE for f in files)
    total = sum(con.execute(f"SELECT count(*) FROM '{f}'").fetchone()[0] for f in files)
    assert total == 200000
