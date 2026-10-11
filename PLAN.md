# InfraAtlas: plan

## Scope

An interactive, source-backed map of the world's power system, starting with Europe:
live figures, history, prices and infrastructure on one globe. Every number shown is
passthrough from a named source or computed in a build script and documented in
docs/DATA_SOURCES.md. It is a static site (frontend + JSON built by scripts); large
geometry lives as PMTiles on Cloudflare R2. A data API and an AI agent come later.

The earlier Germany atlas is archived in the git tag `germany-atlas-final`.

## What exists

- **One map** (`frontend/src/ui`, `frontend/src/map`): a Layers panel (on/off, coverage,
  legend), "colour countries by", search, a time control (Live · 24 h · Years), a
  context panel in tabs, Stories with shareable links, a phone layout. Europe live is
  the default. `?capture=16x9` still opens the earlier single view for video recording.
- **Europe:** grid, plants, gas, cross-border flows, wind and sunshine, outages, a
  30-day archive every 15 minutes, twelve months of prices per zone, LNG and storage
  (ENTSO-E, Elexon, GIE, Ember, Open-Meteo, powerplantmatching, SciGRID_gas).
- **United States:** every generator of 1 MW and more (EIA-860M, monthly; replaces GEM in
  the US while on), transmission lines from 100 kV (OpenStreetMap via Overture, PMTiles on
  R2), every wind turbine (USWTDB), the interconnection queue raised per state (LBNL Queued
  Up), a US panel and the stories "US grid" and "US interconnection queue".
- **World:** GEM power plants by status, OSM high-voltage lines (PMTiles on R2),
  Gridfinder's predicted grid, undersea power cables, data centres, electricity access,
  Ember's yearly and monthly data, live grids of the US (EIA-930), Brazil (ONS) and
  Australia (AEMO).
- **Added 2026-10-11:** Europe's gas flows (ENTSOG), output per plant through a day
  (ENTSO-E per unit + JRC), installed capacity from ENTSO-E, border capacity on the flow
  arrows, wind and solar forecast vs actual, prices to 0.01 €; "A day in the US" (EIA-930),
  US day-ahead prices at six trading hubs, US fossil units hour by hour (EPA CAMPD).
  Stories in sections (Europe, United States, World); Live · Years (the day replays are
  stories).
- Refresh: `eu-snapshot.yml` (every 30 min onto `eu-data`), `eu-days.yml` (daily onto
  `eu-days`), `world-hv.yml` and `world-grid.yml` (tiles onto R2, on demand), `us-grid.yml`
  (US data monthly onto main, US line tiles quarterly onto R2).
- Known gap: `grid/world-hv.pmtiles` holds no lines in the Americas (its `na` and `sa` jobs
  did not finish; the tiles' bounds start at 22.5° W). The US has its own lines layer.

## Waiting on the owner (keys and approvals)

- **PJM** (`PJM_API_KEY`): Western Hub price for the Mid-Atlantic region. Needs a PJM Tools
  account, then apiportal.pjm.com → Data Miner 2 → Primary key (the portal did not resolve
  from the owner's network on 2026-10-11: try a hotspot or DNS 1.1.1.1). Add it as a cloud
  network secret (`Ocp-Apim-Subscription-Key` on `api.pjm.com`) and a GitHub secret; no code
  change needed.
- **Alberta** (`AESO_API_KEY`), **South Korea** (`DATA_GO_KR_KEY`), **Turkey**
  (`EPIAS_USERNAME`, `EPIAS_PASSWORD`): global live grids 3–5 below.
- **Downloads to approve:** Global Solar Atlas PVOUT (~362 MB), Global Wind Atlas (several GB),
  both in GitHub Actions.

## Next

1. **Check the new daily steps** (eu-days: plant output, US days, US prices, EPA) after the
   next morning run; fix what fails.
2. **Cloud wave 2** (briefs in `docs/tasks/`): Climate TRACE emissions per facility
   (worldwide), the rest of the world high-voltage grid from Overture in Actions, EU CO₂ per
   installation (EU ETS) with LNG send-out per terminal (GIE ALSI, `AGSI_API_KEY`).
3. **Product:** downloads (CSV of what a view shows), a country report page, then the agent.
4. **Videos:** "A day in the US", gas flows into Europe, plants through a day.

## Data sources to add, one by one

Each one: a probe (`scripts/probe_*.py`), a fetch/build script, its file in
docs/DATA_SOURCES.md, a layer and/or panel card, and the workflow that refreshes it.
Credentials go in `.env` and `.env.example` (and the repo secrets for workflows).

### Global (first)

1. ✅ **Taiwan live grid** (Taipower open data, every generating unit every 10 min, load;
   no key). Live layer like US/Brazil/Australia, plus a card.
2. ✅ **Ontario live grid** (IESO public reports: demand, generation by fuel, intertie flows,
   prices; no key).
3. **Alberta live grid** (AESO API: supply and demand, pool price, interchange;
   `AESO_API_KEY`).
4. **South Korea** (KPX via data.go.kr: demand, regional solar and wind; `DATA_GO_KR_KEY`).
5. **Turkey** (EPİAŞ transparency platform: generation by source, prices;
   `EPIAS_USERNAME`, `EPIAS_PASSWORD`).
6. **GEM trackers beyond power plants** (Global Energy Monitor; each download needs the form;
   files in `data/world/`, gitignored). Power plants of every fuel are already in the
   Integrated Power Tracker.
   - Fuel infrastructure layer: gas pipelines + LNG terminals (GGIT), oil/NGL pipelines
     (GOIT), coal terminals.
   - Fuel supply layer: oil and gas extraction fields (GOGET), coal mines.
   - Industry layer (large electricity users): iron and steel, cement and concrete,
     chemicals, iron ore mines.
   - Panels and the agent: energy ownership (who owns each asset), coal and gas project
     finance, methane emitters.
7. **Solar and wind resource maps** (Global Solar Atlas: irradiation; Global Wind Atlas:
   mean wind speed at 100 m; GeoTIFF, large downloads) as raster tiles on R2: "where is
   the resource".
8. ✅ **Weather worldwide** (ECMWF open data: wind at 100 m, surface radiation; GRIB2 every
   6 h) for wind particles and sunshine on the whole globe.
9. ✅ **Installed capacity per country** (IRENA renewable capacity statistics, yearly).
10. Later live grids: Japan (OCCTO and the nine area utilities), India (Grid-India),
    South Africa (Eskom data portal), Chile (Coordinador Eléctrico Nacional), Uruguay
    (ADME), New Zealand (Transpower/EMI).

### United States

1. ✅ **Interconnection queues** (LBNL "Queued Up": every project waiting to connect,
   by state, type, size and year; Excel, yearly).
2. ✅ **Every generator** (EIA-860M, monthly: operating, planned and retiring units of
   1 MW or more, with location).
3. ✅ **Transmission lines** as vector tiles on R2: OpenStreetMap from 100 kV through
   Overture (HIFLD's layer is no longer public since 2025).
4. ✅ **Wind turbines** (USWTDB: every turbine). Still to do: solar farm outlines (USPVDB).
5. **Hourly CO₂ per power plant** (EPA CAMPD API; `EPA_API_KEY`).
6. **EV chargers** (NREL AFDC station locator; `NREL_API_KEY`).
7. **Power outages per county** (ORNL EAGLE-I, every 15 min, yearly releases).
8. **Wholesale prices by node/zone** (ISO data: ERCOT, CAISO, NYISO, MISO, SPP, ISO-NE).

### Europe

1. **Gas flows at every border point** (ENTSOG transparency API): a gas version of the
   power-flow map.
2. **Denmark every 5 minutes** (Energinet Energi Data Service: CO₂ intensity, prices,
   production).
3. **Finland every 3 minutes** (Fingrid open data; `FINGRID_API_KEY`).
4. **Great Britain** (NESO data portal: carbon-intensity forecast, the grid connection
   queue).
5. **Offshore wind farms and sea cables** (EMODnet Human Activities).
6. **More ENTSO-E series:** imbalance prices, day-ahead wind and solar forecasts,
   cross-border capacities, installed capacity per unit (replaces Energy-Charts).
7. **Retail electricity prices** (Eurostat, households and industry) and **emissions
   per installation** (EU ETS, EUTL).

## The agent (after the datasets)

- FastAPI + LangGraph, traced with Langfuse; a free LLM to start (Groq Llama 3.3 70B,
  Gemini Flash as fallback) behind a provider adapter.
- Data as Parquet on R2, queried with DuckDB; a small Postgres (Neon) only for app state
  (users, saved views, conversations).
- Tools over the data (`query_prices`, `get_flows`, `country_profile`, `find_plants`),
  also exposed as an MCP server. Grounding: every number in an answer comes from a tool
  result and is checked against it; each answer lists its sources.
- Evals in CI: fixed questions with known answers; correctness, citation coverage,
  latency, cost.
- Keys then: `GROQ_API_KEY`, `GOOGLE_API_KEY`, `LANGFUSE_*`, `DATABASE_URL`.

## Possible products

The map is the shop window. Paying use cases: history and exports (CSV/API), alerts
(negative prices, outages, low storage), queue and plant-pipeline layers, country
reports, and site screening for data centres and developers (grid distance, resource,
queue congestion, prices).
