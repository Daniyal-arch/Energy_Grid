"""The site report (brief 30 Track 6.1): the task skill's checklist in order, figures with
sources, coverage cells, no score."""

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import settings
from tools.context import ToolContext
from tools.report import TASKS, build_report, checklist


def test_every_task_has_its_checklist():
    for skill in TASKS.values():
        assert len(checklist(settings().agent_dir, skill)) >= 3


def test_report_near_berlin():
    rep = build_report(ToolContext(settings()), 13.4, 52.5, 25, "data_centre")
    titles = [s["title"] for s in rep["steps"]]
    assert titles[0].lower().startswith("power")
    power = rep["steps"][0]
    assert power["figures"] and all(t["method"] for t in power["figures"])
    assert any(c["country"] == "DE" for s in rep["steps"] for c in s["coverage"])
    assert "score" not in str(rep["steps"]).lower()


def test_report_routes():
    with TestClient(app) as c:
        r = c.get("/api/report", params={"lon": 13.4, "lat": 52.5, "task": "battery"})
        assert r.status_code == 200 and "Site report" in r.text and "Print or save as PDF" in r.text
        assert c.get("/api/report.json", params={"lon": 13.4, "lat": 52.5}).json()["steps"]
        assert (
            c.get("/api/report", params={"lon": 13.4, "lat": 52.5, "task": "nope"}).status_code
            == 422
        )
