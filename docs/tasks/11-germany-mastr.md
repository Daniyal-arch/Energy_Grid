# 11. Every generating unit in Germany (Marktstammdatenregister)

## Goal

Germany's official register of every unit (solar, wind, storage, CHP, …; 8 M+ records):
installed capacity by technology per municipality, and the large units as points. No key
(bulk download).

## Probe first (`scripts/probe_mastr.py`)

The daily bulk XML dump (Bundesnetzagentur, MaStR "Datendownload"; the `open-mastr` package
reads it): size (several GB zipped: say so before downloading, and run the download in GitHub
Actions, not the session), tables, licence (dl-de/by-2-0 expected: confirm), coordinates
(only units above a size have them; small units carry a postcode and municipality).

## Files

- `.github/workflows/mastr.yml` (monthly + dispatch): download, aggregate, commit the small
  outputs to main. `scripts/build_mastr.py` → `frontend/public/data/eu/mastr/units_large.json`
  (units ≥ 1 MW with coordinates: lon, lat, technology, MW, commissioning, status) and
  `mastr/municipalities.json` (MW per technology per Gemeinde, AGS code) with Gemeinde
  outlines from BKG VG250 (dl-de/by-2-0) simplified, or centroids if outlines are too heavy.
- docs/DATA_SOURCES.md: compare totals with ENTSO-E A68 and the panel's powerplantmatching
  note (German wind per turbine).

## Map and panels

Layer "Germany: every unit" (coverage DE): municipalities shaded by MW of the chosen
technology (solar / wind / storage) and large units as dots from zoom 6. Germany's panel:
units and MW by technology, newest additions per month.

## Full detail in the lake (docs/DATA_LAKE.md)

Besides the map files, keep the full detail as Parquet with `scripts/lake.py` (the lake's
standard: sorted files, zstd, bloom filters, metadata, `_catalog.json`) and upload it from the
workflow to `r2://infraatlas-raw/lake/<dataset>/` (`Lake.upload()`; the workflow passes
`CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` from repo secrets, the session never holds
them). Schemas, partitions, sort order and bloom columns: DATA_LAKE.md section 6. Add the
standard keys (`iso2`, `iso3`, `admin1`) to every table. In the PR: rows and bytes per table
from the catalogue.

Tables: `lake/mastr/` as in DATA_LAKE.md (units per technology, operators, grid connection
points, locations), partition `snapshot` (and `land` for solar), sort `ags, mastr_nr`, bloom
`mastr_nr`. Keep the newest snapshot and one per year.

## Running the heavy part

Downloads of hundreds of MB or more run only in GitHub Actions (CLAUDE.md, hard rule 4). Give
the new workflow a `push:` trigger on its own file and script so it runs when merged, plus
`workflow_dispatch`; while the PR is open it may also run on `push` to the session's branch
(remove that before merging). The job commits the small map files to the branch it runs on
(`git pull --rebase` before `git push`) and uploads the Parquet to R2.

## Done-check

ruff, pytest, `npm run build`; national totals against Bundesnetzagentur's published figures
(PR). Merge `origin/main` before opening the PR.
