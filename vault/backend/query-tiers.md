---
title: Query tiers (prepared, hot, lake) and exact area sums
tags: [backend, lake, latency]
updated: 2026-11-08
paths: [backend/tools/prepared.py, backend/tools/area_sum.py, backend/data/duck.py, backend/probes/probe_query_speed.py, backend/probes/build_prepared.py, scripts/build_hot.py, scripts/lake_rewrite.py, scripts/lake_storage.py, scripts/raster_recompress.py]
---

# Query tiers (brief 32)

How a question gets fast without caching questions: every question is a filter by place, a
filter by attribute, an aggregate and a join, and each is made fast on every dataset. Builds on
[[instant-answers]], [[lake]] and [[areas]]. Owner-facing text: `docs/AGENT.md` section 15,
`docs/DATA_LAKE.md` "Brief 32".

## Tiers
- **Tier 0, prepared answers** (`tools/prepared.py`): `quick` looks up `prepared.answers`
  (per `area_id` and template key) before running a template. Served only when hot.duckdb is
  attached and the row's `fingerprint` equals the app tables' sources (`fingerprint(ctx)`);
  results carry `prepared.built`. Built by `probes/build_prepared.py` (`backend-probe.yml` job
  `prepared`, eight shards): names resolved as users resolve them (countries, US states, NUTS
  1-3, GB LADs, urban centres, local units of 10,000+ people), ambiguous names skipped. Public
  copy: `infraatlas-data/answers/v1/<area_id>.json`.
- **Tier 1, `hot.duckdb`** (`scripts/build_hot.py`, job `hot` after each lake catalogue):
  tables up to 50 MB, rollups, shapes, `prepared`, the name index, `outlines_simple.*`
  (0.001°). `Lake._load_hot` downloads it to `/tmp/hot/` in a background thread, attaches it
  read-only and builds catalog `fast` (a view per table over `hot` or `lake`); `Lake.default`
  switches from `lake` to `fast`; `QueryResult.tier` says which. `HOT_DB=""` switches it off.
- **Tier 2, the lake**: views name their files (`scripts/lake_catalog.py view_path`), so a
  query sends no LIST to R2. `scripts/lake_rewrite.py` brings old files to the row-group
  standard (Hilbert order, capped groups, `bbox`) after equal checksums; `scripts/lake.py`
  enforces it for new files.

## Exact sums for any area
`tools/area_sum.py` (agent tool `area_sum`): H3 cells wholly inside (rollup sums) plus edge
cells' rows tested against the outline = the row-level sum (`tests/test_area_sum.py`).

## Measuring
`probes/probe_query_speed.py` (job `query-speed`, eight shards, input `hot` on/off): every
table's query set with bytes and requests from DuckDB's HTTP log, routes, `quick`,
`resolve_area`, `area_stats`, 200 generated unseen queries. `--merge` writes
`docs/research/query-speed.md` and `data/query_speed.json`; `--check` is the CI speed check
(`backend.yml` job `speed`, a fixed sample, warm p95 +20 % and +50 ms fails).

## Storage
`scripts/lake_storage.py` (audit, dry run, apply of `data/lake_deletions.yaml` only, orphan
registration, agent-cache lifecycle 7 days); `scripts/raster_recompress.py` (lossless test and
apply, lossy options measured for the owner). All by hand in `lake-catalog.yml` inputs
`storage`, `rewrite`, `rasters`.

> [!warning] Gotchas
> - DuckDB needs `pytz` to return `TIMESTAMPTZ` values to Python (added 2026-11-08).
> - A glob view costs one R2 LIST (~250 ms) on every query; keep views on file lists.
> - `ROW_GROUP_SIZE_BYTES` needs `preserve_insertion_order = false`, which loses the sort: cap
>   rows from bytes per row instead. DuckDB's smallest row group is 2,048 rows.
> - Prepared answers hold no `result_id` (results live in one container).
