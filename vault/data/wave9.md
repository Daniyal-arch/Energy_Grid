---
title: Wave 9
tags: [data, wave9, coverage]
updated: 2026-10-31
paths: [scripts/wave9.py, scripts/wave9_sources.yaml, scripts/wave9_families.yaml, .github/workflows/wave9.yml, data/wave9_built/, data/wave9_probes.json, data/wave9_search.json]
---

# Wave 9 (brief 28)

One registry, one script, one workflow for every source of brief 28.

- **Registry** `scripts/wave9_sources.yaml`: one entry per source probed (id, title, category,
  coverage family, places, level, kind, url, licence, status `build | have | blocked | left_out |
  not_published`, why and data request). Kinds: csv, csv_zip, csv_gz, xlsx, xls (pandas, header
  row found, cover sheets skipped, zip members), ods, json, socrata, jsonstat, odata, ckan
  (newest resource of a search), govuk (attachment by title), sciencebase, dirlist (newest file),
  fwf, geojson, gpkg, shp_zip, gpkg_zip, arcgis (paged), page (probe only).
- **Families** `scripts/wave9_families.yaml`: the coverage families of wave 9, the level a full
  cell has, and the query searched on data.europa.eu (phrase), catalog.data.gov and data.gov.uk
  for the evidence behind a dark cell (`python scripts/wave9.py search`, `data/wave9_search.json`).
- **Build** (`wave9.yml`, `[w9: P 0 1 ... 17]` in a commit message): one job per category; each
  source on its own; lake `wave9/<id>` (GeoParquet with bbox when positioned); a map file
  `w9/<id>.json` for point sources up to 30,000 records (all or none); the build record
  `data/wave9_built/<cat>.json` (rows, columns, example answer) committed back.
- **Render** (`python scripts/wave9.py render`): coverage families and cells (Part A families
  only gain built cells), docs/research/wave9-sources.md, the DATA_SOURCES and DATA_LAKE blocks,
  `agent/catalog/wave9.yaml`, the level rows, `frontend/src/app/wave9.json` (layers and datasets).
- Part C: Tasks dashboards (`store.ts`), eleven task skills, `agent/evals/tasks.yaml`.

See [[coverage-and-gaps]], [[lake]], [[agent-tools]], [[state-and-datasets]].
