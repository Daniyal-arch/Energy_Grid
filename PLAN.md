# InfraAtlas: plan

## Scope

An interactive, source-backed map of the world's power system, starting with Europe:
live figures, history, prices and infrastructure on one globe. Every number shown is
passthrough from a named source or computed in a build script and documented in
docs/DATA_SOURCES.md. It is a static site (frontend + JSON built by scripts). Data
APIs and an AI agent come next as Cloudflare Workers next to it.

The earlier Germany atlas is archived in the git tag `germany-atlas-final`.

## What exists

- **Live map** (Europe): grid, plants, gas, cross-border flows, wind, country cards
  (ENTSO-E, GIE AGSI+/ALSI, Ember, Open-Meteo).
- **24 hours:** a 30-day archive of real days, every 15 minutes, with wind.
- **Prices:** twelve months per bidding zone: hours below zero, price by time of day,
  solar and wind capture prices.
- **25 years:** Ember's yearly data for every country on the globe, 2000-2025.
- **World:** electricity access (World Bank), mapped data centres (OpenStreetMap),
  Australia's market live (AEMO).
- Data refresh: `eu-snapshot.yml` (every 30 min onto `eu-data`), `eu-days.yml`
  (daily onto `eu-days`).

## Next, in order

1. **World power plants** (Global Energy Monitor, Global Integrated Power tracker, CC BY
   4.0; the download needs a form). Every plant on the globe by fuel and status:
   operating, construction, planned, retired. Answers "what is the world building, and
   how fast is coal retiring?". Nuclear reactors are part of it.
2. **US live grid** (EIA-930, hourly per balancing authority, interchange between them;
   needs `EIA_API_KEY`).
3. **World transmission grid** (Gridfinder, CC BY 4.0, 725 MB download): high-voltage
   lines as vector tiles (PMTiles on Cloudflare R2, read with range requests).
4. **Smaller additions:** Ember monthly for the world; IEA hydrogen projects (IEA
   account); battery storage projects; more live grids (Brazil ONS, India Grid-India).

## Data APIs and the agent (Cloudflare)

The static files stay the source of the map. Next to them:

- **R2** (object storage): PMTiles for large geometry, Parquet for long time series.
- **D1** (SQLite): the same figures as tables (`prices`, `flows`, `generation`,
  `plants`, `access`), loaded by the build scripts, for queries the files cannot answer
  (any date range, any zone).
- **Data API Worker:** typed, read-only endpoints over D1/R2 with caching. The same
  endpoints are exposed as an **MCP server**, so Claude Desktop or any agent can use
  them: a product in itself (free tier, paid keys).
- **Agent Worker** ("Ask the map"):
  - Claude via the Anthropic API, with tools that call the data API (`query_prices`,
    `get_flows`, `country_profile`, `find_plants`), never free text for numbers.
  - Grounding rule: every number in an answer must come from a tool result; a check
    compares the numbers in the draft with the tool outputs before it is shown, and
    each answer lists its sources.
  - Streaming answers (SSE), prompt caching for the system prompt and tool
    definitions, per-IP rate limits, a cost budget per day, logs of every tool call.
  - Evals: a fixed set of questions with known answers from the data, run in CI;
    scores for correctness, citation coverage, latency and cost.
- Credentials needed then: `ANTHROPIC_API_KEY`, a Cloudflare API token (or
  `wrangler login`).

## Possible products

The map is the shop window. Paying use cases: clean, merged datasets (plants, grid,
flows, prices) as an API or MCP server; reports for grid-connection and siting; alerts
(negative prices, low storage) for traders and flexible loads.
