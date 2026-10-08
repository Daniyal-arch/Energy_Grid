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
- **World:** GEM power plants by status, OSM high-voltage lines (PMTiles on R2),
  Gridfinder's predicted grid, undersea power cables, data centres, electricity access,
  Ember's yearly and monthly data, live grids of the US (EIA-930), Brazil (ONS) and
  Australia (AEMO).
- Refresh: `eu-snapshot.yml` (every 30 min onto `eu-data`), `eu-days.yml` (daily onto
  `eu-days`), `world-hv.yml` and `world-grid.yml` (tiles onto R2, on demand).

## Data sources to add, one by one

Each one: a probe (`scripts/probe_*.py`), a fetch/build script, its file in
docs/DATA_SOURCES.md, a layer and/or panel card, and the workflow that refreshes it.
Credentials go in `.env` and `.env.example` (and the repo secrets for workflows).

### Global (first)

1. **Taiwan live grid** (Taipower open data, every generating unit every 10 min, load;
   no key). Live layer like US/Brazil/Australia, plus a card.
2. **Ontario live grid** (IESO public reports: demand, generation by fuel, intertie flows,
   prices; no key).
3. **Alberta live grid** (AESO API: supply and demand, pool price, interchange;
   `AESO_API_KEY`).
4. **South Korea** (KPX via data.go.kr: demand, regional solar and wind; `DATA_GO_KR_KEY`).
5. **Turkey** (EPİAŞ transparency platform: generation by source, prices;
   `EPIAS_USERNAME`, `EPIAS_PASSWORD`).
6. **Gas pipelines and LNG terminals worldwide** (GEM Global Gas Infrastructure Tracker,
   GeoJSON; the download needs a form). Routes by status, capacity, start year.
7. **Solar and wind resource maps** (Global Solar Atlas: irradiation; Global Wind Atlas:
   mean wind speed at 100 m; GeoTIFF, large downloads) as raster tiles on R2: "where is
   the resource".
8. **Weather worldwide** (ECMWF open data: wind at 100 m, surface radiation; GRIB2 every
   6 h) for wind particles and sunshine on the whole globe.
9. **Installed capacity per country** (IRENA renewable capacity statistics, yearly).
10. Later live grids: Japan (OCCTO and the nine area utilities), India (Grid-India),
    South Africa (Eskom data portal), Chile (Coordinador Eléctrico Nacional), Uruguay
    (ADME), New Zealand (Transpower/EMI).

### United States

1. **Interconnection queues** (LBNL "Queued Up": every project waiting to connect,
   by state, type, size and year; Excel, yearly).
2. **Every generator** (EIA-860M, monthly: operating, planned and retiring units of
   1 MW or more, with location).
3. **Transmission lines** (HIFLD: 69–765 kV with voltage) as vector tiles on R2.
4. **Wind turbines and solar farms** (USWTDB: every turbine; USPVDB: solar outlines).
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
