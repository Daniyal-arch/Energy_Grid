"""Brief 32 Tier 0: quick serves a prepared answer when one exists for the area and its
fingerprint matches the data this service holds; otherwise the template runs as before."""

from __future__ import annotations

import json

import duckdb

from data.duck import Lake
from tests.conftest import TMP, settings
from tools import prepared
from tools.context import ToolContext
from tools.quick import quick


def _ctx_with_answer(fp_ok: bool) -> ToolContext:
    base = ToolContext(settings())
    a = quick(base, "profile", "Paris")["data"]["area"]
    path = TMP / "hot" / f"prepared_{fp_ok}.duckdb"
    path.parent.mkdir(exist_ok=True)
    path.unlink(missing_ok=True)
    con = duckdb.connect(str(path))
    con.execute("CREATE SCHEMA prepared")
    con.execute(
        "CREATE TABLE prepared.answers (area_id VARCHAR, key VARCHAR, payload VARCHAR, built VARCHAR, fingerprint VARCHAR)"
    )
    payload = {
        "data": {"template": "profile", "area": a, "tables": [{"title": "prepared marker"}]},
        "sources": [],
    }
    fp = prepared.fingerprint(base) if fp_ok else "other-data"
    con.execute(
        "INSERT INTO prepared.answers VALUES (?, 'profile:10:plants', ?, '2026-11-08T00:00:00+00:00', ?)",
        [a["area_id"], json.dumps(payload), fp],
    )
    con.close()
    ctx = ToolContext(settings())
    lake = Lake(settings(hot_db=str(path)))
    assert lake.wait_hot(30)
    ctx.__dict__["lake"] = lake
    return ctx


def test_prepared_answer_is_served():
    d = quick(_ctx_with_answer(True), "profile", "Paris")["data"]
    assert d["tables"] == [{"title": "prepared marker"}] and d["prepared"]["built"].startswith(
        "2026-11-08"
    )


def test_other_data_runs_the_template():
    d = quick(_ctx_with_answer(False), "profile", "Paris")["data"]
    assert "prepared" not in d and d["tables"][0].get("title") != "prepared marker"
