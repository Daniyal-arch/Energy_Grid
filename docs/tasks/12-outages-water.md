# 12. Risk: US power outages (EAGLE-I) and water stress (WRI Aqueduct)

No keys.

## Part A: EAGLE-I outages (ORNL)

Customers without power per US county every 15 minutes, 2014– (figshare / ORNL DOI pages;
check the licence and the newest year). Probe sizes first (yearly CSVs are large: process in
GitHub Actions). Build per county the yearly customer-hours out and the largest events (top
50 by peak customers, with start and end), plus the newest month at 15 min for a replay if
small enough. Map: counties shaded by customer-hours out per year (Census cartographic
boundaries, public domain); story "US outages" with the biggest storms. "Customers" are
utility meters, not people: label it.

A draft builder is on main: `scripts/build_us_outages.py` (one DuckDB job per year, then a
combine step writing `us_outages.json` and `us/counties.json`); untested: run it in Actions,
fix it, and add the lake tables (`lake/eaglei/outages` partition `year`, sort `fips, ts`, bloom
`fips`; `counties`; `coverage`). EAGLE-I's files: figshare article 24237376 (2014-2025, 12
CSVs, 0.08-1.4 GB each; the 2023 file names its count column `sum`). Hours without power per
customer use ORNL's `MCC.csv` (modelled customers per county); say so.

## Part B: WRI Aqueduct 4.0 (CC BY 4.0)

Baseline water stress and riverine/coastal flood risk per catchment (download; data
dictionary in GitHub `wri/Aqueduct40`). Build a simplified catchment layer (or a hex grid of
the categories) light enough for the globe; world layer "Water stress" (group "Industry &
data") for site screening, with WRI's own category labels.

Download `https://files.wri.org/aqueduct/aqueduct-4-0-water-risk-data.zip` (262 MB) in
Actions; geometry is in the GDB (`ogr2ogr`/GDAL or `pyogrio`), indicators also in
`CVS/Aqueduct40_baseline_annual_y2023m07d05.csv` (231 columns; `bws_cat`, `bws_label`...).
Lake: `lake/aqueduct/v4.0/baseline_annual` (GeoParquet, all indicators), `baseline_monthly`,
`future_annual`. Map file: per basin (`pfaf_id`) the categories of water stress, riverine and
coastal flood, drought, outlines simplified so the file stays under ~5 MB.

## Both

Files under `frontend/public/data/eu/` (or PMTiles on R2 if over ~5 MB, uploaded by a
workflow), docs/DATA_SOURCES.md sections, ruff, pytest, `npm run build`; spot checks in the
PR. Merge `origin/main` before opening the PR.

## Full detail in the lake (docs/DATA_LAKE.md)

Besides the map files, keep the full detail as Parquet with `scripts/lake.py` (the lake's
standard: sorted files, zstd, bloom filters, metadata, `_catalog.json`) and upload it from the
workflow to `r2://infraatlas-raw/lake/<dataset>/` (`Lake.upload()`; the workflow passes
`CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` from repo secrets, the session never holds
them). Schemas, partitions, sort order and bloom columns: DATA_LAKE.md section 6. Add the
standard keys (`iso2`, `iso3`, `admin1`) to every table. In the PR: rows and bytes per table
from the catalogue.

## Running the heavy part

Downloads of hundreds of MB or more run only in GitHub Actions (CLAUDE.md, hard rule 4). Give
the new workflow a `push:` trigger on its own file and script so it runs when merged, plus
`workflow_dispatch`; while the PR is open it may also run on `push` to the session's branch
(remove that before merging). The job commits the small map files to the branch it runs on
(`git pull --rebase` before `git push`) and uploads the Parquet to R2.

