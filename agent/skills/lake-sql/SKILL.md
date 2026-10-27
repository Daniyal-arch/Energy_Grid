---
name: lake-sql
description: Writing DuckDB SQL over the lake and the app tables - names, units, time zones, aggregation and the API-or-Parquet rule. Use before any run_sql that is more than a simple lookup.
---
# Lake SQL

Relies on: every `agent/catalog/*.yaml` entry with `tables`, and the app tables `app.*`.

1. Names: lake tables are `<dataset>.<table>` (e.g. `registers.gb`, `eaglei.outages`); the app
   tables are `app.eu_plants`, `app.eu_substations`, `app.eu_prices`, `app.world_plants`,
   `app.us_plants`. Quote columns that are SQL words (`"group"`, `"start"`).
2. Units come from `describe_table`: never assume. MW stays MW unless you convert in SQL
   (`sum(mw) / 1000 AS gw`) and say so. kW columns are converted where the catalogue says
   (`gross_kw / 1000`).
3. Time: timestamps are UTC unless the catalogue says local. Filter with half-open ranges
   (`ts >= '2024-01-01' AND ts < '2025-01-01'`). Interval data: energy = value x interval length
   (`sum(customers_out) * 0.25` for 15-minute intervals).
4. Aggregate in SQL; return only the rows the answer or the map needs. `round()` only for the
   final figure, at the precision the source publishes.
5. API or Parquet (docs/DATA_LAKE.md section 1): a catalogue entry with `access: api` has no
   lake table; use the `live` tool or say the figure needs a live read.
6. Partitioned tables (`year=`, `snapshot=`): filter on the partition column first; the newest
   snapshot is `max(snapshot)`.
7. Licensed Global Energy Monitor tables (`gem*`) only in aggregates (sum, count) with GROUP BY.
8. A refused or failed query comes back with the reason: fix it, do not retry it unchanged.

See `references/patterns.md` for worked patterns.
