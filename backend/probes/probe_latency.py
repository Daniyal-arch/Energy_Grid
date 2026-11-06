"""Probe: backend latency with the fake model (brief 30, Track 4), and a smoke run of every
data route and every tool (Track 1.1).

Starts the app with uvicorn on a free port (or uses `--url`), then measures:

- every data route (health, catalog, places, site, areas, shapes, maps): status and time;
- every tool called directly once (ToolSpec.run), with time and, for the lake, bytes read;
- the eval questions (agent/evals/areas.yaml and tasks.yaml, the fake model plays them) through
  POST /api/ask: time to the first event, total time, each tool event's `ms`, SSE overhead
  (total wall time minus the run's own `latency_ms`).

Writes a Markdown table to stdout and the raw records to `--json` (default
/tmp/atlas-latency.json). Run it in the Lambda-sized container (2 vCPU, 3,008 MB) in Actions:
`.github/workflows/backend-probe.yml`. Locally, without the R2 token, the lake routes fall back
to the app tables and the lake tools report "no lake".

    uv run python -m probes.probe_latency [--url http://127.0.0.1:8080] [--questions 30]
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[2]
EVALS = ROOT / "agent" / "evals"

ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/api/health", None),
    ("GET", "/api/catalog/search?q=solar%20capacity%20Germany", None),
    ("GET", "/api/catalog/atb", None),
    ("GET", "/api/places?q=Bavaria", None),
    ("GET", "/api/places?q=Lyon", None),
    ("GET", "/api/site?lon=11.58&lat=48.14&radius_km=50", None),
    ("GET", "/api/areas/resolve?q=Bavaria", None),
    ("GET", "/api/areas/resolve?q=Berlin&level=city", None),
    ("GET", "/api/areas/resolve?q=Greater%20Manchester", None),
    ("GET", "/api/shapes/admin1/DEU", None),
    ("POST", "/api/maps", {"spec": {"title": "probe", "app": {"layers": ["cables"]}}}),
]

# each tool once, with arguments that need only the app tables or the lake
TOOL_CALLS: list[tuple[str, dict[str, Any]]] = [
    ("search_catalog", {"query": "solar capacity Germany states"}),
    ("describe_table", {"name": "plants"}),
    ("run_sql", {"sql": "SELECT country, count(*) AS n FROM plants GROUP BY 1 ORDER BY 2 DESC"}),
    ("find_place", {"text": "Lyon"}),
    ("resolve_area", {"names": ["Bavaria"]}),
    ("resolve_area", {"names": ["Berlin"], "level": "city"}),
    ("site_figures", {"lon": 11.58, "lat": 48.14}),
    ("live", {"source": "eu_snapshot"}),
    ("list_skills", {}),
    ("load_skill", {"name": "area-analysis"}),
]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def start_server() -> tuple[subprocess.Popen[bytes], str, float]:
    port = free_port()
    env = {
        **os.environ,
        "AGENT_MODEL": "fake",
        "AGENT_MODEL_FAST": "fake",
        "IP_REQUESTS_PER_HOUR": "100000",
        "RUN_RECORDS": "false",
    }
    t0 = time.perf_counter()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=ROOT / "backend",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(600):
        try:
            if httpx.get(url + "/api/health", timeout=2).status_code == 200:
                return proc, url, time.perf_counter() - t0
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    proc.kill()
    raise SystemExit("the app did not start in 120 s")


def questions(n: int) -> list[str]:
    qs: list[str] = []
    for name in ("areas.yaml", "tasks.yaml"):
        f = EVALS / name
        if f.exists():
            qs += [q["q"] for q in yaml.safe_load(f.read_text(encoding="utf-8"))["questions"]]
    return qs[:n]


def ask(client: httpx.Client, url: str, q: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    first: float | None = None
    tools: list[dict[str, Any]] = []
    done: dict[str, Any] = {}
    name = ""
    error = ""
    with client.stream("POST", url + "/api/ask", json={"question": q}, timeout=180) as r:
        if r.status_code != 200:
            return {"q": q, "status": r.status_code, "error": r.read().decode()[:200]}
        for line in r.iter_lines():
            if line.startswith("event:"):
                name = line[6:].strip()
                if first is None:
                    first = time.perf_counter() - t0
            elif line.startswith("data:"):
                data = json.loads(line[5:])
                if name == "tool" and data.get("status") in ("done", "error"):
                    tools.append(
                        {"name": data.get("name"), "ms": data.get("ms"), "status": data["status"]}
                    )
                elif name == "done":
                    done = data
                elif name == "error":
                    error = data.get("message", "")
    total = time.perf_counter() - t0
    run_ms = float(done.get("latency_ms") or 0)
    return {
        "q": q,
        "status": 200,
        "first_event_s": first,
        "total_s": total,
        "run_s": run_ms / 1000,
        "sse_overhead_s": max(0.0, total - run_ms / 1000) if done else None,
        "tools": tools,
        "error": error,
        "grounding": (done.get("grounding") or {}).get("ok")
        if isinstance(done.get("grounding"), dict)
        else done.get("grounding"),
    }


def tool_runs() -> list[dict[str, Any]]:
    sys.path.insert(0, str(ROOT / "backend"))
    from app.settings import Settings
    from tools.context import ToolContext
    from tools.registry import by_name

    ctx = ToolContext(Settings())
    specs = by_name()
    out = []
    for name, args in TOOL_CALLS:
        t0 = time.perf_counter()
        try:
            r = specs[name].run(ctx, **args)
            ok, err = True, ""
            rows = len(r.get("data") or []) if isinstance(r.get("data"), list) else None
        except Exception as e:  # noqa: BLE001 - the probe reports every failure
            ok, err, rows = False, f"{type(e).__name__}: {e}"[:200], None
        out.append(
            {
                "tool": name,
                "args": args,
                "s": time.perf_counter() - t0,
                "ok": ok,
                "error": err,
                "rows": rows,
            }
        )
    return out


def load_test(url: str, n: int) -> dict[str, Any]:
    """n asks at once plus the data routes (each once per ask), all in parallel."""
    from concurrent.futures import ThreadPoolExecutor

    qs = questions(10**6) or ["Show the largest power plants in Germany on a map"]
    gets = [p for m, p, _ in ROUTES if m == "GET"]

    def one_ask(i: int) -> dict[str, Any]:
        with httpx.Client() as c:
            try:
                return ask(c, url, qs[i % len(qs)])
            except httpx.HTTPError as e:
                return {"status": 0, "error": str(e)[:200]}

    def one_get(i: int) -> dict[str, Any]:
        t0 = time.perf_counter()
        try:
            r = httpx.get(url + gets[i % len(gets)], timeout=120)
            return {"status": r.status_code, "s": time.perf_counter() - t0}
        except httpx.HTTPError as e:
            return {"status": 0, "s": time.perf_counter() - t0, "error": str(e)[:200]}

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2 * n) as ex:
        fa = [ex.submit(one_ask, i) for i in range(n)]
        fg = [ex.submit(one_get, i) for i in range(n)]
        asks = [f.result() for f in fa]
        routes = [f.result() for f in fg]
    return {"n": n, "wall_s": time.perf_counter() - t0, "asks": asks, "routes": routes}


def names_check() -> list[dict[str, Any]]:
    """agent/evals/area_names.yaml: each name resolves first try to the right country, level
    and an outline within 10 % of the official area."""
    from app.settings import Settings
    from tools.areas import resolve_area
    from tools.context import ToolContext

    ctx = ToolContext(Settings())
    out = []
    for c in yaml.safe_load((EVALS / "area_names.yaml").read_text(encoding="utf-8"))["questions"]:
        t0 = time.perf_counter()
        d = resolve_area(ctx, names=[c["q"]])["data"]
        a = d.get("area") or {}
        km2 = a.get("area_km2") or 0
        ok = (
            a.get("iso3") == [c["iso3"]]
            and (
                not c.get("level")
                or a.get("level") in (c["level"] if isinstance(c["level"], list) else [c["level"]])
            )
            and abs(km2 - c["km2"]) <= 0.1 * c["km2"]
            and not d.get("ambiguous")
        )
        out.append(
            {
                "id": c["id"],
                "q": c["q"],
                "ok": ok,
                "s": time.perf_counter() - t0,
                "got": {k: a.get(k) for k in ("name", "level", "iso3", "area_km2")},
                "note": (d.get("note") or d.get("error") or "")[:160],
            }
        )
    return out


def resolve_profile() -> str:
    """Where one resolve_area call spends its time on the real lake (brief 30): cProfile of a
    second call for a region and a city (the first call of each opens the sets)."""
    import cProfile
    import io
    import pstats

    from app.settings import Settings
    from tools.areas import resolve_area
    from tools.context import ToolContext

    ctx = ToolContext(Settings())
    out = []
    resolve_area(ctx, names=["Lower Saxony"])  # opens the sets
    for name in ("Saxony-Anhalt", "Toulouse"):  # names not asked before (a repeat is in memory)
        prof = cProfile.Profile()
        prof.enable()
        resolve_area(ctx, names=[name])
        prof.disable()
        buf = io.StringIO()
        st = pstats.Stats(prof, stream=buf).sort_stats("cumulative")
        st.print_stats(r"(areas|area_stats|duck|gazetteer)\.py", 14)
        out.append(
            f"### resolve_area({name!r}), first call after the sets are open\n```\n"
            + "\n".join(
                line
                for line in buf.getvalue().splitlines()
                if line.strip()[:1].isdigit() or "cumtime" in line
            )[:3000]
            + "\n```"
        )
    return "\n".join(out)


def pct(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, round(p / 100 * (len(xs) - 1))))
    return xs[k]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--questions", type=int, default=30)
    ap.add_argument("--load", type=int, default=0, help="concurrent asks for the load test")
    ap.add_argument("--json", default="/tmp/atlas-latency.json")
    a = ap.parse_args()

    proc = None
    cold = None
    url = a.url
    if not url:
        proc, url, cold = start_server()
    rec: dict[str, Any] = {"cold_start_to_health_s": cold, "routes": [], "tools": [], "asks": []}
    try:
        with httpx.Client() as c:
            for method, path, body in ROUTES:
                t0 = time.perf_counter()
                try:
                    r = c.request(method, url + path, json=body, timeout=120)
                    st, err = r.status_code, "" if r.status_code < 400 else r.text[:200]
                except httpx.HTTPError as e:
                    st, err = 0, str(e)[:200]
                print(f"route {method} {path}", file=sys.stderr, flush=True)
                rec["routes"].append(
                    {
                        "route": f"{method} {path}",
                        "status": st,
                        "s": time.perf_counter() - t0,
                        "error": err,
                    }
                )
            # the warm repeat: the same routes again
            for method, path, body in ROUTES:
                t0 = time.perf_counter()
                r = c.request(method, url + path, json=body, timeout=120)
                rec["routes"].append(
                    {
                        "route": f"{method} {path} (warm)",
                        "status": r.status_code,
                        "s": time.perf_counter() - t0,
                        "error": "",
                    }
                )
            for i, q in enumerate(questions(a.questions)):
                rec["asks"].append(ask(c, url, q))
                x = rec["asks"][-1]
                print(
                    f"ask {i + 1}: {x.get('total_s', 0):.1f} s {q[:60]}",
                    file=sys.stderr,
                    flush=True,
                )
        if a.load:
            rec["load"] = load_test(url, a.load)
        rec["tools"] = tool_runs()
        rec["names"] = names_check()
        rec["resolve_profile"] = resolve_profile()
    finally:
        if proc:
            proc.terminate()
    Path(a.json).write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")

    print(f"cold start to first health answer: {cold:.2f} s" if cold else "server given by --url")
    print("\n| Route | Status | Time (s) |\n|---|---|---|")
    for r in rec["routes"]:
        print(
            f"| `{r['route']}` | {r['status']} | {r['s']:.2f} |"
            + (f" {r['error'][:80]}" if r["error"] else "")
        )
    print("\n| Tool | OK | Time (s) | Note |\n|---|---|---|---|")
    for t in rec["tools"]:
        print(
            f"| `{t['tool']}` {json.dumps(t['args'])[:60]} | {'yes' if t['ok'] else 'NO'} | {t['s']:.2f} | {t['error'][:80]} |"
        )
    print("\n| Name | OK | Resolved to | Time (s) |\n|---|---|---|---|")
    for n in rec["names"]:
        g = n["got"]
        print(
            f"| {n['q']} | {'yes' if n['ok'] else 'NO'} | {g['name']} ({g['level']}, {g['iso3']}, {g['area_km2']} km²) {n['note'][:60]} | {n['s']:.2f} |"
        )
    print("\n" + rec["resolve_profile"])
    asks = [x for x in rec["asks"] if x.get("status") == 200]
    by_tool: dict[str, list[float]] = {}
    for x in asks:
        for t in x["tools"]:
            if t.get("ms") is not None:
                by_tool.setdefault(t["name"], []).append(t["ms"] / 1000)
    print(
        f"\nAsks: {len(asks)} of {len(rec['asks'])} answered; errors: {sum(1 for x in asks if x['error'])}"
    )
    for label, key in (
        ("first event", "first_event_s"),
        ("total", "total_s"),
        ("SSE overhead", "sse_overhead_s"),
    ):
        xs = [x[key] for x in asks if x.get(key) is not None]
        if xs:
            print(
                f"- {label}: p50 {statistics.median(xs):.2f} s, p95 {pct(xs, 95):.2f} s, max {max(xs):.2f} s"
            )
    print("\n| Tool in asks | Calls | p50 (s) | p95 (s) |\n|---|---|---|---|")
    for name, xs in sorted(by_tool.items()):
        print(f"| `{name}` | {len(xs)} | {statistics.median(xs):.2f} | {pct(xs, 95):.2f} |")
    if rec.get("load"):
        ld = rec["load"]
        ok = [x for x in ld["asks"] if x.get("status") == 200 and not x.get("error")]
        tot = [x["total_s"] for x in ok]
        rs = [x["s"] for x in ld["routes"] if 0 < x.get("status", 0) < 500]
        print(
            f"\nLoad test: {ld['n']} concurrent asks + {ld['n']} data-route reads, wall {ld['wall_s']:.1f} s"
        )
        print(
            f"- asks: {len(ok)} ok, {ld['n'] - len(ok)} errors; total p50 {statistics.median(tot) if tot else float('nan'):.2f} s, p95 {pct(tot, 95):.2f} s"
        )
        print(
            f"- routes: {len(rs)} ok, {ld['n'] - len(rs)} errors; p50 {statistics.median(rs) if rs else float('nan'):.2f} s, p95 {pct(rs, 95):.2f} s"
        )
    data_routes = [
        r["s"] for r in rec["routes"] if "(warm)" in r["route"] and "/api/maps" not in r["route"]
    ]
    if data_routes:
        print(
            f"\nData routes warm: p50 {statistics.median(data_routes):.2f} s, p95 {pct(data_routes, 95):.2f} s"
        )


if __name__ == "__main__":
    main()
