# 15. The lake for the datasets already on the map, its catalogue and topic views

## Goal

Every dataset the map already uses that docs/DATA_LAKE.md (section 7) marks "Parquet" or
"snapshots" gets its full detail in the lake; the lake gets one catalogue and the topic views
the agent queries. ENTSO-E (task 14), EAGLE-I and Aqueduct (task 12), MaStR (task 11) and the
Overture extract (task 07) are done elsewhere: leave them out.

## Datasets (all with `scripts/lake.py`, uploaded by workflows)

| Dataset | Script to extend | Tables |
|---|---|---|
| ENTSOG gas flows, 2015– | `fetch_entsog.py` (+ a backfill `--year`) | `flows` (gas day, point, direction, operator, kWh/d), `points` |
| EIA-930 hourly, 2015– | `fetch_us.py` / `build_us_day.py` | `demand`, `generation_by_fuel`, `interchange` per BA; `bas` |
| EIA-860M | `fetch_us_grid.py` | `generators` per monthly snapshot |
| LBNL queue | `fetch_us_grid.py` | `requests` per yearly release |
| IRENA | `fetch_irena.py` | `capacity`, `generation` |
| JRC-PPDB, powerplantmatching | `build_eu_units.py`, `fetch_eu_reference.py` | `units`, `plants` |
| GEM trackers (private licence) | `fetch_gem.py --pull-r2` in `gem.yml` | one table per tracker, partition `release` (never public) |
| OSM-derived (Europe grid, cables, data centres) | `build_eu_grid.py`, `fetch_cables.py`, `fetch_world.py` | snapshots |
| EU ETS registry | `fetch_eu_ets.py` | `installations` (snapshot), `verified_emissions`, `eea_link` |
| NESO TEC, Dutch capacity map, REE nodes | `fetch_connect_here.py` | snapshots (DATA_LAKE.md section 6) |

Each gets the standard keys (`iso2`, `iso3`, `admin1`, position) and its own `_catalog.json`.
Add the lake step to the workflow that already fetches the dataset (`eu-days.yml`,
`us-grid.yml`, `gem.yml`, `eu-snapshot.yml`); backfills get `workflow_dispatch` inputs.

## Catalogue and views

- `scripts/lake_catalog.py` + `.github/workflows/lake-catalog.yml` (daily, after the other
  jobs): read every `lake/*/_catalog.json` from R2, write `lake/_catalog.json` (datasets,
  tables, rows, bytes, updated) and `lake/lake.duckdb`: a read-only DuckDB file with one view
  per table over its R2 path (hive partitioning) and the topic views of DATA_LAKE.md section
  3 (`plants`, `prices`, `outages`, `emissions`, `grid_capacity`, `water_risk`), each with a
  `source` column. Views over datasets not built yet are created when their catalogue appears.
- Update DATA_LAKE.md section 7: replace the estimated sizes by the measured ones.

## PUDL in place (measure, do not copy)

`scripts/probe_pudl.py`: from a GitHub runner, time three agent-like queries against PUDL's
public Parquet (EPA CEMS hourly: one plant in one month; one state in one year; EIA-923 one
plant's monthly generation). Write the timings into DATA_LAKE.md; if a query takes over ~5 s,
say so (the rule's second test) and propose an extract.

## Done-check

ruff, pytest, the workflows green, `lake/_catalog.json` listing every dataset with rows and
bytes (in the PR), a query through `lake.duckdb` on one topic view shown in the PR. Merge
`origin/main` before opening the PR.
