# InfraAtlas: plan

## Scope

An interactive, source-backed map of the world's power system, starting with Europe and the US:
live figures, history, prices and infrastructure on one globe, and an agent that answers
questions from the same data and draws its answers on the map. Every number shown is passthrough
from a named source or computed in a build script and documented in docs/DATA_SOURCES.md. The map
is a static site (frontend + JSON built by scripts; geometry as PMTiles on Cloudflare R2); the
full data sits in a Parquet lake on R2 (docs/DATA_LAKE.md); the agent is the one backend
(docs/AGENT.md).

The earlier Germany atlas is archived in the git tag `germany-atlas-final`.

## What exists (2026-10-18)

- **One map** (`frontend/src`): Layers panel, "colour countries by", search (places, plants,
  "lat, lon"), Live · 24 h · Years, a context panel in tabs, stories with shareable links, a phone
  layout. **Check a site** (right-click: nearest lines and substations, room to connect, plants,
  prices, water and outage risk; CSV) and a **country report** (printable, CSV, `?report=DE`).
- **Europe:** grid, plants, gas and its flows, cross-border power flows with capacity, prices to
  0.01 € and twelve months per zone, wind and sun, outages, output per plant through a day, a
  30-day archive every 15 minutes, LNG per terminal, CO₂ per ETS installation, grid capacity (GB
  TEC, NL capacity map, Spain nodes), retail prices, Germany's every unit (MaStR), offshore wind
  farm areas (EMODnet).
- **United States:** every generator (EIA-860M), lines from 100 kV, every wind turbine, every
  large solar array (USPVDB), the queue (LBNL and the markets' own), "A day in the US", hub and
  nodal day-ahead prices (six markets), fossil units hour by hour (EPA), outages per county
  (EAGLE-I), retail prices.
- **World:** GEM plants and fuel infrastructure, high-voltage lines (Overture), undersea cables,
  data centres, access, Ember and IRENA, Climate TRACE emitters, water risk (Aqueduct), live grids
  of Brazil, Australia, Taiwan and Ontario.
- **Lake:** ~1.9 GB Parquet on R2, 101 tables (`lake/_catalog.json`, `lake.duckdb` views).
- **Brief 16 (pull request):** imbalance prices per zone (card, lake history 2015–), GB carbon
  intensity and Denmark every 5 minutes (country cards), the solar and wind resource atlases
  (layers, "Check a site", COGs in the lake); US EV fast chargers built, waiting for a key.

## Waiting on the owner (keys and approvals)

- **Anthropic API key** for the agent (console.anthropic.com), ideally with Claude Startups
  credits: needs a custom domain and an email on it (Cloudflare can register both).
- **Cloudflare Workers Paid plan** ($5 a month; the backend runs as a Cloudflare Container) and
  the token rights and R2 tokens of docs/AGENT.md section 10.
- **PJM** (`PJM_API_KEY`), **Alberta** (`AESO_API_KEY`), **South Korea** (`DATA_GO_KR_KEY`),
  **Turkey** (`EPIAS_USERNAME`, `EPIAS_PASSWORD`), **France RTE** (free key), **Finland**
  (`FINGRID_API_KEY`).
- **NYISO** nodal prices: its site answers automated downloads with a bot check (HTTP 202); no
  key fixes it, a route the owner approves does.
- **NREL** (`NREL_API_KEY`, an api.data.gov key from https://developer.nrel.gov/signup/) as a
  repo secret: the US EV fast chargers (brief 16 B) are built and wait for it. The repo secret
  `EPA_API_KEY` reached the workflow empty on 2026-10-18 (brief 17 counts on it too).
- **Downloads to approve:** Global Renewables Watch (GeoPackages, size from its probe), GHSL
  population (~0.3 GB at 1 km). (The atlases of brief 16 were approved and are built.)

## The plan: four phases, run as parallel cloud briefs

Each phase is a set of briefs in `docs/tasks/`, one cloud session each, run in parallel where they
touch different files. The owner merges; the next phase starts when its inputs are on main.

### Phase 1: data (one cloud session) and the backend

| Brief | What |
|---|---|
| **16** (pull request) | ✅ imbalance prices, ✅ GB carbon intensity, ✅ Denmark every 5 minutes, ✅ solar and wind atlases; US EV fast chargers wait for `NREL_API_KEY` |
| **17 Datasets wave 5** ([17-datasets-wave5.md](docs/tasks/17-datasets-wave5.md)) | 22 datasets in one session: NUTS 0–3, bidding-zone outlines, world admin-1, GeoNames cities; EIA-923, eGRID, GHGRP; netztransparenz redispatch and curtailment, SMARD; TYNDP projects, ENTSO-E transmission outages; Global Renewables Watch; Eurostat balances, EIA SEDS, EIA STEO, Energy Institute review, EDGAR; JEPX, CENACE, Grid-India; GHSL population, NASA Black Marble |
| **18 Backend skeleton** | `backend/` FastAPI + DuckDB (read-only lake, SQL guard, limits), saved maps on R2; hosting chosen by the owner (docs/AGENT.md §2) |

### Phase 1b: datasets wave 6 (after wave 5 merges)

| Brief | What |
|---|---|
| **21 Datasets wave 6** ([21-datasets-wave6.md](docs/tasks/21-datasets-wave6.md)) | 24 datasets: room to connect in France, Italy, Belgium, Portugal, Ireland, Poland; substations worldwide, German grid operators, US utility territories, sea cables and pipelines; protected areas, flood hazard, major roads and rail; hydrogen projects, auction results, technology costs, planned gas projects, GHG inventories; OE-417 disturbances, FERC 714 demand; France and Spain regional mix, New Zealand and South Africa live |

### Phase 2: the agent that draws

| Brief | What |
|---|---|
| **19 Agent core** | the loop on the Claude API (tools of docs/AGENT.md §3), the semantic catalogue completed, MapSpec schema shared with the frontend, grounding check, SSE events, caps and logs, `agent/evals/` in CI |
| **20 Ask in the app** | an "Ask" tab in the context panel, `map/agentLayers.ts` rendering MapSpec overlays with the app's palettes, legends in the existing key, "Explain this map", `?map=<id>` links, "Ask about this area" from the site analysis |

### Phase 4: products on top (after phase 2)

- **Alerts:** a daily and live job writes events (negative day-ahead hours tomorrow, large forced
  outages, storage below the seasonal range, big queue changes) to a feed (JSON and RSS) with an
  agent-written summary; email later.
- **Maps to stories and videos:** a saved agent map becomes a story; the recorder
  (docs/VIDEO.md) renders it for LinkedIn from the same spec.
- **MCP server:** the agent's tools for Claude Code, Claude Desktop and other agents.
- **Accounts and exports** when a paid tier starts (saved maps, site lists, CSV of any view).

## Rules that do not change

CLAUDE.md's hard rules and working rules: every number sourced; probe before building; heavy
downloads in Actions; calm maps with the grid as the hero; one Layers panel and one context
panel; the data branches belong to the workflows; small commits, ruff, pytest and the build
before a PR.

The full catalogue of candidate datasets is in [docs/DATASETS.md](docs/DATASETS.md).
