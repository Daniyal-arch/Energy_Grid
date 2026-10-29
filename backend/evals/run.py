"""Run the evaluation questions through the agent graph and score them.

    uv run python -m evals.run --model claude-opus-5-5 --sample 10 [--needs app] [--out r.json]

Questions whose data is not reachable here (`needs: lake` without the R2 keys, `needs: api`
without the source's key) are skipped and counted. Results go to Langfuse as a dataset run when
its keys are set. The summary per model (scores, cost, latency) is printed as Markdown for the PR.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time
from pathlib import Path
from typing import Any

import yaml

from agent.deps import build_deps
from agent.graph import GRAPH, initial_state
from app.settings import get_settings
from evals.scorers import score
from obs import langfuse, tracing

ROOT = Path(__file__).resolve().parents[2]


def load(path: Path) -> list[dict[str, Any]]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["questions"]


def reachable(q: dict[str, Any], s: Any, lake_tables: set[str]) -> bool:
    needs = q.get("needs", "app")
    if needs == "lake":
        ds = str(q.get("dataset", "")).split(".")[0]
        return any(t.startswith(ds + ".") for t in lake_tables)
    # the live tool covers the snapshot files; other APIs need their own keys
    return needs != "api"


async def ask(q: dict[str, Any], model: str, cost_cap: float) -> dict[str, Any]:
    s = get_settings()
    d = build_deps(s, model=model)
    with tracing.span("eval.question", {"eval.id": q["id"]}):
        tid = tracing.current_trace_id()
        config = {
            "configurable": {"deps": d},
            "callbacks": langfuse.callbacks(s, tid),
            "metadata": langfuse.run_metadata(f"eval-{q['id']}", ["eval", d.main_entry.id]),
            "recursion_limit": 60,
        }
        try:
            out = await asyncio.wait_for(
                GRAPH.ainvoke(initial_state(q["q"], trace_id=tid), config), 180
            )
        except Exception as e:
            return {
                "run": {"trace_id": tid, "stop": f"error: {type(e).__name__}: {e}"},
                "answer": "",
            }
    out["answer"] = out.get("answer", "")
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    ap.add_argument("--sample", type=int, default=0, help="random sample size (0 = all)")
    ap.add_argument("--seed", type=int, default=25)
    ap.add_argument(
        "--needs", default=None, help="only questions with this 'needs' (app, lake, api, catalog)"
    )
    ap.add_argument(
        "--cost-cap", type=float, default=2.0, help="stop when the run has spent this many USD"
    )
    ap.add_argument("--questions", default=str(ROOT / "agent" / "evals" / "questions.yaml"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    s = get_settings()
    tracing.setup_tracing(s)
    model = a.model or s.agent_model
    if model not in s.models_allowed():
        s.agent_models_allowed = [*s.models_allowed(), model]
    d = build_deps(s, model=model)
    tables = set(d.ctx.lake.tables())
    qs = [q for q in load(Path(a.questions)) if not a.needs or q.get("needs") == a.needs]
    runnable = [q for q in qs if reachable(q, s, tables)]
    skipped = len(qs) - len(runnable)
    if a.sample:
        runnable = random.Random(a.seed).sample(runnable, min(a.sample, len(runnable)))
    results, spent = [], 0.0
    t0 = time.time()
    for q in runnable:
        if spent >= a.cost_cap:
            print(f"cost cap ${a.cost_cap} reached; stopping")
            break
        out = await ask(q, model, a.cost_cap)
        sc = score(q, out)
        sc["answer"] = out.get("answer", "")[:300]
        sc["trace_id"] = out.get("run", {}).get("trace_id")
        spent += sc.get("cost_usd") or 0
        results.append(sc)
        for k in ("correct", "grounded", "map"):
            if k in sc:
                langfuse.score(s, sc["trace_id"] or "", f"eval.{k}", float(sc[k]), comment=q["id"])
        print(
            json.dumps(
                {
                    k: sc.get(k)
                    for k in (
                        "id",
                        "correct",
                        "map",
                        "grounded",
                        "sources",
                        "latency_ms",
                        "cost_usd",
                        "stop",
                    )
                }
            )
        )
    tracing.flush()
    langfuse.flush(s)

    def mean(k: str) -> float | None:
        v = [r[k] for r in results if r.get(k) is not None]
        return round(statistics.mean(v), 3) if v else None

    summary = {
        "model": d.main_entry.id,
        "fast_model": d.fast_entry.id,
        "questions": len(results),
        "skipped_unreachable": skipped,
        "correct": mean("correct"),
        "map": mean("map"),
        "grounded": mean("grounded"),
        "sources": mean("sources"),
        "latency_ms_median": statistics.median(
            [r["latency_ms"] for r in results if r.get("latency_ms")]
        )
        if results
        else None,
        "cost_usd_total": round(spent, 4),
        "cost_usd_per_question": round(spent / len(results), 4) if results else None,
        "wall_s": round(time.time() - t0, 1),
    }
    print("\n| model | n | correct | map | grounded | sources | median latency | cost / question |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    cols = ("model", "questions", "correct", "map", "grounded", "sources")
    print(
        "| "
        + " | ".join(str(summary[c]) for c in cols)
        + f" | {summary['latency_ms_median']} ms | ${summary['cost_usd_per_question']} |"
    )
    print(f"\n({skipped} questions skipped: their data is not reachable from here)")
    if a.out:
        Path(a.out).write_text(
            json.dumps({"summary": summary, "results": results}, indent=2, default=str),
            encoding="utf-8",
        )


if __name__ == "__main__":
    asyncio.run(main())
