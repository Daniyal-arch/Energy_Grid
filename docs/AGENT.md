# Ask InfraAtlas: the agent and its backend

The agent answers questions about the power system from InfraAtlas's own data and **draws its
answer on the map**: it can switch the app's layers, move the camera, select a place, and add its
own layers built from a query (points, lines, shaded countries, states, counties or zones), each
with a legend and its sources. Every number in an answer comes from a tool result; every map it
makes is a link that opens the same view. Design for the phases in PLAN.md; the briefs in
docs/tasks/ build it.

## 1. What it does (the first version)

- **Answer:** "Which German states added the most solar in 2025?", "Hours below zero in NL this
  year vs last", "How much is waiting to connect in Texas, by type?", "Where in Spain can a 50 MW
  load still connect near a 400 kV substation?"
- **Map:** the same questions return a map: the states shaded by MW added, the zones by negative
  hours, the queue as stacked columns, the Spanish nodes as dots sized by free capacity.
- **Explain the view:** "Explain this map" sends the current view (the URL state) and the
  figures behind it; the agent explains what is on screen and what stands out.
- **Site questions:** "Is 52.37 N, 4.90 E a good place for a data centre?" runs the same figures as
  "Check a site" and adds the comparison.
- **Share:** each answer with a map gets a link (`?map=<id>`); saved maps can become stories.

Out of the first version: accounts, alerts, write access, anything the data cannot answer (the agent
says what is missing and which dataset would answer it).

## 2. Architecture

```
browser (React app)                      backend (FastAPI, Python 3.12)               data
-----------------------------------     ------------------------------------------   ---------------------------
context panel, tab "Ask"   --SSE-->      /api/ask  (agent loop, Claude API)  ------>  lake on R2 (Parquet, DuckDB)
map/agentLayers.ts  <-- MapSpec --       tools: catalog, sql, places, live,          map files (eu-data, eu-days,
?map=<id>  ---------------------->       site, make_map, make_chart                   bundled JSON)
                                         /api/maps/<id> (saved MapSpecs on R2)       live APIs (API-or-Parquet rule)
```

- **Backend:** one FastAPI app in `backend/` (Python 3.12, `uv`, ruff, pytest), DuckDB with
  `httpfs` and `spatial`. Stateless; conversation history is sent by the browser each turn.
- **Hosting:** AWS Lambda (container image, AWS Lambda Web Adapter, a function URL with response
  streaming for SSE), deployed by GitHub Actions through an OIDC role. AWS-native compute is
  paid by the owner's AWS credits ($120 until 2027-10-13; Claude itself is not, see memory
  "bedrock-route-dropped"). Cloudflare routes `/api/*` on the site's domain to the function URL
  (same origin, no CORS) and applies a per-IP rate-limiting rule.
- **Model:** Claude through the Anthropic API (first-party key `ANTHROPIC_API_KEY`), funded by the
  Claude Startups credits once granted, else pay-as-you-go under the caps of section 7. Default
  `claude-opus-5-5` ($4 / $20 per million input / output tokens, cache reads $0.20; 1M context)
  at effort `medium`; `claude-sonnet-5-5` ($2 / $10) is the owner's choice if cost requires it.
  One model per conversation (caches are per model).
- **State:** saved MapSpecs and usage logs on R2 (`agent/maps/<id>.json`,
  `agent/logs/<date>.jsonl`); the daily spend counter in a small DynamoDB table (AWS credits).

## 3. Tools (what the model can call)

All tools are read-only. Inputs are JSON-schema validated (`strict: true`); every result carries
`sources` (dataset, table, licence, retrieved) that the answer must cite.

| Tool | Does | Limits |
|---|---|---|
| `search_catalog(query)` | finds datasets, tables, columns, units, keys and map layers that answer a question, from the semantic catalogue (section 4) | top 10 matches |
| `describe_table(name)` | columns with types and units, grain, keys, time range, row count, licence, 5 sample rows, example queries | |
| `run_sql(sql)` | DuckDB over the lake's views (`lake.duckdb`) and the map files registered as views | SELECT only (parsed and checked); 25 s; 2 GB memory; external access limited to R2 and the app's public files; ≤ 2,000 rows returned (the full result stays server-side under a `result_id` for maps); licensed GEM tables only in aggregates |
| `find_place(text)` | a country, US state or county, NUTS region, bidding zone, city (gazetteer) or coordinates → codes, centre, bbox | our outlines and the gazetteer only |
| `site_figures(lon, lat)` | the "Check a site" figures computed server-side (nearest lines, substations, capacity, plants within 50 km, prices, water risk, outages) | the same sources and rules as the panel |
| `live(source, params)` | allow-listed live reads where the API-or-Parquet rule says API (ENTSO-E newest interval, EIA-930, GIE, Ember, the markets via gridstatus) | per-source rate limits; cached 10 min |
| `make_map(spec)` | validates a MapSpec (section 5) and sends it to the browser; returns the map id | data by `result_id` or inline ≤ 5,000 features |
| `make_chart(spec)` | a small line/bar/stacked chart for the panel (same encoding rules) | ≤ 2 series of ≤ 2,000 points inline |

Every number the answer states must appear in a tool result of this turn; a check after the turn
compares the numbers in the text with the tool results and marks any it cannot find.

## 4. The semantic catalogue (what makes the agent good)

`lake/_catalog.json` lists files and columns; the agent also needs meaning. One YAML per dataset
in `agent/catalog/<dataset>.yaml`, kept next to the code that builds the dataset and checked by a
test (every lake table and every map file has an entry):

```yaml
dataset: eaglei
title: US power outages per county (ORNL EAGLE-I)
licence: CC BY 4.0
tables:
  outages:
    grain: one row per county and 15-minute interval with customers out
    keys: {fips: US county (5-digit FIPS) -> shapes.us_counties, ts: UTC interval start}
    measures: {customers_out: {unit: customers, how: as published}}
    time: 2014-11 to 2025-12
    joins: [shapes.us_counties on fips]
    examples:
      - q: customer-hours without power in Harris County, 2024
        sql: SELECT sum(customers_out) * 0.25 FROM eaglei.outages WHERE fips = '48201' AND ts >= '2024-01-01' AND ts < '2025-01-01'
        answer: 176042304.25 customer-hours
```

The examples double as the evaluation set (section 8). Map layers (`LAYERS` in
`frontend/src/app/store.ts`) and the map files (docs/DATA_SOURCES.md) get entries too, so the agent
can switch on an existing layer instead of rebuilding it.

**Shapes and keys** (lake `shapes/`, GeoParquet): countries (ISO 2/3), US states, US counties,
NUTS 0–3 (Eurostat GISCO), European bidding zones, world admin-1 (geoBoundaries), plus a gazetteer
(GeoNames cities ≥ 15,000 people). A query that returns a key column can be shaded on the map
without the model handling any geometry.

## 5. MapSpec: how the agent draws

A MapSpec is plain JSON, validated against a schema shared by backend and frontend
(`backend/agent/mapspec.py` and `frontend/src/lib/mapspec.ts`, generated from one JSON Schema):

```json
{
  "title": "Solar added in 2025 by German state",
  "camera": {"preset": "europe"} ,
  "app": {"layers": ["gridEU"], "colour": "none", "mode": "live", "selection": null},
  "overlays": [
    {
      "id": "solar_2025",
      "kind": "choropleth",
      "data": {"result_id": "r_7f3a", "key": "admin1", "shapes": "nuts1"},
      "value": {"column": "mw_added", "unit": "MW", "scale": "sequential", "palette": "solar"},
      "legend": {"title": "Solar added in 2025", "how": "sum of units commissioned in 2025"},
      "tooltip": ["name", "mw_added", "units"],
      "source": "Marktstammdatenregister snapshot 2026-10-13"
    }
  ],
  "notes": "Units of 1 MW and more counted individually; smaller ones summed per municipality."
}
```

- **Kinds:** `points` (size and colour by columns), `lines` (from geometry or from/to pairs),
  `arcs` (flows between places), `choropleth` (by key on a shapes table), `columns` (3-D bars),
  `labels`. Data comes from a `result_id` (the server keeps the full query result) or inline.
- **Style comes from the app, never from the model:** the model picks a scale (`sequential`,
  `diverging`, `categorical`) and a named palette from the app's own (`app/colors.ts`); sizes
  and widths are bounded. Calm by construction: no blinking, no free colours, one overlay legend
  in the existing key.
- **Existing layers first:** when an app layer already shows the answer (plants, queue, prices,
  outages, water), the spec switches it on and frames it rather than redrawing it.
- **Rendering:** `frontend/src/map/agentLayers.ts` turns overlays into deck.gl layers;
  `MapLegend` shows their legend and source; the "Ask" tab lists the sources of the answer.
- **Saved maps:** `/api/maps` stores the spec and its result data on R2; `?map=<id>` opens it for
  anyone; the owner can promote one to a story (later: the recorder renders it for LinkedIn).

## 6. The loop

- Claude API with user-defined tools; the SDK's tool runner (`client.beta.messages.tool_runner`)
  drives the loop, with per-turn hooks for logging, the step limit and the spend check; streamed
  (`messages.stream`) so text, tool progress and the MapSpec reach the browser as SSE events
  (`text`, `tool`, `map`, `chart`, `sources`, `done`, `error`). A hand-written loop replaces the
  runner only if its hooks cannot carry the SSE events.
- **Prompt caching:** tools and system prompt are frozen and ordered (tool list sorted, no dates
  in the system prompt) with a cache breakpoint at the end of the system prompt; the volatile
  parts (today's date, the current view, the question) come after it. Check
  `usage.cache_read_input_tokens` in the logs.
- **System prompt:** the house rules (every number from a tool, cite sources, say what is
  missing, prefer existing layers, calm maps, the units and precision rules of CLAUDE.md), the
  catalogue's dataset list (titles and one line each), the MapSpec schema.
- **Refusals:** check `stop_reason` before reading content; server-side fallback as the SDK
  documents for the chosen model.
- **Limits per question:** at most 12 tool calls, 25 s per SQL query, a task budget, and the
  answer streams within about 60 s or stops with what it has.

## 7. Cost, abuse and safety

- Caps: per IP (Cloudflare rule plus a per-IP daily count), a global daily spend cap from
  `usage` tokens × price (the counter in DynamoDB); over the cap the Ask tab says so.
- Planning figure (an estimate, not shown in the app): with caching, a typical question reads
  20–40 k tokens (mostly cached) and writes 1–3 k, roughly $0.03–0.10 on Opus 5.5.
- Read-only everywhere: the R2 token can only read `lake/`; DuckDB runs with external access
  limited to R2 and the app's public files and with its configuration locked; no tool writes
  except `make_map` (to `agent/maps/`).
- Rows from sources are data, never instructions (prompt injection through data has nothing to
  write to). Licensed GEM rows only in aggregates.
- Logs: question, tool calls, SQL, tokens, cost, latency; no personal data; 90 days.

## 8. Evaluation

- `agent/evals/questions.yaml`: about 40 questions with known answers taken from the catalogue
  examples and DATA_SOURCES (EAGLE-I Harris County, MaStR solar per Land, LBNL queue per state,
  ENTSO-E negative hours per zone, ETS totals, ...), plus 10 map questions with the expected
  overlay kind and key.
- Checks: answer correctness (number within the source's precision), every number grounded, sources
  listed, MapSpec valid, latency and cost per question.
- Runs in Actions on PRs that touch `backend/agent/` or `agent/` (a 10-question sample, cost
  capped), the full set weekly.

## 9. Also exposed as an MCP server (later)

The same tools behind an MCP endpoint (`/mcp`, read-only, key-protected) so Claude Code, Claude
Desktop or other agents can query InfraAtlas's data directly. Same limits and logs.

## 10. Keys and accounts the owner provides

| What | Where | Used by |
|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com (Claude Startups programme credits when granted) | backend (Lambda env, from a GitHub secret) |
| R2 read-only token for `infraatlas-raw/lake/`, read-write for `agent/` | Cloudflare dashboard → R2 → API tokens | backend |
| AWS role for deploys (GitHub OIDC), Lambda, DynamoDB | the AWS account with the credits; a template in `backend/deploy/` | deploy workflow |
| Cloudflare route `/api/*` and a rate-limiting rule | Cloudflare dashboard (or the deploy workflow with the existing API token) | site |
