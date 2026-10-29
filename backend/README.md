# InfraAtlas backend

The data service and the agent (brief 25, `docs/tasks/25-agent-backend.md`; contract in
`docs/AGENT.md`). One FastAPI app: data routes the map can use without the agent, `/api/ask`
(the LangGraph agent, Server-Sent Events) and `/mcp` (the same read-only tools for other
agents). Runs on AWS Lambda from a container image; works with any chat model by configuration.

## Run locally

```sh
cd backend
uv sync                                   # Python 3.12, its own lock (uv.lock)
cp .env.example .env                      # or leave it: defaults need no keys except the model's
AGENT_MODEL=fake AGENT_MODEL_FAST=fake LAKE_DB= uv run uvicorn app.main:app --port 8080
curl -N -X POST localhost:8080/api/ask -H 'content-type: application/json' \
  -d '{"question": "Show the largest power plants in Germany on a map"}'
```

With `ANTHROPIC_API_KEY` set, drop the two `fake` variables. Without the R2 keys (or with
`LAKE_DB=`) only the app tables (`app.eu_plants`, `app.eu_prices`, ...) are queryable;
`LAKE_DIR=<dir>` serves a local directory of Parquet files as the lake.

| Route | What |
|---|---|
| `GET /api/health` | version, git sha, lake catalogue date, model ids |
| `GET /api/catalog/search?q=` / `GET /api/catalog/{dataset}` | the semantic catalogue |
| `GET /api/places?q=` | countries, US states, bidding zones, cities, coordinates |
| `GET /api/site?lon=&lat=&radius_km=` | the "Check a site" figures, each with its source |
| `POST /api/maps` / `GET /api/maps/{id}` | saved maps (MapSpec and its data) |
| `POST /api/ask` | the agent: SSE `text`, `tool`, `map`, `chart`, `sources`, `done`, `error` |
| `POST /api/admin/sql` | the guarded SQL (`X-Admin-Key`) |
| `/mcp` | MCP over streamable HTTP (`Authorization: Bearer <MCP_API_KEYS entry>`) |

Every response carries `sources`. Connect Claude Code to the MCP server:
`claude mcp add --transport http infraatlas https://<site>/mcp --header "Authorization: Bearer <key>"`.

## Test and check

```sh
uv run ruff check . && uv run ruff format --check . && uv run pytest
uv run python scripts/gen_mapspec.py           # regenerate the MapSpec schema and TS types
uv run python -m probes.probe_lake             # DuckDB, lockdown, the lake or the public files
uv run python -m probes.probe_models           # a tool-calling round trip per key present
uv run python -m probes.probe_streaming        # events arrive one by one
uv run python -m probes.probe_tracing          # spans and the run record for one question
uv run python -m evals.run --model claude-opus-5-5 --sample 10 --needs app
```

## Switch models

`AGENT_MODEL` (the analyst) and `AGENT_MODEL_FAST` (router and cartographer) take an id from
`agent/models.yaml` or any `provider:model` (`openai:gpt-6.1-sol`, `google_genai:gemini-3.8-flash`,
`bedrock_converse:<id>`, `ollama:<model>`). Install the provider's extra
(`uv sync --extra openai|google|aws|ollama|groq`, or `--build-arg EXTRAS="--extra openai"` for
the image) and add the model to the registry with its prices so costs and the spend cap count it. A
request may pick a model (`"model"` in the body) only from `AGENT_MODELS_ALLOWED`.

## Deploy (GitHub Actions, `.github/workflows/backend.yml`)

On `main`: build the arm64 image, push it to ECR, `sam deploy` (`deploy/template.yaml`), a smoke
test, then the Cloudflare Worker (`deploy/worker/`). Locally:
`docker build -f backend/deploy/Dockerfile -t infraatlas-backend .` (from the repository root).

### The owner's one-time AWS setup

1. Region: `eu-central-1` unless you pick another (repo variable `AWS_REGION`).
2. IAM, identity providers: add `token.actions.githubusercontent.com` (audience `sts.amazonaws.com`).
3. IAM role `infraatlas-github-deploy`: trust policy `deploy/iam/github-oidc-trust.json`, inline
   policy `deploy/iam/deploy-policy.json` (replace `<ACCOUNT_ID>` and `<REGION>`). Repo secret
   `AWS_DEPLOY_ROLE_ARN` = the role's ARN.
4. SSM Parameter Store, SecureString, under `/infraatlas/`: `anthropic_api_key`, `r2_account_id`,
   `r2_access_key_id`, `r2_secret_access_key`, `langfuse_public_key`, `langfuse_secret_key`,
   `langfuse_host`, `mcp_api_keys`, `admin_api_key`, `proxy_secret` (and optionally
   `openai_api_key`, `google_api_key`, `eia_api_key`, `ip_hash_salt`).
   `aws ssm put-parameter --name /infraatlas/anthropic_api_key --type SecureString --value ...`
5. Repo variables (optional): `SITE_ORIGINS` (the site's origin for CORS), `SITE_DOMAIN` (the
   Worker's routes), `REQUIRE_PROXY=true` once the Worker is live. Repo secret `PROXY_SECRET`
   (same value as in SSM) for the smoke test and the Worker; `CLOUDFLARE_API_TOKEN` needs
   Workers Scripts edit rights, `CLOUDFLARE_ACCOUNT_ID` the account.
6. R2: a lifecycle rule on `infraatlas-raw` deleting `agent/logs/` objects after 90 days
   (Cloudflare dashboard, R2, the bucket, Settings, Object lifecycle rules).

Without the role the deploy job prints these steps and skips.
