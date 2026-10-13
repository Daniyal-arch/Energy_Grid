# 14. ENTSO-E history in the lake (2015 onward)

## Goal

Europe's power data in full detail for the agent: prices, load, generation by type, wind and
solar forecasts, cross-border flows, output per unit, installed capacity, transfer capacity
and outages, from 2015 to yesterday, as Parquet in `lake/entsoe/` (docs/DATA_LAKE.md
section 6 has every table, column, partition, sort order and bloom column). The map keeps its
own files; nothing on the map changes.

`ENTSOE_API_KEY` is a GitHub repo secret: the backfill and the daily append run in GitHub
Actions; the session writes and tests the code (it may test against the API with a few
requests only if the key is in its environment; otherwise through a workflow run).

## Reuse

`scripts/entsoe.py` already speaks the API (four requests at a time, the document types,
`series_of`, Italy zone by zone, the rules for the newest complete interval in
docs/DATA_SOURCES.md). Build on it; do not write a second client.

## Files

- `scripts/build_lake_entsoe.py`: `--year 2019` (one year, every table) and `--recent 3`
  (re-fetch the last three days of the current year's partitions, then rewrite those files).
  One ordered file per table and year with `scripts/lake.py`; `areas` and `units` dimension
  tables (units: EIC, plant, name, area, type, capacity, and JRC-PPDB positions where
  `build_eu_units.py` already places them).
- `.github/workflows/lake-entsoe.yml`: `workflow_dispatch` with a `years` input runs one job
  per year in parallel (matrix 2015..current, `max-parallel` low enough for ENTSO-E's limit of
  400 requests a minute per key: measure it in the first run); a daily schedule after
  `eu-days` appends the recent days. Each job uploads its year with `Lake.upload()` (repo
  secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `ENTSOE_API_KEY`).
- Resolution: keep each series at the resolution ENTSO-E publishes (`resolution_min`), no
  resampling. Values passed through (prices `DECIMAL(9,2)`, MW as published).
- docs/DATA_SOURCES.md: a "Lake: ENTSO-E" section (what, from when, gaps per area).

## Done-check

ruff, pytest (a unit test for the table builders with a small XML fixture), the workflow run
for one year green, then all years; the catalogue's rows and bytes per table in the PR; three
values checked against the ENTSO-E Transparency website (one price, one load, one unit's
output). Merge `origin/main` before opening the PR.
