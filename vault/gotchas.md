---
title: Gotchas
tags: [gotchas]
updated: 2026-10-31
---

# Gotchas

> [!warning] Windows laptop
> `uv` is not on PATH: in PowerShell prepend `$env:Path = "$env:APPDATA\Python\Python313\Scripts;$env:Path"`.
> `zoneinfo` needs `tzdata` (a dependency). Git warns about LF/CRLF; harmless.

> [!warning] r2.dev limits concurrent requests
> Read a lookup grid area in one range request (`readGrid` in `frontend/src/lib/area.ts`, up to
> 4 MB) with retries; never fire hundreds at once. The Maps view's six maps share the limit.

- **ENTSO-E** newest intervals arrive late and in parts (Italy zone by zone); pick the newest
  complete interval (rules in `docs/DATA_SOURCES.md`). Four requests at a time.
- **Day archive**: a day with fewer than 20 ENTSO-E countries is a failed fetch
  (`scripts/build_eu_day.py` `MIN_COUNTRIES`); it is rebuilt, not indexed.
- **powerplantmatching** lists German units individually: German wind sums ~12 % above the
  official capacity; panels show both.
- **EU ETS positions**: only installations the EEA register links by ETS id are placed (2,234 of
  9,668; Germany 78 of 1,818); the UK ETS has none. Brief 24. See [[coverage-and-gaps]].
- **`Math.max(...array)`** on large arrays overflows the call stack: use loops.
- **Memo keys** (`frontend/src/map/memo.ts`) are global by name: per-map values need the map's
  `scope` in the key (the Maps view draws up to six maps with the same code).
- **Interleaved deck.gl** layers are inserted before `label-names`; a map style without that
  layer drops them.
- **Range requests in Edge** need `cache: "no-store"` (else `ERR_CACHE_OPERATION_NOT_SUPPORTED`).
- **GitHub CLI** is not installed on the laptop; Actions are dispatched through the REST API with
  the git credential token.
- **Backend**: DuckDB 2.0's lockdown needs the CA bundle allowed; catalogue YAML values with
  ": " must be quoted; see [[backend-service]] and [[agent-tools]].
- **Wave 8 sources**: the Census API refuses keyless requests (redirect to missing_key.html);
  Nomis returns 25,000 rows a request (page with `recordoffset`); DESNZ xlsx headers carry line
  breaks and a note row naming the columns; GHSL UCDB names carry a byte-order mark; IRIS
  geometries are GeoArrow; R2 multipart uploads need `AWS_REQUEST_CHECKSUM_CALCULATION=WHEN_REQUIRED`;
  rasterio's Env rejects AWS_* keys (use `AWSSession`); DuckDB needs `SET GLOBAL
  geometry_always_xy = true` before the lockdown.
- **rasterio on the laptop**: PostGIS sets `PROJ_LIB` to its own older `proj.db`, so the
  backend's raster tests fail with `CRSError: The EPSG code is unknown`; clear `PROJ_LIB` for the
  run (`Remove-Item Env:PROJ_LIB`). CI is unaffected.
- **public.ecr.aws rate limit**: the backend image job can fail with `429 Too Many Requests ...
  Data limit exceeded` pulling the Lambda adapter image anonymously; re-run the job.
- **GitHub `contains()` on a string ignores case**: `contains(groups, 'C')` matched "Mworldcover";
  wave8.yml compares whole words (`fromJSON(words)`). DuckDB 1.5 on runners refuses the `x -> y`
  lambda (write `lambda x: y`). The outline name index must read every set (local or R2), or a
  partial rebuild shrinks it.
- **Wave 9 sources**: DuckDB reads JSON with many keys as one MAP column unless
  `map_inference_threshold = -1`; gov.uk ODS workbooks start with cover sheets; the Census API
  needs a key; data.europa.eu ORs the words of a query unless quoted; catalog.data.gov's CKAN API
  moved (use `/search?q=`); some CSVs are CP1252 (recode before DuckDB).
