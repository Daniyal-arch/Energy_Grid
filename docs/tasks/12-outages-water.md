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

## Part B: WRI Aqueduct 4.0 (CC BY 4.0)

Baseline water stress and riverine/coastal flood risk per catchment (download; data
dictionary in GitHub `wri/Aqueduct40`). Build a simplified catchment layer (or a hex grid of
the categories) light enough for the globe; world layer "Water stress" (group "Industry &
data") for site screening, with WRI's own category labels.

## Both

Files under `frontend/public/data/eu/` (or PMTiles on R2 if over ~5 MB, uploaded by a
workflow), docs/DATA_SOURCES.md sections, ruff, pytest, `npm run build`; spot checks in the
PR. Merge `origin/main` before opening the PR.
