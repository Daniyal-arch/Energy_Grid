"""The row-group rewrite keeps every row and value (scripts/lake_rewrite.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import lake_rewrite  # noqa: E402


def test_rewrite_keeps_rows_values_and_metadata(tmp_path: Path) -> None:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    src = tmp_path / "src.parquet"
    # points, an empty geometry and a NULL one; KV metadata with an empty value and a quote
    con.execute(
        "COPY (SELECT i AS id, i * 0.5 AS mw, "
        "CASE WHEN i = 7 THEN ST_GeomFromText('POLYGON EMPTY') WHEN i = 8 THEN NULL "
        "ELSE ST_Point(i % 97, i % 89) END AS geometry FROM range(5000) t(i)) "
        f"TO '{src}' (FORMAT parquet, KV_METADATA {{source: '', licence: 'it''s open'}})"
    )
    work = tmp_path / "work"
    work.mkdir()
    r = lake_rewrite.rewrite_file(con, str(src), [], work)
    assert r["rows"] == 5000 and r["checksums"] == "equal" and r["bbox_added"]
    out = r["file"]
    kv = dict(con.execute(f"SELECT key, value FROM parquet_kv_metadata('{out}')").fetchall())
    assert kv[b"licence"] == b"it's open" and kv[b"source"] == b""
    assert con.execute(f"SELECT count(*) FROM '{out}' WHERE geometry IS NULL").fetchone()[0] == 1
