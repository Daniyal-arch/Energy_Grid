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

Decided 2026-10-27 (replaces the Cloudflare Containers plan of 2026-10-18); built by brief 25
(`docs/tasks/25-agent-backend.md`).

```
browser (React app)                 Cloudflare Worker          AWS Lambda (container, streamed)                data
--------------------------------    -----------------          ---------------------------------------------   ---------------------------
context panel, tab "Ask" --SSE-->   /api/*, /mcp on the  --->  FastAPI: data service + /api/ask + /mcp   --->   lake on R2 (Parquet, DuckDB)
map/agentLayers.ts <-- MapSpec --   site's domain              LangGraph agent, tools, skills                  map files (eu-data, eu-days,
?map=<id> ---------------------->   (rate limit, secret)       OpenTelemetry + Langfuse, CloudWatch            bundled JSON)
                                                               DynamoDB counters, SSM secrets                  live APIs (API-or-Parquet rule)
                                                               saved maps and run records on R2 agent/
```

- **Backend:** one FastAPI app in `backend/` (Python 3.12, its own uv project, ruff, pytest),
  DuckDB with `httpfs` and `spatial`. Two faces: the **data service** (catalogue, places, "Check a
  site" figures, saved maps; usable by the app without the agent) and the **agent**
  (`/api/ask`, Server-Sent Events). Stateless; the browser sends the conversation each turn.
- **Orchestration: LangGraph** (section 6), LangChain core message and tool types.
- **Any model:** `init_chat_model("<provider>:<model>")` with a registry in `agent/models.yaml`
  (prices, context, tool calling, caching). Default Claude through the Anthropic API
  (`ANTHROPIC_API_KEY`; Claude Startups credits once granted): `claude-opus-5-5` for the analyst,
  `claude-haiku-5-5` for the router and the cartographer; OpenAI, Google, Bedrock (non-Claude
  models, paid by AWS credits) and local models by configuration. One model per conversation
  (caches are per model).
- **Hosting: AWS Lambda.** A container image in ECR with the AWS Lambda Web Adapter in
  response-streaming mode behind a Function URL (`RESPONSE_STREAM`); AWS SAM; secrets in SSM
  Parameter Store; DynamoDB for the per-IP limit and the daily spend counter; CloudWatch logs,
  metrics, dashboard and alarms; deployed by GitHub Actions with OIDC. AWS credits pay for the
  compute; they do not pay for Claude (decision of 2026-10-18). A small Cloudflare Worker routes
  `/api/*` and `/mcp` from the site's domain (same origin, first rate limit, a shared secret
  header).
- **State:** saved MapSpecs and run records on R2 (`agent/maps/<id>.json`,
  `agent/logs/<date>/<trace>.json`); counters in DynamoDB.
- **Traceability:** OpenTelemetry spans (GenAI semantic conventions) and Langfuse traces per
  question: graph nodes, model calls with tokens and cost, tool calls, SQL.

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

The map's own datasets, as the user sees them, are in `frontend/src/app/datasets.json` (the
Datasets panel, the dashboards and the data catalogue read it): one entry per kind of data with
its category, the map layers that hold it per region (`where`: ISO codes or World, Europe, EU,
US), what each shows, the source, the update cadence, the `docs/DATA_SOURCES.md` section and the
coverage registry family (`data/coverage.yaml`, per-country status for EU-27, the UK and the US).
`make_map` turns a dataset id into its layers; `search_catalog` searches these entries too.

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

- **Styles (2026-10-29):** twelve flat (`dots`, `bubbles`, `choropleth`, `hexbin`, `grid`,
  `heatmap`, `contour`, `lines`, `flows`, `labels`, `bivariate`, `pies`) and ten in 3D
  (`columns`, `beams`, `spikes`, `lollipops`, `hex_columns`, `grid_columns`, `prisms`,
  `arcs_3d`, `terrain`, `point_cloud`), drawn by `frontend/src/map/agentLayers.ts`. Encodings:
  `value` (scale, palette), `value2` (bivariate), `size`, `category` (type colours), `radius_km`
  (bins), `label`. Data comes from a `result_id` (the server keeps the full query result) or
  inline.
- **One map or several:** `overlays` (one map, up to four) or `panels` (2-6 maps of the same
  place side by side in the Maps view, one camera, one variable or theme each). `replaces`
  names a map on screen the spec changes (an edit).
- **Who designs:** the analyst queries; the cartographer (fast model) picks the style and the
  layout from the question and the data (`backend/agent/prompts/cartographer.md`). An edit
  ("make it 3D", "split it into two maps") goes from the router straight to the cartographer
  with the maps on screen, whose data comes back from the saved maps.
- **Style comes from the app, never from the model:** the model picks a scale (`sequential`,
  `diverging`, `categorical`) and a named palette from the app's own (`app/colors.ts`); sizes
  and widths are bounded. Calm by construction: no blinking, no free colours, one overlay legend
  in the existing key.
- **Existing layers first:** when an app layer already shows the answer (plants, queue, prices,
  outages, water), the spec switches it on and frames it rather than redrawing it.
- **Rendering:** `frontend/src/map/agentLayers.ts` turns overlays into deck.gl layers; the
  "Ask" tab (`frontend/src/ui/AskTab.tsx`, store `frontend/src/app/agent.ts`) streams the answer
  with its tool steps, map cards (key, how, source), charts and sources; panels open in the Maps
  view with their keys.
- **Saved maps:** `/api/maps` stores the spec and its result data on R2; `?map=<id>` opens it for
  anyone; the owner can promote one to a story (later: the recorder renders it for LinkedIn).

## 6. The loop (LangGraph)

- **Graph:** `guard` (caps, input size) → `router` (fast model: the kind of answer and the
  specialists it needs) → `analyst` (main model: tools and skills, at most 12 tool calls) →
  `cartographer` (fast model, only for maps and charts: a MapSpec from result ids, validated) →
  `grounding` (deterministic number check, one repair round) → `finish` (sources, cost, trace
  id). The analyst answers most questions alone; parallel analyst runs (`Send`) for comparisons
  only where the evals show a gain.
- **Skills:** `agent/skills/<name>/SKILL.md` (Agent Skills format). The system prompt lists names
  and descriptions; the model loads a skill's body and references with tools when it needs them,
  so any model can use them.
- **Streaming:** `graph.astream` (messages, updates and custom events) becomes the SSE events
  `text`, `tool`, `map`, `chart`, `sources`, `done`, `error`, with a heartbeat.
- **Prompt caching:** tools and system prompt frozen and ordered (tool list sorted, no dates in
  the system prompt), a cache breakpoint after them for providers that take one (Anthropic);
  the volatile parts (today's date, the current view, the question) come after it. Cached tokens
  are in the traces.
- **System prompt:** the house rules (every number from a tool, cite sources, say what is
  missing, prefer existing layers, calm maps, the units and precision rules of CLAUDE.md), the
  catalogue's dataset list (titles and one line each), the MapSpec schema, the skill index.
- **Refusals and stop reasons:** handled per provider before reading content.
- **Limits per question:** at most 12 tool calls, 25 s per SQL query, a token budget, and the
  answer streams within about 60 s or stops with what it has.

## 7. Cost, abuse and safety

- Caps: per IP (the Worker's rate-limiting binding plus a per-IP count in DynamoDB), a global
  daily spend cap from `usage` tokens × the registry's prices (an atomic DynamoDB counter); over
  the cap the Ask tab says so.
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

## 9. MCP

- **Server:** the same tools at `/mcp` (streamable HTTP, the official `mcp` Python SDK), read-only
  and key-protected (`MCP_API_KEYS`), so Claude Code, Claude Desktop or other agents can query
  InfraAtlas's data directly. Same limits and logs.
- **Client:** external MCP servers listed in `agent/mcp.yaml` become tools of the agent through
  `langchain-mcp-adapters` (none by default).

## 10. Keys and accounts the owner provides

The full table, with where to register, is in `docs/tasks/25-agent-backend.md`.

| What | Where | Used by |
|---|---|---|
| `ANTHROPIC_API_KEY` (other providers optional) | console.anthropic.com (Claude Startups programme credits when granted) | backend (SSM) |
| AWS account, region, GitHub OIDC deploy role (`AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`) | aws.amazon.com, IAM | deploy workflow |
| R2 read-only token for `infraatlas-raw/lake/`, read-write for `agent/` | Cloudflare dashboard → R2 → API tokens | backend (SSM) |
| Langfuse keys | cloud.langfuse.com or self-hosted | backend (SSM) |
| `ADMIN_API_KEY`, `MCP_API_KEYS`, `PROXY_SECRET` | generated by the owner | backend (SSM), Worker |
| `CLOUDFLARE_API_TOKEN` with Workers Scripts edit (extend the existing secret) | Cloudflare dashboard → My Profile → API Tokens | the Worker in the deploy workflow |

## 11. As built (brief 25, 2026-10-27)

`backend/` (its own uv project; how to run, test and deploy: `backend/README.md`).

- **Service** (`backend/app/`): FastAPI; settings from the environment, then SSM in Lambda
  (`app/settings.py`); request ids, W3C trace context, JSON logs; CORS for the site origin and
  `http://localhost:5173`. Data routes without the agent: catalogue search and entries, places,
  site figures, saved maps, admin SQL; every response carries `sources`.
- **Data** (`backend/data/`): one DuckDB connection per container. The lake's `lake.duckdb`
  attached read-only as catalog `lake` (default, so `registers.gb` works as written); the app's
  map rows as `app.eu_plants`, `app.eu_substations`, `app.eu_prices`, `app.world_plants`,
  `app.us_plants`. Then locked: extensions from the image, no persistent secrets, external access
  only to the allowed directories (the lake prefix, the public map files, the CA bundle),
  configuration locked. The SQL guard (`data/guard.py`, sqlglot) is the first wall; DuckDB's
  lockdown the second. Results kept under `result_id` (100,000 rows), 2,000 shown to the model.
- **Tools** (`backend/tools/`): the table of section 3, plus `list_skills`, `load_skill`,
  `read_skill_file`. `site_figures` ports the panel's place, substations, plants, prices and
  water-risk figures; line distances (vector tiles) and the per-country connection files stay
  in the browser. `live` reads the `eu-data` snapshot and `eu-days` archive files and EIA-930.
- **Graph** (`backend/agent/graph.py`): guard, router (fast model), analyst with tools (12 calls,
  60 s soft deadline), cartographer (fast model, three tries), grounding (`agent/grounding.py`:
  numbers within the precision shown, unit factors 1,000 and 100 accepted, years and small
  counts skipped; one repair round, then unfound numbers are marked), finish. No `Send` fan-out:
  no eval shows a need yet.
- **Streaming** (`app/sse.py`): `text` (`delta`, or `reset` when the grounding asks for a
  rewrite), `tool`, `map`, `chart`, `sources`, `done` (trace id, answer, grounding, cost,
  latency), `error`; a heartbeat comment every 15 s.
- **Models** (`agent/models.yaml`, `backend/agent/models.py`): prices with their page and date;
  the Anthropic cache breakpoint on the frozen system prompt (tools render before it, so both
  are cached); the volatile part (date, view, question) after it. A scripted fake model runs
  everything without keys.
- **MapSpec**: `backend/agent/mapspec.py` -> `agent/mapspec.schema.json` and
  `frontend/src/lib/mapspec.ts` (`backend/scripts/gen_mapspec.py`).
- **Observability** (`backend/obs/`): spans `http.request`, `agent.ask`, `agent.node.*` (with
  `gen_ai.*` usage and cost), `agent.tool`, `sql.query` (statement hash, rows, ms); OTLP to
  Langfuse or any collector; the Langfuse LangChain handler per run (session = conversation id);
  run records `agent/logs/<date>/<trace>.json`; CloudWatch EMF metrics `InfraAtlas/Agent`.
- **Caps** (`backend/agent/limits.py`): DynamoDB token bucket per hashed IP, daily spend
  counter; the Worker's rate-limiting binding in front.
- **Hosting**: `backend/deploy/` (Dockerfile with the Lambda Web Adapter 0.9.1, SAM template,
  IAM policies, the Worker); `.github/workflows/backend.yml`, `agent-evals.yml`.
- **Measured** (2026-10-27, no model key in the session): the image is 175 MB compressed and
  uses ~150 MB of memory with the app tables loaded; with the fake model a question takes
  ~40 ms in process. Model costs per question are not measured yet: the eval workflow prints
  them per model once `ANTHROPIC_API_KEY` is set.

## 12. Areas: any area, only the data inside it (brief 27, 2026-10-29)

The agent answers for whatever area a question means and shows only the data inside it.

- **One area record** (`backend/data/areas.py`): `area_id` (`a_` + 12 hex of the SHA-256 of the
  normalised outline), name, level, ISO alpha-3 codes, parents, outline (GeoJSON, EPSG:4326), bbox,
  geodesic `area_km2`, people (GHSL, cells whose centre lies inside), source and how it was built.
  Kept in the results directory and the object store (`agent/areas/<id>.json`), so maps, links
  (`?aid=`) and later turns reuse it.
- **`resolve_area`** (agent and MCP): from the view (`from_view`: the drawn polygon or circle,
  the selected countries, the map on screen, sent by `viewOf()`), from text (the gazetteer and the
  outline sets `shapes.nuts`, `shapes.admin1`, `shapes.bidding_zones`, `outlines.*`, ranked by
  exact match, asked level, outline before point, in view, population, level preference;
  "Name, qualifier" filters by country, parent or US state), named groups
  (`agent/areas/groups.yaml`, each with the page stating its membership), unions of several names,
  circles (`radius_km` around a point or a place), buffers (`buffer_km`, azimuthal equidistant
  projection centred on the area) and intersections. Ambiguous names come back as candidates
  with parents; a place that has only a point (a GeoNames city without an outline set) is never
  given an invented outline: the note names what exists. The result lists `datasets_at_level`
  from the level matrix `agent/areas/levels.yaml`.
- **`run_sql` sees the areas**: the request's areas and any `a_...` id written in the SQL become
  the temporary view `areas(area_id, name, level, geometry, xmin, ymin, xmax, ymax)` and the macros
  `in_area(lon, lat, id)`, `intersects_area(geom, id)`, `km_inside(geom, id)`,
  `km2_inside(geom, id)`, `area_geom(id)` on the query's own cursor. `in_area` with a literal id is
  rewritten to a plain bounding-box test first (literal bounds, so Parquet row groups are
  skipped) and `ST_Contains` after it; the rewritten query passes the guard again. DuckDB runs
  with `geometry_always_xy = true` (lon/lat order; geodesic lengths and areas on WGS84).
- **Tables keyed by region**: joined by key when the area is that region. A country or a group
  of countries on a table with a country key is filtered by the key (generalised outlines leave
  coastal and offshore records outside). For a drawn area a region's total is never split by
  area share: the regions wholly inside are summed and the ones partly inside listed with their
  full values.
- **`area_stats`** (agent and MCP, `backend/tools/area_stats.py`, rasters in
  `agent/rasters.yaml`): people and built-up surface (GHSL sums: the finest published grid
  within the cell budget, else the next published one), land cover and slope class shares
  (ESA WorldCover and Copernicus DEM read in place from AWS open data; slope computed per DEM
  cell), solar PVOUT and 100 m wind means, river flood depth classes. Cells count when their
  centre lies inside (GDAL's rasterize rule); above the budget, means and classes read a COG
  overview and say so. rasterio adds about 120 MB to the image.
- **Maps**: MapSpec `area` (and a per-panel `area`) draws the outline, frames the camera, clips
  the agent's layers and makes it the app's own area (base layers clipped, area card). Shape sets
  below the country (`admin2`, `lau`, `divisions:<subtype>`, `us_places`, `us_tracts`, `lad`,
  `msoa`, `lsoa`, `fr_communes`, `iris`, `nl_gemeente`, `nl_wijk`, `nl_buurt`,
  `urban_centres`, `h3:<res>`, `area`) travel with the saved map record, simplified to 1/1500 of
  their extent; H3 outlines come from DuckDB's `h3` extension (in the image).
- **API**: `GET /api/areas/resolve?q=&level=`, `GET /api/areas/{area_id}` (outline, figures,
  sources), `GET /api/shapes/{set}/{iso3|all}` (cached in the object store).
- **Skill** `area-analysis`; `places-and-shapes`, `make-map`, the system and cartographer
  prompts updated. **Evals**: `agent/evals/areas.yaml` (20 cases, built by
  `backend/scripts/build_area_evals.py`; the fake model plays them through the graph in
  `tests/test_area_evals.py`; `uv run python -m evals.run --questions ../agent/evals/areas.yaml`
  scores a real model).
