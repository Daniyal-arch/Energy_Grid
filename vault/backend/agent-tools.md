---
title: Agent tools
tags: [backend, agent]
updated: 2026-10-31
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

## Areas (planned, brief 27)
- Today the agent gets the view's countries only (`view.area`), not a drawn polygon, and no
  tool filters by an outline. Brief 27 adds `resolve_area` (any level, unions, buffers, the
  drawn area), an `areas` view and `in_area()` macro in `run_sql`, `area_stats` (rasters summed
  in a polygon) and MapSpec `area` (outline, clip, camera).

## Maps (2026-10-29)
- MapSpec v2 (`agent/mapspec.py`): 12 flat and 10 3D styles (`FLAT_STYLES`, `STYLES_3D`),
  `panels` for 2-6 maps side by side, `replaces` for edits; `check_map` covers panels.
- The analyst does not get `make_map`/`make_chart` (`Deps.analyst_tools`); the cartographer
  draws. MCP keeps them.
- `run_sql` shows the model `sql_rows_returned` rows (default 200); maps and charts read all
  rows by `result_id`.
- **Areas (brief 27)**: `resolve_area`, `area_stats`, `in_area()` in SQL; see [[areas]].
  Catalogue entries for wave 8: outlines, small_area_energy, industrial, dams, co2stop,
  hotmaps, gem_ownership, tri, uk_pi.
- **Customer tasks (brief 28)**: eleven task skills (checklists, no composite score); wave 9
  tables as `wave9.<id>` and map files as `app.w9_<id>`; evals `agent/evals/tasks.yaml`.
