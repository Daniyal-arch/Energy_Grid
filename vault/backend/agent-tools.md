---
title: Agent tools
tags: [backend, agent]
updated: 2026-10-27
paths: [backend/tools/, backend/agent/mapspec.py, backend/agent/skills.py, agent/skills/]
---

# Agent tools

Read-only tools of [[agent-graph]], shared with the MCP server ([[backend-service]]). Every
result: `{data, sources: [{dataset, table, licence, retrieved}], result_id?}`.

## Where
- `tools/registry.py`: `specs()` (sorted, for a stable prompt prefix), `langchain_tools(ctx)`.
- `tools/context.py`: `ToolContext` (settings, lake, catalogue, gazetteer, results, store, emit).
- `tools/catalog.py`: `Catalogue` over `agent/catalog/*.yaml`, `datasets.json` and the `app.*`
  tables (`APP_TABLES`); token/idf search.
- `tools/sql.py` (`run_sql`, `describe_table`), `tools/places.py`, `tools/site.py` (the panel's
  place, substations, plants, prices, water figures), `tools/live.py` (eu-data, eu-days, EIA-930;
  rate limits, 10-minute cache), `tools/maps.py` (`make_map`, `make_chart`, `check_map`, layer
  ids read from `frontend/src/app/store.ts`), `tools/results.py` (`result_id` store in /tmp).
- `agent/mapspec.py`: MapSpec, ChartSpec; `scripts/gen_mapspec.py` writes the schema and TS types
  (a test fails when stale).
- `agent/skills.py` + `agent/skills/`: eight skills (lake-sql, make-map, site-screening,
  explain-view, prices, grid-capacity, emissions, places-and-shapes); each body names the
  catalogue entries it relies on.

> [!warning] Catalogue YAML
> Values with ": " must be quoted; seven files did not parse until 2026-10-27. The catalogue
> loader reads every file, so a broken file breaks search.
