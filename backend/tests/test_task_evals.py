"""The customer-task questions of brief 28 (agent/evals/tasks.yaml): each task skill runs one
case through the whole graph with the scripted fake model (load_skill, resolve_area, run_sql,
grounded numbers)."""

import asyncio
from pathlib import Path

import pytest
import yaml

from agent.deps import build_deps
from agent.graph import GRAPH, initial_state
from evals.scorers import score
from tests.conftest import settings

CASES = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "agent" / "evals" / "tasks.yaml").read_text()
)["questions"]
SKILLS = Path(__file__).resolve().parents[2] / "agent" / "skills"


def test_thirty_cases_and_every_task_skill_has_one():
    assert len(CASES) >= 30
    app_skills = {c["skill"] for c in CASES if c["needs"] == "app"}
    tasks = {
        "datacentre-siting", "battery-siting", "solar-wind-siting", "offshore-wind", "physical-risk",
        "grid-planning", "revenues", "industrial-decarbonisation", "heat-networks",
        "ev-electrification", "public-money",
    }  # fmt: skip
    assert tasks <= app_skills
    assert all((SKILLS / s / "SKILL.md").exists() for s in tasks)
    assert all(c.get("numbers") for c in CASES)


@pytest.mark.parametrize("case", [c for c in CASES if c["needs"] == "app"], ids=lambda c: c["id"])
def test_task_case(case):
    d = build_deps(settings())
    out = asyncio.run(
        GRAPH.ainvoke(
            initial_state(case["q"], trace_id="t" * 32),
            {"configurable": {"deps": d}, "recursion_limit": 80},
        )
    )
    names = [t["name"] for t in out["tool_log"]]
    assert "load_skill" in names and names.index("resolve_area") < names.index("run_sql"), names
    sc = score(case, out)
    assert sc["grounded"] == 1.0
    assert sc["correct"] == 1.0, (case["numbers"], out["answer"])
