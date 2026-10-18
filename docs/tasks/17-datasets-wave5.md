# 17. Datasets wave 5: 22 datasets in one session (20 to build, 2 blocked)

Read CLAUDE.md, then this file. Each dataset below has a fixed spec: source, what to build, where it
shows. Follow the spec; do not redesign, do not research beyond the probe. Work through the
checklist in order; commit and push after each dataset. If a source needs a login or key, is closed,
or its licence forbids reuse: stop that dataset, add one line to the PR (what blocked it, the sign-up
URL, the env var name), and continue with the next one. Never estimate a missing value.

## Run to the end (owner's standing approval, 2026-10-18)

- **Do not stop to ask or to show results.** The probe already ran (branch
  `claude/busy-fermat-nodvwe`, workflow "Probe wave 5", 2026-10-18); its findings are the decisions
  below. CLAUDE.md's "show the probe output" is met by listing it in the PR. The owner approves the
  large downloads named here (CGAZ 360 MB, GHSL 484 MB, Global Renewables Watch 453 MB, EDGAR) in
  GitHub Actions. Keep working until every dataset is ✅ or ⛔; only then open the PR.
- **20 datasets are required** (all except 20 Grid-India and 22 Black Marble, blocked below). Allowed
  reasons to mark one ⛔: a login/key the environment lacks, a licence that forbids reuse, or a
  source that fails twice in Actions with the error quoted. "It is a lot of work" is not one.
- **A dataset is ✅ only when all of these hold:** its build ran in Actions on the branch and its
  output exists (repo file ≤ 5 MB, or R2 / lake upload confirmed by the run); its UI piece from the
  spec is in (layer + key + card, or the rows/card named); a refresh step exists (workflow step or
  documented "by hand"); docs/DATA_SOURCES.md section, docs/DATA_LAKE.md row, `agent/catalog/<name>.yaml`;
  one pytest for its pure parsing/shaping function. Partial work stays ☐ in the PR checklist.
- **One build workflow for all:** `.github/workflows/wave5.yml` (`workflow_dispatch` + `push` on
  the branch), one job per dataset group with `continue-on-error`, each committing its small outputs
  back to the branch; the session triggers it, waits, pulls, and reads only the job summaries. Delete
  the branch trigger before the PR; keep the scheduled refresh steps in the existing workflows.

## Decisions from the probe (do not probe again)

| # | Finding | Decision |
|---|---|---|
| 1 NUTS | GISCO file reachable | build as specified |
| 2 Bidding zones | electricityMaps geometry is AGPL-3.0; entsoe-py's are copies of it | build zones from NUTS regions (zone → NUTS ids per zone, documented); label them "approximate outline (NUTS regions)"; single-zone countries = the country |
| 3 CGAZ ADM1 | 360.5 MB, CC BY 4.0 per geoboundaries.org | build as specified |
| 4 GeoNames | CC BY 4.0, 34,167 cities, 6,284 ≥ 100,000 people | build as specified |
| 5 EIA-923 | PUDL `core_eia923__monthly_generation_fuel` (to 2026-06), `out_eia__yearly_generators` (has `capacity_factor`), `out_eia__yearly_plants` | use PUDL's tables in place; capacity factor = PUDL's where present, else computed and labelled |
| 6 eGRID | `egrid2023_data_rev2.xlsx` (21.2 MB) | build as specified |
| 7 GHGRP | Envirofacts `PUB_DIM_FACILITY` answers (with lat/lon); `2023_data_summary_spreadsheets.zip` (28.4 MB) | facilities from Envirofacts, emissions from the data summary |
| 8 netztransparenz | API needs registration (401); open archive `redispatch export 2013-2020.zip` | build from the open archive (2013–2020); PR lists `NETZTRANSPARENZ_CLIENT_ID/_SECRET` for newer years |
| 9 SMARD | answers, weekly files to 2026-10-11 | catalogue file only (API) |
| 10 TYNDP | pages build links with JavaScript | find the JSON/file endpoint the page calls (two tries in Actions, e.g. the `api`/`assets` requests in the page source); else ⛔ with the error |
| 11 A78 | HTTP 429 "Requester banned": the lake backfill used the same key | run only when no "Lake ENTSO-E" run is active (check with the API before dispatching), one request at a time, short windows |
| 12 GRW | MIT; v1.0 `solar_all_2024q2_v1.gpkg` 395 MB, `wind_all_2024q2_v1.gpkg` 58 MB | build as specified (quarter 2024 Q2) |
| 13 Eurostat balances | API answers (`nrg_bal_c`) | as specified |
| 14 SEDS, 15 STEO | EIA API v2 answers (paginate: 5,000 rows per request) | as specified |
| 16 EI review | resources page builds links with JavaScript | try the file URL the page requests (two tries); else ⛔ |
| 17 EDGAR | `IEA_EDGAR_CO2_1970_2024.zip` and the 2025 booklet xlsx | use the booklet xlsx (per country and sector) |
| 18 JEPX | `spot_summary_2026.csv` answers (Shift-JIS, 48 slots a day, 9 areas); terms page 404 | build it; the PR says the terms of use were not found (owner decides before merge) |
| 19 CENACE | `SWPML/SIM/SIN/MDA/<nodes>/<dates>/JSON` answers | as specified |
| 20 Grid-India | ConnectError from Actions (all endpoints) | ⛔ blocked: refuses GitHub runners |
| 21 GHSL | `GHS_POP_E2025_GLOBE_R2023A_4326_30ss_V1_0.zip` 483.7 MB | as specified |
| 22 Black Marble | LAADS listing 404 without a login | ⛔ blocked: `NASA_EARTHDATA_TOKEN` (urs.earthdata.nasa.gov) |

## Keep the session cheap (token rules)

1. **Read only what you need:** CLAUDE.md, this brief, and the template files named below. Never
   open whole data files (use `head -c 2000`, `python -c` summaries) or long docs end to end
   (grep the section you need in docs/DATA_SOURCES.md and docs/DATA_LAKE.md).
2. **Templates to copy** (read each once):
   - points/areas as a map layer: `scripts/fetch_emodnet_wind.py` → `frontend/src/lib/offshoreWind.ts`,
     `frontend/src/map/offshoreLayers.ts`, its key in `ui/LayersPanel.tsx` (`OffshoreKey`), its card
     in `ui/LayerStats.tsx` (`OffshoreWindCard`), its entry in `app/store.ts` `LAYERS` and `data.ts`.
   - large point sets as tiles: `scripts/fetch_us_lines.py` + `.github/workflows/us-grid.yml` (lines job).
   - lake tables: `scripts/lake.py`, `scripts/build_lake_datasets.py` (one function per dataset).
   - country rows: `frontend/src/components/CountryReport.tsx` (`useSections`).
   - daily refresh steps: `.github/workflows/eu-days.yml` (each step with `timeout-minutes` and
     `continue-on-error: true`).
3. **The probe is done** (`scripts/probe_wave5.py`, decisions table above): do not rerun it. One
   shared helper `scripts/wave5_common.py` (download with retries and progress lines, unzip to a temp
   dir, simplify geometry, write compact JSON, hand tables to `scripts/lake.py`) keeps each build
   script short; write the scripts of a whole group, then run that group once in `wave5.yml` and
   fix what fails, rather than one Actions run per dataset.
   Wait for a run with one polling command (e.g. a loop on the runs API with `sleep 30`), not
   repeated manual checks; read only the failing job's last 40 log lines.
4. **No browser checks:** no headless browser, no screenshots. Verify with `npm run build`,
   `uv run pytest` (add a small test per build script for its pure functions) and the probe output.
5. **Short docs:** per dataset one section in docs/DATA_SOURCES.md (≤ 10 lines: source, licence,
   passthrough, computed, refresh), one row in docs/DATA_LAKE.md §7, one catalogue file
   `agent/catalog/<dataset>.yaml` (format in docs/AGENT.md §4, with 1–2 example queries and their
   answers from your build output), and its status in docs/DATASETS.md set to "have".
6. **Heavy work in Actions:** any download over 50 MB, ENTSO-E, and every lake upload run in
   Actions; outputs over 5 MB go to R2 (PMTiles, lake), not to the repo.
7. **Commits:** one per dataset, no AI attribution. One PR at the end with a checklist (✅ done,
   ⛔ blocked + why). If your context runs low, stop at a dataset boundary, push, update the PR
   checklist with "next: …"; a new session continues from it.

Keys available as secrets/env: `ENTSOE_API_KEY`, `EIA_API_KEY`, `EPA_API_KEY`, `NREL_API_KEY`,
Cloudflare (R2 uploads from Actions only). The large downloads are approved (see "Run to the end"),
Actions only.

8. **No exploring:** don't read frontend files beyond the templates; don't refactor or restyle
   existing code; new map layers follow the offshore-wind template exactly (layer file, key, card,
   `LAYERS` entry in the right group: see `LAYER_GROUPS` in `app/store.ts`).
9. **PR text:** the checklist (one line per dataset: ✅/⛔, output, size, refresh), the blocked list
   with what the owner must do, and the session link. Nothing else.

## The checklist (in this order)

### A. Shapes and names (for the agent and regional maps) → lake `shapes/`, `places/`

1. **NUTS 0–3 (Eurostat GISCO)** — `https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2024_4326.geojson`
   (all levels, `LEVL_CODE`). Lake `shapes/nuts` (GeoParquet: nuts_id, level, name, iso2, geometry).
   Attribution "© EuroGeographics for the administrative boundaries".
2. **European bidding-zone outlines** — probe licence-clean sources (entsoe-py `entsoe/geo/geojson/`,
   electricityMaps `geo/`); if none is clean, build zones from NUTS (zone → NUTS ids, documented
   per zone; Nordic zones need the operators' published zone membership). Lake `shapes/bidding_zones`
   (zone id as in `prices.json`) and `frontend/public/data/eu/zones.json` (simplified, ≤ 1 MB) so
   the Prices view can shade zones (switch `pr-zones` markers to shaded zones when the file is there).
3. **World admin-1 (geoBoundaries CGAZ ADM1, CC BY 4.0)** — `https://github.com/wmgeolab/geoBoundaries/raw/main/releaseData/CGAZ/geoBoundariesCGAZ_ADM1.geojson`.
   Lake `shapes/admin1` (iso3, admin1 id, name, geometry; simplified copy for the map later).
4. **Cities (GeoNames cities15000, CC BY 4.0)** — `https://download.geonames.org/export/dump/cities15000.zip`.
   Lake `places/cities` (name, ascii name, iso2, admin1, lon, lat, population). Add a "City" hit to
   `ui/Search.tsx` from a small `frontend/public/data/eu/cities.json` (cities ≥ 100,000 people).

### B. United States, plant performance and emitters

5. **EIA-923 generation and fuel per plant** — PUDL's public Parquet (`s3://pudl.catalyst.coop/stable/`,
   anonymous; table names from its data dictionary), queried in place with DuckDB. Build
   `frontend/public/data/us/plants_perf.json`: per EIA plant id, the newest full year's net generation
   (MWh) and capacity factor (computed: generation ÷ (nameplate × hours)), shown in the US plant hover
   card (`map/tooltip.ts`, `us-plants`).
6. **EPA eGRID** — the newest eGRID plant file (epa.gov/egrid/download-data, xlsx). Add per plant CO₂
   output rate (lb/MWh) and annual CO₂ to `plants_perf.json`; lake `egrid/plants`.
7. **EPA GHGRP** — the newest data summary spreadsheet (FLIGHT/GHGRP downloads) or Envirofacts API.
   Layer "US industrial emitters" (group "Industry & data", points sized by t CO₂e, sector colours as
   `CT_COLOR`), card in "On the map", lake `ghgrp/facilities`.

### C. Germany

8. **netztransparenz.de redispatch and curtailment** — probe the open downloads and the API (the API
   needs a free client registration: if only the API has the data, stop and list
   `NETZTRANSPARENZ_CLIENT_ID`/`_SECRET` with the sign-up URL). Output: German redispatch volume and
   cost per month and curtailment (EinsMan) per TSO area; a card in Germany's country panel; lake
   `netztransparenz/*`.
9. **SMARD (Bundesnetzagentur, CC BY 4.0)** — `https://www.smard.de/app/chart_data/...` (no key).
   API only (the API-or-Parquet rule): a catalogue file listing its series and how to call them; no
   lake copy, no new UI.

### D. The grid that is coming, and lines out of service

10. **ENTSO-E TYNDP 2024 projects** — tyndp2024.entsoe.eu project list (xlsx) and its map data (probe
    the download links). Layer "Planned grid projects" (group "Power grid", Europe): lines/points by
    status (under construction, permitting, planned), commissioning year and capacity in the hover;
    card in "On the map"; lake `tyndp/projects`.
11. **ENTSO-E transmission outages (A78)** — `documentType=A78` per control area, planned and forced
    (`businessType`), the last 30 days and the next 30 (answers come zipped like A85; reuse
    `scripts/build_imbalance.py`'s zip handling). Daily step in `eu-days.yml`; card "Lines out of
    service" in the country panel (element, voltage, start, end, reason); lake `entsoe/transmission_outages`.

### E. Every wind turbine and solar farm worldwide

12. **Global Renewables Watch (Microsoft/Planet)** — GitHub releases of microsoft/global-renewables-watch
    (GeoPackages; check the licence in the probe). Newest quarter → PMTiles on R2
    (`grid/grw.pmtiles`, wind points and solar polygons, minzoom by size like `fetch_us_lines.py`);
    layer "Wind and solar seen from space" (group "Power plants", World); per-country counts and MW
    (as published) by quarter → `frontend/public/data/eu/grw_countries.json` for a card; lake `grw/*`.

### F. Country and state profiles (rows in the country report, no new layers)

13. **Eurostat energy balances (`nrg_bal_c`, CC BY 4.0)** — API (no key): final energy by sector and
    fuel, newest year. API only + catalogue file; a "Final energy use" section in `CountryReport.tsx`.
14. **EIA SEDS** — EIA API v2 `seds` (`EIA_API_KEY`): per state, consumption and production by
    source, newest year. API only + catalogue; rows in the US country report and the US state card.
15. **EIA STEO** — EIA API v2 `steo`: US electricity generation and price forecast, labelled
    "forecast". API only + catalogue; a small card in the US panel.
16. **Energy Institute Statistical Review** — the consolidated dataset (CSV/xlsx, free with
    attribution). Lake `ei_review/*`; primary energy by fuel since 1965 in the country report.
17. **EDGAR (JRC, CC BY 4.0)** — CO₂ and GHG per country and sector, the newest release (xlsx/CSV).
    Lake `edgar/*`; emissions by sector in the country report.

### G. Live markets beyond Europe and the US

18. **Japan, JEPX** — spot area prices, 30-minute (the CSV downloads on jepx.jp; check the terms of use
    in the probe). Daily in `eu-days.yml` → `jepx.json`; a Japan card in the World panel (area prices
    today, average, min, max per area); lake `jepx/spot`.
19. **Mexico, CENACE** — day-ahead local marginal prices (PML) by node, the public web service
    (`ws01.cenace.gob.mx`, no key; probe the URL pattern). Daily → `cenace.json` with per-system
    spreads like `us_nodes` (nodes counted, not placed unless CENACE publishes positions); a Mexico
    card; lake `cenace/pml`.
20. **India, Grid-India** — daily power supply position reports (grid-india.in). If only PDFs, stop
    and say so; if a table/CSV/JSON exists, daily → `india.json` (demand met, peak, generation by
    source as published); an India card.

### H. People and lights

21. **GHSL population (JRC, CC BY 4.0)** — GHS-POP, 2025 epoch, 30 arc-seconds (≈ 1 km) GeoTIFF.
    In Actions: sums per NUTS 3 and per admin-1 (computed zonal sums) → lake `ghsl/population`; a
    "People" row (and density) in the country report; a 0.1° grid of people per cell
    (`frontend/public/data/eu/population_grid.bin` or JSON, ≤ 5 MB, documented) read by
    "Check a site" for "people within the area" (sum of cells whose centre is inside, labelled with the
    cell size).
22. **NASA Black Marble (monthly night lights, VNP46A3)** — needs a NASA Earthdata login: if the probe
    confirms that, stop and list `NASA_EARTHDATA_TOKEN` with the sign-up URL
    (urs.earthdata.nasa.gov); do not build it.

## Done-check

`uv run ruff check . && uv run ruff format .`, `uv run pytest`, `cd frontend && npm run build`; merge
`origin/main` (brief 16 may have landed: keep both sides). PR: the checklist, the probe annotations
(one line per dataset), the new layers and cards, the session link.

Out of scope: the backend, the agent, alerts, redesigns of existing layers.
