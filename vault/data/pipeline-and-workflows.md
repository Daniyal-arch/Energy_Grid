---
title: Pipeline and workflows
tags: [data, ci]
updated: 2026-10-29
paths: [scripts/, .github/workflows/, frontend/public/data/, docs/DATA_SOURCES.md]
---

# Pipeline and workflows

Scripts fetch and build every file the map reads; GitHub Actions run them on schedules and own
the data branches. Every file and its source: `docs/DATA_SOURCES.md`. The lake: [[lake]].

## Where
- `scripts/` (~165 files): `fetch_*.py` and `build_*.py` per source, `probe_*.py` before new
  sources, `entsoe.py` (ENTSO-E client, four requests at a time), `cloud_setup.sh` (cloud session
  dependencies). Tests in `tests/` (pytest).
- Bundled files: `frontend/public/data/eu/` and `frontend/public/data/us/` (committed with the
  code). Live files: branch `eu-data`; day archive: branch `eu-days` (written only by Actions).

## Workflows (`.github/workflows/`, schedule UTC)
- `eu-snapshot.yml` hourly at :37 (loops inside the run with a deadline): live flows, prices,
  generation, outages onto `eu-data`.
- `eu-days.yml` daily 07:23: the 30-day archive per 15 minutes and transmission outages onto
  `eu-days`; days with fewer than 20 ENTSO-E countries are rebuilt.
- `lake-entsoe.yml` daily 04:41, `lake-catalog.yml` daily 09:47, `lake-datasets.yml`,
  `lake-overture.yml` monthly: the lake on R2.
- `gem.yml` weekly (GEM trackers; raw files only in the private bucket), `mastr.yml` monthly,
  `us-grid.yml` monthly, `us-queues.yml` weekly, `browser-fetch.yml` monthly.
- On demand: `atlas.yml`, `world-grid.yml`, `world-hv.yml`, `water-risk.yml`, `us-outages.yml`,
  `wave5/6/7.yml` (dataset waves), `probe-*.yml`, `diag-entsoe.yml`.
- Room to connect: `wave7.yml` job R runs `build_connect_h23.py all`, `build_connect_h26.py all`,
  then `build_connect_harmonised.py --osm --upload` (Overpass name matching, unreliable from a
  cloud sandbox: never regenerate `harmonised.json` locally without the OSM cache, the matched
  positions would be lost).

## How to run things
- Locally: `uv run python scripts/<script>.py`; frontend `cd frontend && npm run dev`.
- Dispatch a workflow: `gh workflow run <file>` (or the REST API where `gh` is missing).
- Secrets live in repo secrets (ENTSO-E, EIA, EPA, Cloudflare, GEM form, ...); never printed.
- **wave8.yml** runs on pushes to `claude/**` whose commit message carries `[w8: <groups>]`
  (O outlines, R/Rpop/Rbuilt rasters, S/M class shares, C small-area energy, A asset layers,
  P probes, T in_area timing); A commits `frontend/public/data/eu/w8/*.json` to the branch, so
  pull before the next push.
