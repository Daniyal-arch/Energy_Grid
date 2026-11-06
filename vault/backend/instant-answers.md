---
title: Instant answers, cache and streaming
tags: [backend, agent, latency]
updated: 2026-11-05
paths: [backend/tools/quick.py, backend/app/routes/quick.py, backend/agent/graph.py, backend/agent/cache.py, backend/app/live_runs.py, backend/agent/suggest.py, backend/tools/more.py, backend/probes/probe_latency.py]
---

# Instant answers, cache and streaming (brief 30 Track 4)

Model-independent speed and plumbing around [[agent-graph]] and [[agent-tools]].

## Instant answers
- `tools/quick.py`: six SQL templates (`profile`, `top`, `totals`, `compare`, `published`,
  `prices`) over the app tables, through `run_sql` (guard, sources); each table has its method
  and `as_of`. A whole country or group filters by country codes, smaller areas by outline.
- Served as `GET /api/quick/{template}?area=` (`app/routes/quick.py`), the `quick` tool, and the
  graph's `quick` node: `match()` regexes route a question straight to a template with no model
  call (questions naming a map/chart go to the agent). Grounding still runs.
- Follow-up chips (`agent/suggest.py`): template questions for the turn's areas, sent in `done`.

## Cache
- `agent/cache.py`: key = tool + normalised args (SQL whitespace/case folded, literals kept) +
  lake catalogue date; local `results_dir/cache/` and R2 `agent/cache/`; 512 kB cap per entry,
  2,000 local entries, 7-day expiry; errors not cached; a hit restores the result id's rows.
  `run_sql`, `quick`, `area_stats`, `describe_table`, `search_catalog`, `site_figures` only.

## Streaming
- `app/live_runs.py`: the graph runs as its own task into a buffer; events carry `id:`; the
  first is `run` (run id, also header `x-run-id`). `GET /api/ask/{run_id}/stream` with
  `Last-Event-ID` resumes; `POST /api/ask/{run_id}/cancel` stops it. In-process only (Lambda:
  same instance, 15 minutes).
- A tool over `TOOL_TIMEOUT_S` returns `timeout`, `missing` and an instruction to answer with
  what is there.

## More tools
`tools/more.py`: `nearest` (haversine km), `along` (corridor area from a line), `compare_areas`,
`trend` (capacity by commissioning year: the present fleet's age profile), `export` (CSV,
GeoJSON, Parquet with terms; refuses non-commercial/no-redistribution; files at
`/api/exports/<name>`), `explain_coverage`. All on MCP too (`docs/MCP.md`).

## Latency
`probes/probe_latency.py` (routes, tools, names, 30 eval asks, load test) runs in
`backend-probe.yml` against the real lake. Before (2026-11-05): `resolve_area` 6-60 s on R2
(name normalised per row: fixed with `name_norm`), cold `run_sql` 16 s (fixed by warming at
start). One uvicorn process serialises a load test; Lambda gives each request an instance.

> [!warning] Security tests
> `tests/test_security.py` fuzzes the guard and checks no route leaks keys or traces; real-model
> injection cases are in `agent/evals/injection.yaml` (the owner runs them).
