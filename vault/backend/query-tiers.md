---
title: Query tiers (prepared, hot, lake) and exact area sums
tags: [backend, lake, latency]
updated: 2026-11-09
paths: [backend/tests/test_area_registry.py, backend/tools/prepared.py, backend/tools/area_sum.py, backend/data/duck.py, backend/probes/probe_query_speed.py, backend/probes/build_prepared.py, scripts/build_hot.py, scripts/lake_rewrite.py, scripts/lake_storage.py, scripts/raster_recompress.py]
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
  rollups, shapes, `prepared` and the name index, then lake tables (≤50 MB, ≤1 M rows)
  smallest first until the file reaches 90 % of 1,200 MB (the Lambda's `/tmp` is 2,048 MB). `Lake._load_hot` downloads it to `/tmp/hot/` in a background thread, attaches it
  read-only and builds catalog `fast` (a view per table over `hot` or `lake`); `Lake.default`
  switches from `lake` to `fast`; `QueryResult.tier` says which. `HOT_DB=""` switches it off.
- **Tier 2, the lake**: views name their files (`scripts/lake_catalog.py view_path`), so a
  query sends no LIST to R2. `scripts/lake_rewrite.py` brings old files to the row-group
  standard (Hilbert order, capped groups, `bbox`) after equal checksums; `scripts/lake.py`
  enforces it for new files.

## Areas in queries
- `Lake.register_areas` (`data/duck.py`): each outline parsed once per container into the
  shared in-memory `areamem.areas` (most recently used 300 kept); a cursor gets a view `areas`
  of its own areas and the macros. Was 60-80 ms of GeoJSON parsing on every query.
- `in_area` with a known area: a background thread builds the H3 cells wholly inside
  (`areamem.cells`) and the outline clipped to each buffered edge cell (`areamem.clips`, with
  its boundary); `expand_in_area` then tests cell membership, else the clip, else (within 1e-9°
  of a clip's edge) the whole outline. Equal to `ST_Contains` (`tests/test_area_registry.py`);
  20,000 points in a 60,000-vertex outline: 10 s plain, 60 ms with cells. A query with
  `_area(` waits up to `CELLS_WAIT_S` (3 s) for its areas' cells, then the plain test answers.
  Two workers build cells (`_cells_pool`); batch jobs call `wait_area_cells` once per area.
- Outlines over `DETAILED_VERTICES` (5,000; `tools/area_sum.py` `_cells_detailed`): boundary
  cells from sampling the rings at 0.4 x the smallest edge length plus one ring, candidates
  from a polyfill of the outline simplified and buffered, one exact `ST_Contains` per connected
  group of off-boundary cells (200,000 vertices at res 6: 22 s to 0.9 s). Clips in two steps:
  pieces per res-3 parent group, then each cell from its piece (one copy of the outline per row
  ran out of memory).
- `Areas.from_candidate` keeps built areas by reference (validate, hash, measure once);
  name search over `shapes.*` reads ids first and the `bbox` column.

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
> - `resolve_area` lists `candidates` whenever several outlines match (Germany in the real
>   lake); prepared answers are keyed by the resolved area's id, so ambiguous names are stored
>   too (skipping them left Germany, Bavaria and Berlin unprepared).
> - DuckDB spatial has no prepared geometry: `ST_Contains` costs ~0.45 ms a point against a
>   detailed outline whatever the query form.
> - hot.duckdb: native storage of repetitive tables is far larger than their Parquet; the
>   build fills a 1,200 MB budget (the Lambda's `/tmp` is 2,048 MB).
> - DuckDB's HTTP log (`enable_logging`) grows without end: the probe truncates it after
>   each read (`CALL truncate_duckdb_logs()`).
> - Prepared answers: without `wait_area_cells`, queued cell builds made every query wait 3 s
>   and the shards ran out of time (5,999 of ~9,600 areas).
> - hot.duckdb attaches as catalog `fast` with views only over its own tables; every cursor
>   sets `search_path` to `fast.main,fast.<hot schemas>,lake.<schemas>` (`Duck.cursor`), so a
>   lake table resolves through `lake`. A view per lake table bound its Parquet on R2 and made
>   the file ready only after 500-570 s; now 6-10 s.
> - main's daily `lake-catalog` run rebuilds glob views until brief 32 merges; dispatch
>   `lake-catalog.yml` from the branch to restore file-list views and rebuild hot.duckdb.
> - The Lambda image installs `libexpat1` (rasterio's GDAL); without it `area_stats` failed.
> - `tools/areas.py` keeps the area population in `_PEOPLE` (2,048 areas): re-reading the
>   raster made a warm `resolve_area` of Bavaria take 12 s.
