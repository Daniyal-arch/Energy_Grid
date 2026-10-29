"""Build agent/evals/questions.yaml: the catalogue's example questions with their known answers,
questions on the app tables with answers computed here from the map files, and map questions
with the expected overlay kind and key.

    uv run python scripts/build_eval_questions.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("LAKE_DB", "")

from agent.grounding import numbers_in_text  # noqa: E402
from app.settings import Settings  # noqa: E402
from data.duck import Lake  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "agent" / "evals" / "questions.yaml"

# questions on the app tables: (id, question, sql); the answer is the query's result now
APP = [
    (
        "app-neg-hours-top",
        "Which European bidding zone had the most hours with a negative day-ahead price in the newest 12 months, and how many?",
        "SELECT zone, negative_hours FROM app.eu_prices ORDER BY negative_hours DESC LIMIT 1",
    ),
    (
        "app-nl-mean",
        "What was the average day-ahead price in the Netherlands over the newest 12 months?",
        "SELECT mean_eur_mwh FROM app.eu_prices WHERE zone = 'NL'",
    ),
    (
        "app-dk1-neg",
        "How many hours below zero did DK1 have in the newest 12 months?",
        "SELECT negative_hours FROM app.eu_prices WHERE zone = 'DK1'",
    ),
    (
        "app-de-coal",
        "How much coal capacity (plants of 20 MW and more) operates in Germany?",
        "SELECT round(sum(mw)) FROM app.eu_plants WHERE country = 'DE' AND fuel = 'coal'",
    ),
    (
        "app-fr-nuclear",
        "How much nuclear capacity operates in France (plants of 20 MW and more)?",
        "SELECT round(sum(mw)) FROM app.eu_plants WHERE country = 'FR' AND fuel = 'nuclear'",
    ),
    (
        "app-es-solar-count",
        "How many solar plants of 20 MW and more operate in Spain?",
        "SELECT count(*) FROM app.eu_plants WHERE country = 'ES' AND fuel = 'solar'",
    ),
    (
        "app-largest-eu",
        "Which is the largest power plant in Europe in the map's plant list and how big is it?",
        "SELECT name, mw FROM app.eu_plants ORDER BY mw DESC LIMIT 1",
    ),
    (
        "app-subs-380-de",
        "How many substations of 380 kV are in Germany's transmission grid on the map?",
        "SELECT count(*) FROM app.eu_substations WHERE country = 'DE' AND kv = 380",
    ),
    (
        "app-us-tx-operating",
        "How much generating capacity operates in Texas by EIA-860M?",
        "SELECT round(sum(mw)) FROM app.us_plants WHERE state = 'TX' AND status = 'operating'",
    ),
    (
        "app-world-coal-construction",
        "How much coal capacity is under construction worldwide in Global Energy Monitor's tracker?",
        "SELECT round(sum(mw)) FROM app.world_plants WHERE type = 'coal' AND status = 'construction'",
    ),
]

MAPS = [
    (
        "map-de-plants",
        "Show Germany's power plants of 20 MW and more on a map, sized by capacity.",
        "points",
        "lon/lat",
    ),
    (
        "map-neg-hours-zones",
        "Map the hours with negative day-ahead prices per bidding zone.",
        "choropleth",
        "zone",
    ),
    (
        "map-price-zones",
        "Shade Europe's bidding zones by their average day-ahead price.",
        "choropleth",
        "zone",
    ),
    (
        "map-coal-country",
        "Map operating coal capacity per European country.",
        "choropleth",
        "country",
    ),
    (
        "map-es-solar",
        "Where are Spain's large solar plants? Show them on the map.",
        "points",
        "lon/lat",
    ),
    ("map-tx-plants", "Show the operating power plants in Texas on a map.", "points", "lon/lat"),
    ("map-uk-wind", "Map the UK's operating wind projects from the REPD.", "points", "lon/lat"),
    ("map-subs-nl", "Show the 380 kV substations in the Netherlands.", "points", "lon/lat"),
    ("map-nuclear-country", "Map nuclear capacity per European country.", "choropleth", "country"),
    (
        "map-world-coal-building",
        "Show the coal plants under construction worldwide.",
        "points",
        "lon/lat",
    ),
]


def fmt(v: object) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return f"{v:,}" if isinstance(v, int | float) and not isinstance(v, bool) else str(v)


def expected_numbers(answer: str) -> list[str]:
    return [raw for raw, _, _ in numbers_in_text(answer)]


def main() -> None:
    questions = []
    for p in sorted((ROOT / "agent" / "catalog").glob("*.yaml")):
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        exs = [(None, e) for e in d.get("examples") or []]
        for t, tv in (d.get("tables") or {}).items():
            if isinstance(tv, dict):
                exs += [(t, e) for e in tv.get("examples") or []]
        for i, (table, e) in enumerate(exs):
            answer = str(e.get("answer", ""))
            nums = expected_numbers(answer)
            if not nums:
                continue
            needs = (
                "lake"
                if e.get("sql")
                else ("api" if e.get("call") or d.get("access") == "api" else "catalog")
            )
            questions.append(
                {
                    "id": f"{p.stem}-{i + 1}",
                    "q": str(e["q"]),
                    "answer": answer,
                    "numbers": nums,
                    "dataset": d["dataset"] + (f".{table}" if table else ""),
                    "needs": needs,
                    "source": f"agent/catalog/{p.name}",
                }
            )
    lake = Lake(Settings(lake_db=None))
    for qid, q, sql in APP:
        row = lake.run(sql, guard=False).rows[0]
        answer = ", ".join(fmt(v) for v in row)
        questions.append(
            {
                "id": qid,
                "q": q,
                "answer": answer,
                "numbers": expected_numbers(answer) or [answer],
                "dataset": "app",
                "needs": "app",
                "sql": sql,
                "source": "computed from the app's map files by this script",
            }
        )
    for qid, q, kind, key in MAPS:
        questions.append(
            {
                "id": qid,
                "q": q,
                "map": {"kind": kind, "key": key},
                "needs": "lake" if "REPD" in q else "app",
            }
        )
    doc = {
        "about": "Evaluation questions (backend/evals/run.py). Built by backend/scripts/build_eval_questions.py from the "
        "catalogue's examples (answers as published there), questions on the app tables (answers computed from the "
        "map files when built) and map questions with the expected overlay kind and key. 'needs' says what must be "
        "reachable: app (the map files), lake (R2), api (a live API), catalog (the catalogue text).",
        "questions": questions,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8"
    )
    n_num = sum(1 for q in questions if "numbers" in q)
    print(
        f"wrote {OUT.relative_to(ROOT)}: {n_num} questions with known answers, {len(MAPS)} map questions"
    )


if __name__ == "__main__":
    main()
