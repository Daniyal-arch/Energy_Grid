"""Change feeds (brief 30 Track 6.2): one snapshot a day, a change is a row that differs."""

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import settings
from tools.context import ToolContext
from tools.feeds import _diff, feed, key_of


def test_diff_rows():
    old = {
        "date": "2026-11-01",
        "tables": [
            {
                "title": "T",
                "columns": ["fuel", "plants", "mw"],
                "rows": [["solar", 2, 10.0], ["wind", 1, 5.0]],
                "as_of": "x",
                "sources": [],
            }
        ],
    }
    new = {
        "date": "2026-11-08",
        "tables": [
            {
                "title": "T",
                "columns": ["fuel", "plants", "mw"],
                "rows": [["solar", 3, 14.5], ["wind", 1, 5.0], ["gas", 1, 50.0]],
                "as_of": "y",
                "sources": [],
            }
        ],
    }
    ch = _diff(old, new)
    assert [c["key"] for c in ch] == ["gas", "solar"]
    assert ch[1]["change"] == "plants 2 to 3; mw 10.0 to 14.5"


def test_feed_keeps_one_snapshot_a_day_and_rss():
    ctx = ToolContext(settings())
    f1 = feed(ctx, "Luxembourg")
    f2 = feed(ctx, "Luxembourg")
    assert f1["snapshots"] == f2["snapshots"] and len(f2["snapshots"]) >= 1
    assert f2["key"] == key_of("Luxembourg")
    with TestClient(app) as c:
        r = c.get("/api/feed/Luxembourg.rss")
        assert r.status_code == 200 and r.text.startswith("<?xml") and "Luxembourg" in r.text
        assert c.get("/api/feed/Atlantis.json").status_code == 404
