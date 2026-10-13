"""Aqueduct builder (scripts/build_aqueduct.py) on three tiny layers shaped like the GDB's."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_aqueduct as ba  # noqa: E402


def _layers(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("INSTALL spatial; LOAD spatial")
    ind = ", ".join(
        f"{c}::DOUBLE AS {i}_raw, {c}::DOUBLE AS {i}_score, {c}::DOUBLE AS {i}_cat, "
        f"'cat ' || {c} AS {i}_label"
        for i, c in [("bws", "b"), ("rfr", "r"), ("cfr", "cf"), ("drr", "d")]
    )
    # basin 111 has two units in two countries (DE larger) with different coastal flood cats
    con.execute(
        f"""CREATE TABLE annual AS SELECT aq30_id, aq30_id AS aq30_id_1, pfaf_id, gid_0,
                   'p' || aq30_id AS name_1, area AS area_km2, 1.0 AS Shape_Leng, {ind},
                   ST_GeomFromText(wkt) AS geom
            FROM (VALUES (1, 111, 'DEU', 10.0, 4, 1, 0, 2, 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))'),
                         (2, 111, 'FRA', 5.0, 4, 1, 3, 2, 'POLYGON((1 0, 2 0, 2 1, 1 1, 1 0))'),
                         (3, 222, 'XKO', 7.0, -1, -9999, -9999, 0,
                          'POLYGON((5 5, 6 5, 6 6, 5 6, 5 5))'))
                 t(aq30_id, pfaf_id, gid_0, area, b, r, cf, d, wkt)"""
    )
    months = ", ".join(
        f"{m}.0 AS bws_{m:02d}_raw, 1.0 AS bws_{m:02d}_score, 1.0 AS bws_{m:02d}_cat, "
        f"'Low' AS bws_{m:02d}_label"
        for m in range(1, 13)
    )
    con.execute(
        f"""CREATE TABLE monthly AS SELECT pfaf_id, pfaf_id AS pfaf_id_1, {months},
                   ST_GeomFromText(wkt) AS geom
            FROM (VALUES (111, 'POLYGON((0 0, 2 0, 2 1, 0 1, 0 0))'),
                         (222, 'POLYGON((5 5, 6 5, 6 6, 5 6, 5 5))')) t(pfaf_id, wkt)"""
    )
    con.execute(
        """CREATE TABLE future AS SELECT 1 AS fid, pfaf_id, 2.5 AS bau30_ws_x_r,
                   0.5 AS bau30_ws_x_s, 1.0 AS bau30_ws_x_c, 'Low-medium' AS bau30_ws_x_l, 9.0 AS bau30_ba_x_r,
                   '< 1 cm' AS bau30_ba_x_l, ST_GeomFromText('POINT(0 0)') AS geom
            FROM (VALUES (111), (222)) t(pfaf_id)"""
    )


def test_map_file_and_lake(tmp_path: Path) -> None:
    con = duckdb.connect()
    _layers(con)
    out = ba.map_file(con)
    by_id = {b["id"]: b for b in out["basins"]}
    # highest category where units differ (cfr in 111), none where WRI has no data (-9999)
    assert by_id[111]["c"] == [4, 1, 3, 2]
    assert by_id[222]["c"] == [-1, None, None, 0]
    assert out["mixed"] == {"bws": 0, "rfr": 0, "cfr": 1, "drr": 0}
    assert out["indicators"]["bws"]["labels"]["4"] == "cat 4"
    ba.basin_country(con)
    cat = json.loads(ba.write_lake(con, tmp_path, upload=False).read_text(encoding="utf-8"))
    t = cat["tables"]
    assert t["baseline_annual"]["rows"] == 3 and "aq30_id_1" not in t["baseline_annual"]["columns"]
    assert t["baseline_annual"]["columns"]["bws_cat"] == "SMALLINT"
    assert t["baseline_monthly"]["rows"] == 24 and t["future_annual"]["rows"] == 2 * 9
    d = tmp_path / "aqueduct"
    basins = con.execute(
        f"SELECT pfaf_id, iso2, iso3, admin1 FROM '{d / t['basins']['files'][0]}' ORDER BY 1"
    ).fetchall()
    assert basins == [(111, "DE", "DEU", "p1"), (222, "XK", "XKO", "p3")]
    fut = con.execute(
        f"SELECT ws_raw, ba_raw, ba_score FROM '{d / t['future_annual']['files'][0]}' "
        "WHERE pfaf_id = 111 AND scenario = 'bau' AND year = 2030"
    ).fetchone()
    assert fut == (2.5, 9.0, None)
