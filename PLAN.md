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
- **In the cloud now:** brief 16 (imbalance prices, US EV fast chargers, GB carbon intensity,
  Denmark every 5 minutes, the solar and wind atlases).

## Waiting on the owner (keys and approvals)

- **Anthropic API key** for the agent (console.anthropic.com), ideally with Claude Startups
  credits: needs a custom domain and an email on it (Cloudflare can register both).
- **AWS deploy role** for the backend (a template comes with brief 18), the R2 tokens of
  docs/AGENT.md section 10.
- **PJM** (`PJM_API_KEY`), **Alberta** (`AESO_API_KEY`), **South Korea** (`DATA_GO_KR_KEY`),
  **Turkey** (`EPIAS_USERNAME`, `EPIAS_PASSWORD`), **France RTE** (free key), **Finland**
  (`FINGRID_API_KEY`).
- **Downloads to approve:** Global Renewables Watch (GeoPackages, size from its probe), GHSL
  population (~0.3 GB at 1 km); the atlases in brief 16 if not approved there.

## The plan: four phases, run as parallel cloud briefs

Each phase is a set of briefs in `docs/tasks/`, one cloud session each, run in parallel where they
touch different files. The owner merges; the next phase starts when its inputs are on main.

### Phase 1: data the agent needs (now, with brief 16)

| Brief | What | Why |
|---|---|---|
| **17 Shapes, keys and the semantic catalogue** | `lake/shapes/`: countries, US states and counties, NUTS 0–3 (GISCO), European bidding-zone outlines, world admin-1 (geoBoundaries); a gazetteer (GeoNames ≥ 15,000 people); `agent/catalog/<dataset>.yaml` for every lake table and map file (grain, keys, units, joins, example queries with answers); topic views extended | the agent can shade any region by any key without handling geometry; the catalogue is what makes its SQL right |
| **18 Backend skeleton** | `backend/` FastAPI + DuckDB (read-only lake, SQL guard, limits), `/api/health`, `/api/sql` (internal), saved maps on R2, Docker image, deploy to AWS Lambda (function URL, streaming) by OIDC from Actions, Cloudflare route `/api/*`, tests | the one backend, small and stateless |

### Phase 2: the agent that draws (week 2)

| Brief | What |
|---|---|
| **19 Agent core** | the loop on the Claude API (tools of docs/AGENT.md section 3), MapSpec schema shared with the frontend, grounding check, SSE events, caps and logs, `agent/evals/` (40 questions + 10 maps) in CI |
| **20 Ask in the app** | an "Ask" tab in the context panel (SSE client, sources list), `map/agentLayers.ts` rendering MapSpec overlays with the app's palettes, legends in the existing key, "Explain this map", `?map=<id>` links, "Ask about this site" from Check a site |

### Phase 3: datasets, wave 5 (in parallel with phase 2)

Chosen for the agent's questions and the paid uses (site screening, history, alerts). Each follows
the API-or-Parquet rule (docs/DATA_LAKE.md): what an API answers fast stays an agent tool, the rest
goes to the lake.

| Brief | Datasets | Gives the agent |
|---|---|---|
| **21 US plant performance** | EIA-923 generation and fuel per plant (monthly), EPA eGRID, EPA GHGRP, through PUDL's public Parquet (queried in place) | capacity factors, CO₂ per MWh per plant, industrial emitters |
| **22 Germany congestion** | netztransparenz.de redispatch and curtailment (EinsMan), SMARD 15-min market data | where wind is curtailed and what redispatch costs |
| **23 The grid that is coming** | ENTSO-E TYNDP projects (lines, storage, with dates and costs), ENTSO-E transmission outages (A78/A79) | "which new lines reach this region", why flows and prices change |
| **24 Every wind turbine and solar farm worldwide** | Global Renewables Watch (Microsoft/Planet; download approval), with build quarters | renewables built per country and region over time, beyond GEM's thresholds |
| **25 Country and state profiles** | Eurostat energy balances, EIA SEDS and STEO, Energy Institute Statistical Review, EDGAR (API where they have one) | whole-energy context: heat, transport, industry, emissions by sector |
| **26 Live markets beyond Europe and the US** | Japan JEPX (area prices), Mexico CENACE (nodal), Grid-India, plus the keyed ones when keys arrive | the live globe and price maps in Asia and Latin America |
| **27 People and lights** | GHSL population grid (per admin-1 and NUTS 3), NASA Black Marble (monthly lights) | per-capita maps, electrification, outage detection after disasters |

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
