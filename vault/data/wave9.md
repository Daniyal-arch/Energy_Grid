---
title: Wave 9
tags: [data, wave9, coverage]
updated: 2026-11-05
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
- **On the map** (after PR #18 review): point sources up to 30,000 records as map files; every
  other positioned source as vector tiles (`w9/<id>.pmtiles`, tippecanoe in the build jobs,
  `map/wave9Tiles.ts`, click card); area series as colourings (`w9c/<id>.json`, ColourId
  `w9c_<id>`, `lib/wave9.ts` quartile stops; countries via countryColour, US counties and GB
  local authority districts via `map/wave9Layers.ts`; the shapes file per scope is
  `W9C_SHAPES`: `usCounties` or `gbLad` = `eu/gb_lad.json`, built by `wave9.py gb-lad`). A
  tippecanoe failure keeps the table and records `tiles.error`. A choro config may carry
  `period_label` when the period is a column name (VEH0131 `c_2021_q4`).

- **Brief 30 kinds**: `raster` (COG to `lake/rasters/wave9/<id>.tif`, measure `w9_<id>` in
  `agent/rasters_waves.yaml` by `render`), `census` (ACS per tract, needs CENSUS_API_KEY),
  `parquet`, `datafair_agg`, json `coords`/`latlon`, csv_zip `member`/`inner` (zip-in-zip);
  `{env:NAME}` in url/headers (missing key = `skipped` record, not a failure). Page-only
  research: `docs/research/page-only-batch-{a,b,c}.md`; failed-build fixes:
  `docs/research/wave9-failed-fixes.md`. See [[freshness]].
- **More kinds (2026-11-06)**: `pxweb` (GET the table's variables, POST every one with "all",
  json-stat2), `aqviewer` (EEA AQ Viewer: one POST per country and year, a capped answer
  refused), `entsoe` (any Transparency document per area via `scripts/entsoe.py`, points as
  published), custom `eur_overture_comm_lines` (Overture infrastructure read anonymously).
  Builds are started by the `[w9: ...]` tag only when that commit is the head of its push;
  otherwise dispatch `wave9.yml` with `groups: "s:<id> ..."`. The single-source job gets the
  same keys as the category jobs. FEMA NFHL is queried in place by the `live` tool
  (`fema_nfhl`).
- **Readers for page-only sources (2026-11-06, `CUSTOM` in `scripts/wave9.py`)**: `pxweb`
  batches the largest variable under `max_cells` (100,000; the API answers 403 above its cell
  limit); `eirgrid_dispatch_down` (workbook bands per year, sections per area and technology,
  MWh and %); `xlsx_multihead` (census sheets with multi-row headers: `head`, `data`, `ids`,
  `id_names`, `group`; ELSTAT); `ine_pt_indicator` (INE JSON `Dados`); `semo_reports` (the
  report API's listed XML files, about two weeks kept); `bfee_abwaerme` (public list, 100 a
  page: 500 was refused). csv `lenient` (DuckDB `strict_mode = false`, SVK); ArcGIS `page` and
  a stop on a server error or an empty layer (GDAL's 200 MB GeoJSON cap lifted); raster
  `member` is a name or a regex. Romania and Serbia connection data wait on owner question 5.

