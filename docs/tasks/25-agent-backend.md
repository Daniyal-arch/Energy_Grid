# 25. The backend: the data service and the agent on AWS Lambda (LangGraph, any model, traced)

## Goal

Build `backend/`, one Python service that:

1. **serves the app's data** without the agent: the catalogue, places, the "Check a site"
   figures, saved maps (the backend service);
2. **runs the agent** that answers questions from InfraAtlas's own data and draws its answer on
   the map (the contract is docs/AGENT.md §1 and §3–§5: tools, semantic catalogue, MapSpec, every
   number from a tool result);
3. **exposes the same tools as an MCP server** for Claude Code, Claude Desktop and other agents;
4. is **traced end to end** (every question, model call, tool call and SQL query, with tokens,
   cost and latency) and **evaluated** on a fixed question set;
5. works with **any chat model** by configuration (Anthropic by default);
6. is **deployed to AWS Lambda** by GitHub Actions (container image, streamed responses).

One session, one pull request, a commit per stage below. The frontend "Ask" tab and the map
overlays are brief 20; this brief only generates the shared MapSpec types for the frontend.

## Read first, and nothing else until a stage needs it

- `vault/index.md`, then `vault/backend/agent-backend.md`, `vault/data/lake.md`,
  `vault/rules.md`, `vault/decisions.md` (the owner's decisions of 2026-10-18 and 2026-10-27).
- `docs/AGENT.md` (the agent's contract), `docs/DATA_LAKE.md` §1, §2 and §8, `CLAUDE.md`.
- `agent/catalog/*.yaml` only when building the catalogue tools.

## How to work in this session

- **Chat in the caveman style** (`.claude/skills/caveman/SKILL.md`, level full) to save tokens;
  code, comments, commits, docs, the PR and the vault stay in normal English.
- **The vault replaces re-reading the repo** (`.claude/skills/atlas-vault/SKILL.md`): read the
  index first; at the end of every stage update `vault/backend/*.md`, `vault/index.md`,
  `vault/decisions.md` (only for decisions the owner made) and `vault/log.md`.
- **Probe before building** (stage 0); show the probe output in the PR.
- **Missing credentials never stop the work:** build and test with fakes (a fake chat model,
  a local fixture lake), mark the step as blocked, and list in the PR what the owner must
  provide, where to get it and which variable to set (table below).
- **Lean:** the frameworks below are the owner's choice; add no other framework without a line
  in the PR saying why. No multi-agent structure the evals do not justify.
- Commit after each stage with its tests green; no AI attribution in commits or the PR.

## Fixed choices

| Concern | Choice |
|---|---|
| Runtime | Python 3.12; `backend/` is its own uv project (`backend/pyproject.toml`, `backend/uv.lock`) so the Lambda image stays small; ruff and pytest as in the root |
| Web | FastAPI + uvicorn; Server-Sent Events for `/api/ask` |
| Orchestration | LangGraph (`StateGraph`); LangChain core types only (messages, tools); no legacy chains |
| Models | `langchain.chat_models.init_chat_model("<provider>:<model>")`; `langchain-anthropic` installed by default, `langchain-openai`, `langchain-google-genai`, `langchain-aws` (Bedrock Converse) and `langchain-ollama` as optional extras; a registry in `agent/models.yaml` |
| Data | DuckDB (`httpfs`, `spatial`) over the lake on R2 (S3 API) and the public map files; `sqlglot` for the SQL guard |
| Schemas | Pydantic v2 for tool inputs and the MapSpec; JSON Schema generated from Pydantic; TypeScript types generated into `frontend/src/lib/mapspec.ts` |
| MCP | the official `mcp` Python SDK (FastMCP, streamable HTTP) mounted at `/mcp`; `langchain-mcp-adapters` to attach external MCP servers to the agent (none by default) |
| Observability | OpenTelemetry SDK with the GenAI semantic conventions; Langfuse (LangChain callback handler and its OTLP endpoint); JSON logs and CloudWatch EMF metrics; LangSmith works through its own environment variables but is not required |
| Hosting | AWS Lambda from a container image (ECR) with the AWS Lambda Web Adapter in response-streaming mode, a Function URL with `InvokeMode: RESPONSE_STREAM`; AWS SAM template; DynamoDB (on demand) for rate and spend counters; secrets in SSM Parameter Store (SecureString); deployed by GitHub Actions with OIDC (no long-lived AWS keys) |
| Storage | saved maps and run records on R2 under `agent/` (the S3 API), next to the lake |
| Same origin | a small Cloudflare Worker routes `/api/*` and `/mcp` on the site's domain to the Function URL (stage 13) |

The model choice: Claude through the Anthropic API by default (the owner's decision of
2026-10-18: AWS credits do not pay for Claude on Bedrock). AWS credits pay for Lambda,
DynamoDB, ECR and CloudWatch, and for non-Claude Bedrock models if the owner selects one.

## Layout

```
backend/
  pyproject.toml  uv.lock  README.md  .env.example
  app/        main.py  settings.py  deps.py  sse.py
              routes/  health.py  catalog.py  places.py  site.py  maps.py  ask.py  admin.py
  agent/      graph.py  state.py  router.py  analyst.py  cartographer.py  grounding.py
              limits.py  mapspec.py  events.py  skills.py  models.py
              prompts/  system.md  router.md  cartographer.md
  tools/      catalog.py  sql.py  places.py  site.py  live.py  maps.py  charts.py  results.py
  data/       duck.py  guard.py  r2.py  gazetteer.py
  mcp_server/ server.py  client.py
  obs/        tracing.py  langfuse.py  logging.py  cost.py  metrics.py
  evals/      run.py  scorers.py
  probes/     probe_*.py
  deploy/     Dockerfile  template.yaml  samconfig.toml  iam/  worker/ (wrangler.toml, src/index.ts)
  tests/
agent/        catalog/*.yaml (exists)  skills/<name>/SKILL.md  models.yaml  mcp.yaml
              mapspec.schema.json  evals/questions.yaml
frontend/src/lib/mapspec.ts   (generated; no other frontend change)
.github/workflows/backend.yml  .github/workflows/agent-evals.yml
vault/backend/*.md
```

## Stages

### 0. Probes (`backend/probes/`, outputs in the PR)

- **Lake:** DuckDB with `httpfs` reads `lake/_catalog.json` and one partitioned table on R2 with
  the read-only token; time the cold open and a typical query. Without the R2 token, read the
  public map files and mark the lake as blocked.
- **Models:** for each key present (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, AWS
  credentials for Bedrock), one streamed round trip with a tool call through `init_chat_model`;
  record tool calling, streaming, cached tokens and the current model ids and prices from the
  providers' pages (the registry's source).
- **Streaming on Lambda:** the FastAPI SSE endpoint behind the Lambda Web Adapter (run the image
  with Docker if the environment has it; else test the ASGI app with an `httpx` streaming client
  and say so). Events must arrive one by one, not at the end.
- **Tracing:** a trace reaches Langfuse when its keys are set; else the OTel console exporter.

### 1. Service skeleton

FastAPI app, settings (pydantic-settings: environment, then SSM in Lambda), `/api/health`
(version, git sha, lake catalogue date, model ids), CORS for the site origin and
`http://localhost:5173`, request ids, JSON logs. Tests.

### 2. Data layer and SQL guard

- One DuckDB connection per container: read-only, extensions shipped in the image (no download
  at start), external access limited to the lake prefix and the app's public files
  (`allowed_directories` / `allowed_paths`, `enable_external_access`), `lock_configuration`.
- The guard (`sqlglot`): one `SELECT` or `WITH`; no DDL, DML, `PRAGMA`, `ATTACH`, `COPY`,
  `INSTALL`, `LOAD`, `SET`; file-reading functions only on allowed paths; a `LIMIT` added;
  25 s timeout (interrupt); at most 2,000 rows returned, the full result kept under a
  `result_id` (in `/tmp`, and on R2 when a map uses it). Licensed GEM tables only in aggregates.
- Tests on a fixture lake (small Parquet files written by the tests) and a list of attack
  queries that must be refused.

### 3. The backend service (usable by the app without the agent)

`GET /api/catalog/search?q=`, `GET /api/catalog/{dataset}`, `GET /api/places?q=`,
`GET /api/site?lon=&lat=` (the "Check a site" figures computed server-side with the same sources
and rules as `frontend/src/components/SiteCards.tsx`; each figure with its source),
`POST /api/maps` (a MapSpec and its data, returns an id) and `GET /api/maps/{id}`,
`POST /api/admin/sql` (admin key only: for evals and the owner). Every response carries
`sources`. Tests.

### 4. Tools

The tools of docs/AGENT.md §3 as LangChain tools with Pydantic arguments: `search_catalog`,
`describe_table`, `run_sql`, `find_place`, `site_figures`, `live` (an allow-list of sources with
per-source rate limits and a 10-minute cache), `make_map` (validates the MapSpec of
`agent/mapspec.py`; the JSON Schema goes to `agent/mapspec.schema.json` and the TypeScript types
to `frontend/src/lib/mapspec.ts` through a generator script), `make_chart`. Every result:
`{data, sources: [{dataset, table, licence, retrieved}], result_id?}`. Tests per tool.

### 5. Any model

- `agent/models.yaml`: per entry the id, `provider:model`, prices per million input, output and
  cached tokens (with the source page and date), context window, tool calling, the caching kind,
  default effort or temperature.
- Environment: `AGENT_MODEL` (default `anthropic:claude-opus-5-5`), `AGENT_MODEL_FAST` for the
  router and the cartographer (default `anthropic:claude-haiku-5-5`); a request may pick a model
  only from `AGENT_MODELS_ALLOWED`.
- Provider details live only in `agent/models.py`: Anthropic cache breakpoints after the tools and
  the system prompt; OpenAI's automatic caching; Bedrock Converse for non-Claude Bedrock models.
  A model without tool calling is refused with a clear error.
- A fake tool-calling chat model for the tests. Done when the unit tests pass with the fake and
  the 10-question eval sample runs on Anthropic and one other provider (when keys exist).

### 6. Skills for the agent (Agent Skills format, any model)

`agent/skills/<name>/SKILL.md` (frontmatter `name` and `description`, a short body, optional
`references/`). The system prompt lists only names and descriptions; the tools `list_skills()`,
`load_skill(name)` and `read_skill_file(name, path)` load the rest when the model asks
(progressive disclosure, so any model can use them). First skills: `lake-sql` (DuckDB patterns,
units, time zones, the API-or-Parquet rule), `make-map` (MapSpec rules, the app's palettes,
existing layers first, calm maps), `site-screening`, `explain-view`, `prices` (precision, zones,
negative hours), `grid-capacity` (the four classes, the summable rule), `emissions` (reported
versus modelled, which installations are placed), `places-and-shapes` (keys and joins). Each
names the catalogue entries it relies on. Test: a price question loads `prices`.

### 7. The agent graph (LangGraph)

```
START -> guard (caps, input size)
      -> router        fast model: the kind of answer and the specialists it needs
      -> analyst       main model: tools + skills, at most 12 tool calls
      -> cartographer  fast model, only when a map or chart is asked: MapSpec from result_ids, validated, at most 3 tries
      -> grounding     deterministic: every number in the text is in this turn's tool results within the source's precision;
                       one repair round by the analyst; numbers still unfound are marked
      -> finish        sources, cost, trace id
      -> END
```

- **Multi-agent only where it pays.** The analyst answers most questions alone. The
  cartographer is separate because a small model builds a MapSpec well and keeps the analyst's
  context clean. Comparisons across three or more places may fan out with LangGraph's `Send` to
  parallel analyst runs, kept only if the evals show it is faster or cheaper (numbers in the PR).
- **State:** messages, the tool results (indexed for the grounding check), result ids, sources,
  spend, step count. Stateless between requests: the browser sends the conversation (trimmed);
  no server-side checkpoints beyond one request.
- **Streaming:** `graph.astream(..., stream_mode=["messages", "updates", "custom"])` mapped in
  `app/sse.py` to the SSE events of docs/AGENT.md §6 (`text`, `tool`, `map`, `chart`, `sources`,
  `done`, `error`), a heartbeat every 15 s.
- **Limits:** 12 tool calls, 25 s per query, a 60 s soft deadline (answer with what it has),
  output tokens per turn; refusals and stop reasons handled for every provider.
- **Prompts:** the house rules of docs/AGENT.md §6, the catalogue list, the MapSpec schema and
  the skill index before the cache breakpoint; today's date, the current map view and the
  question after it.

### 8. MCP

- Server: FastMCP at `/mcp` (streamable HTTP) with `search_catalog`, `describe_table`, `run_sql`,
  `find_place`, `site_figures` and `live` (the same code, limits and logs as the agent), the
  catalogue entries and skill files as resources; bearer keys from `MCP_API_KEYS`; off when unset.
  Test with the `mcp` client.
- Client: `agent/mcp.yaml` lists external MCP servers to attach as tools with
  `langchain-mcp-adapters` (empty by default; one commented example).

### 9. Observability and traceability

- A trace id per request (W3C `traceparent`), returned in the SSE `done` event and a header.
- OpenTelemetry spans: request, graph node, model call (`gen_ai.*`: system, model, input, output
  and cached tokens, cost), tool call, SQL query (statement hash, rows, ms). Exporters by
  environment: OTLP (Langfuse's endpoint or any collector), console in development.
- Langfuse: the callback handler on every graph run when `LANGFUSE_*` is set; session id = the
  browser's conversation id; tags: model, route, version; scores: grounding, eval results.
- A run record per question on R2 at `agent/logs/<date>/<trace>.json`: question, route, tool
  calls and arguments, SQL, row counts, tokens, cost, latency, grounding result, model; no
  personal data (the IP hashed); 90 days (an R2 lifecycle rule, documented).
- CloudWatch: JSON logs, EMF metrics (latency, tokens, cost, errors, tool calls per question), a
  dashboard and alarms in the SAM template. `obs/cost.py`: cost = usage × the registry's prices.

### 10. Safety and caps

Per-IP limit (a DynamoDB token bucket on the hashed IP), a global daily spend cap (an atomic
counter; over the cap the SSE stream says the day's budget is used), request size limits,
read-only everywhere, rows are data and never instructions (said in the system prompt and
enforced by wrapping tool results), keys for `/mcp` and `/api/admin`, CORS. Tests.

### 11. Evaluations

`agent/evals/questions.yaml`: at least 40 questions with known answers (from the catalogue
examples and docs/DATA_SOURCES.md) and 10 map questions with the expected overlay kind and key.
`uv run python -m evals.run --model <id> --sample 10`; scorers: the number within the source's
precision, every number grounded, sources listed, MapSpec valid, latency, cost. Results to
Langfuse dataset runs when its keys exist and a summary per model in the PR.
`.github/workflows/agent-evals.yml`: a 10-question sample on PRs that touch `backend/` or
`agent/` (cost-capped, skipped without a key), the full set weekly.

### 12. Lambda packaging and deploy

- `backend/deploy/Dockerfile`: a slim Python 3.12 base; the Lambda Web Adapter extension copied
  from its public ECR image at a pinned version into `/opt/extensions/`; dependencies installed
  with `uv sync --frozen`; DuckDB extensions installed at build; `AWS_LWA_INVOKE_MODE=response_stream`,
  `AWS_LWA_PORT=8080`, readiness check on `/api/health`, `HOME=/tmp`; arm64.
- `backend/deploy/template.yaml` (SAM): the function (memory 3008 MB to start, measure and adjust
  in the PR; ephemeral storage 2048 MB; timeout 300 s; reserved concurrency 10), the Function URL
  (`AuthType: NONE`, `InvokeMode: RESPONSE_STREAM`), the DynamoDB table, least-privilege IAM (SSM
  `/infraatlas/*`, the table), log retention 30 days, the dashboard and alarms.
- Secrets in SSM SecureString under `/infraatlas/` (model keys, R2 keys, `LANGFUSE_*`,
  `MCP_API_KEYS`, `ADMIN_API_KEY`, `PROXY_SECRET`), read once per cold start; nothing secret in
  the image, the template or the repository.
- `.github/workflows/backend.yml`: on pull requests touching `backend/` or `agent/`: ruff,
  pytest, image build; on `main`: OIDC role (`AWS_DEPLOY_ROLE_ARN` secret, `AWS_REGION`
  variable), push to ECR, `sam deploy`, then a smoke test (`/api/health` and one cheap question on
  the fast model). Without the role the job prints the setup steps and skips.
- `backend/README.md`: run locally, test, deploy, and the owner's one-time AWS setup (the GitHub
  OIDC provider and role with the policy in `deploy/iam/`, the SSM parameters, the region).

### 13. Same origin (Cloudflare Worker)

`backend/deploy/worker/`: routes `/api/*` and `/mcp` on the site's domain to the Function URL,
adds `X-Atlas-Proxy: <PROXY_SECRET>` (the Lambda refuses requests without it when
`REQUIRE_PROXY=true`), passes SSE through unbuffered, applies the Workers rate-limiting binding
first. Deployed by the workflow with wrangler and the existing `CLOUDFLARE_API_TOKEN` (needs
Workers edit rights; else blocked). The frontend can also call the Function URL directly (CORS);
keep both possible.

### 14. Docs and vault

docs/AGENT.md brought to what was built (architecture, run locally, deploy, measured costs),
`backend/README.md`, `.env.example` (every variable), the vault notes `vault/backend/*.md`
(service, graph, tools, models, observability, deploy) with `vault/index.md` and `vault/log.md`
updated, and `.claude/skills/atlas-vault/SKILL.md` if the way of working changed.

## Credentials the owner provides (the session builds with fakes until then)

| What | Where | Variable |
|---|---|---|
| Anthropic API key | console.anthropic.com (Claude Startups credits when granted) | `ANTHROPIC_API_KEY` (SSM; a cloud env var for probes and evals) |
| Other model keys (optional) | platform.openai.com, aistudio.google.com; Bedrock through the AWS role | `OPENAI_API_KEY`, `GOOGLE_API_KEY` |
| AWS account and region | aws.amazon.com; region `eu-central-1` unless the owner picks another | repo variable `AWS_REGION` |
| GitHub OIDC deploy role | AWS IAM: identity provider `token.actions.githubusercontent.com` and a role for `Daniyal-arch/Energy_Grid` (policy in `backend/deploy/iam/`) | repo secret `AWS_DEPLOY_ROLE_ARN` |
| R2 tokens | Cloudflare dashboard, R2, API tokens: read-only for `infraatlas-raw/lake/`, read-write for `agent/` | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` (SSM) |
| Langfuse project | cloud.langfuse.com (free tier) or self-hosted later | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` |
| Service keys | generated by the owner (`openssl rand -hex 32`) | `ADMIN_API_KEY`, `MCP_API_KEYS`, `PROXY_SECRET` (SSM) |
| Cloudflare token rights | the existing `CLOUDFLARE_API_TOKEN` with Workers Scripts edit | repo secret (exists) |

## Done-check

- `cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest` green; the
  root checks green; `cd frontend && npm run build` green with the generated `mapspec.ts`.
- Locally `uv run uvicorn app.main:app --port 8080` and
  `curl -N -X POST localhost:8080/api/ask -d '{"question": "..."}'` stream `text`, `tool`, `map`
  and `done` events with the fake model; with a real key, the 10-question sample's scores, cost
  and latency per model are in the PR.
- An MCP client lists the tools and runs `search_catalog`.
- The image builds; streaming through the Lambda Web Adapter is verified, or the PR says why it
  could not be run in the session.
- The deploy job is green when the role is set, else it skips with the setup steps.
- A trace with its spans and a run record exist for an eval question (describe them; no
  screenshots committed).
- The PR describes what the backend serves, the graph, how to switch models, the measured costs,
  the blocked items with where to get each key, and the session link.

## Out of scope

The Ask tab and the overlay rendering (brief 20); accounts and saved conversations; tools that
write anything but saved maps and run records; alerts; new datasets.
