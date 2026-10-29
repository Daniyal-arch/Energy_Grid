"""The area questions of brief 27 (agent/evals/areas.yaml) through the whole graph with the
scripted fake model: resolve_area, run_sql with the area, grounded numbers, maps with the area."""

import asyncio
from pathlib import Path

import pytest
import yaml

from agent.deps import build_deps
from agent.graph import GRAPH, initial_state
from evals.scorers import score
from tests.conftest import settings

CASES = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "agent" / "evals" / "areas.yaml").read_text()
)["questions"]


def test_twenty_cases_at_every_level():
    assert len(CASES) == 20
    levels = {c["level"] for c in CASES}
    assert {"group", "circle", "polygon", "bbox", "us_county", "us_state", "world"} <= levels
    assert {"region", "county", "locality", "nl_buurt"} <= levels  # with the lake


@pytest.mark.parametrize("case", [c for c in CASES if c["needs"] == "app"], ids=lambda c: c["id"])
def test_area_case(case):
    d = build_deps(settings())
    d.ctx.view = case.get("view")
    out = asyncio.run(
        GRAPH.ainvoke(
            initial_state(case["q"], view=case.get("view"), trace_id="t" * 32),
            {"configurable": {"deps": d}, "recursion_limit": 80},
        )
    )
    names = [t["name"] for t in out["tool_log"]]
    assert names[:2] == ["resolve_area", "run_sql"], names
    sc = score(case, out)
    assert sc["grounded"] == 1.0
    if case.get("numbers"):
        assert sc["correct"] == 1.0, (case["numbers"], out["answer"])
    if case.get("map"):
        assert sc["map"] == 1.0
        assert out["maps"][0]["spec"]["area"]["area_id"].startswith("a_")
