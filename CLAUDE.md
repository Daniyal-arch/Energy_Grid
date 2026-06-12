# gridwatch — project conventions

Satellite-based construction monitoring for German energy infrastructure. **Read [PLAN.md](PLAN.md) first** — it is the single source of truth for architecture, phases, and current status. Update its Status section at the end of every working session.

## Layout

- `backend/` — FastAPI app. Domain models in `backend/app/models/domain.py` are the **shared** Pydantic models.
- `ingestion/` — data-source adapters + CLI runner. Depends on `backend` via uv workspace; may import `app.models`, `app.config`, `app.db` only (never `app.routers`).
- `frontend/` — React + Vite + TS + MapLibre GL + Tailwind.
- `supabase/migrations/` — plain SQL, applied with `supabase db push` (or `supabase migration up`).
- `scripts/` — probe scripts for uncertain external APIs.
- `docs/` — DATA_SOURCES.md (adapter status tracker), SETUP.md (credentials walkthrough), ADRs.

## Commands

```sh
uv sync                                          # install everything (workspace root)
uv run pytest                                    # all tests
uv run ruff check . && uv run ruff format .      # lint + format
uv run python -m ingestion.run --source brightsky --since 2026-06-01   # run one adapter
uv run uvicorn app.main:app --reload --app-dir backend                 # backend dev server
cd frontend && npm install && npm run dev        # frontend dev server
```

## Hard rules

1. **The agent never computes facts.** It only retrieves stored rows (detections, evidence, timeseries, deadlines) and narrates them with citations. Anything analytical happens in pipelines and is stored with provenance first.
2. **New data source = one new adapter class + registry decorator.** If adding a source requires touching `ingestion/base.py`, `ingestion/registry.py`, or `ingestion/run.py`, the design is wrong — fix the framework, don't special-case.
3. **Probe before implementing.** For uncertain external behavior (API quirks, rate limits, file formats), write a small script in `scripts/`, show the user the output, then implement the adapter.
4. **Stop and ask for credentials.** When a step needs an account, key, or manual download, stop and tell the user exactly what to do (where to register, which key, which env var). Keep `.env.example` documenting every variable.
5. **Type hints everywhere.** Pydantic models for all data crossing a boundary. `ruff` clean before committing.
6. **Tests:** at minimum one smoke test per adapter with external calls mocked (use `respx` for httpx).
7. **Small commits per feature.**
8. **No over-engineering:** no multi-tenancy, billing, k8s, microservices. One deployable backend, one frontend, one ingestion package.

## Stack notes

- Python 3.11+, **uv workspace** (root `pyproject.toml` lists members `backend`, `ingestion`).
- DB access via `supabase-py` (service-role key in pipelines/backend; anon key only in frontend). Geometry written as WKT through PostGIS.
- Image chips → Supabase Storage bucket `chips`; DB stores URLs only.
- Timeseries is a narrow table: `(site_id, date, sensor, metric, value)` with upsert on conflict.
- Agent: Anthropic Python SDK, model **`claude-opus-4-8`**, adaptive thinking (`thinking={"type": "adaptive"}`), tool use; responses must carry a structured `sources` array. Don't use deprecated `budget_tokens` or assistant prefills.
- States: `no_activity → clearing → earthworks → construction → complete` (enum `SiteState` in domain models — reuse it, never string literals).
- Dates in DB are ISO date strings; everything UTC.

## Data sources

Implementation order and status tracked in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md). Phase 1: GEE (S2+S1), MaStR (`open-mastr`), Bright Sky/DWD. Phase 2: EEG auctions, ENTSO-E, SMARD, OSM. Phase 3: WorldCover/DEM, state orthophoto WMS, stubs for Netztransparenz/UVP/news.
