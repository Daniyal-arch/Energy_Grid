# Germany InfraAtlas - project conventions

Source-backed intelligence for German infrastructure, energy security, external
dependencies, economic resilience, transition delivery, and geopolitical exposure.
The existing energy asset and remote-sensing code is a lifecycle signal layer within
that broader system. **Read [PLAN.md](PLAN.md) first**; it defines scope and migration
order. Package names and database tables may retain legacy names until compatibility
migrations are ready.

## Layout

- `backend/` — FastAPI app. Domain models in `backend/app/models/domain.py` are the **shared** Pydantic models.
- `ingestion/` — data-source adapters + CLI runner. Depends on `backend` via uv workspace; may import `app.models`, `app.config`, `app.db` only (never `app.routers`).
- `frontend/` — React + Vite + TS + MapLibre GL + Tailwind.
- `supabase/migrations/` — plain SQL, applied with `supabase db push` (or `supabase migration up`).
- `scripts/` — probe scripts for uncertain external APIs.
- `docs/` — DATA_SOURCES.md (adapter status tracker), SETUP.md (credentials walkthrough), VIDEO.md (power-grid video recording + rules for text in published videos), ADRs.

## Commands

```sh
uv sync                                          # install everything (workspace root)
uv run pytest                                    # all tests
uv run ruff check . && uv run ruff format .      # lint + format
uv run python -m ingestion.run --source brightsky --since 2026-06-01   # run one adapter
uv run uvicorn app.main:app --reload --app-dir backend                 # backend dev server
cd frontend && npm install && npm run dev        # frontend dev server
cd frontend && npm run record:video -- --format 4x5   # power-view MP4 (dev server + API running) -> recordings/; see docs/VIDEO.md
```

## Hard rules

1. **The agent never computes facts.** It retrieves stored observations or curated source-catalog entries and narrates them with citations. Catalog coverage is not a current observation. Derived indicators are computed in pipelines, versioned, and stored with provenance first.
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
- Agent ([backend/app/agent.py](backend/app/agent.py)): **OpenAI-compatible chat API**, provider configurable via `LLM_PROVIDER` (`deepseek` | `groq` | `gemini`; default DeepSeek `deepseek-chat`). Manual retrieval loop; responses carry a structured `sources` array. `get_strategic_context` covers researched sources while the existing tools cover stored asset and grid observations. Served at `POST /agent/query`.
- Asset lifecycle states remain `no_activity -> clearing -> earthworks -> construction -> complete` (enum `SiteState` in domain models). They are one signal type, not the platform taxonomy.
- Dates in DB are ISO date strings; everything UTC.

## Data sources

Implementation order and status are tracked in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).
The machine-readable catalog is `backend/app/strategic_context.py`; keep the two in
sync. Priority expansion sources are BNetzA gas, the hydrogen core network, Destatis
trade, DB InfraGO, Eurostat material/industry tables, UBA, and DERA.

### Gotchas (this environment)

- **uv** is installed user-level and not on PATH. In PowerShell prepend `$env:Path = "$env:APPDATA\Python\Python313\Scripts;$env:Path"`. Use `uv sync --all-packages` (plain `uv sync` only does the root group).
- **MaStR data:** the official `marktstammdatenregister.de` bulk server is throttled to ~6 KB/s (server-side). Use the open-mastr **Zenodo snapshot** instead ([scripts/download_mastr.py](scripts/download_mastr.py) → `data/`, gitignored). The adapter reads that zip directly; `mastr_zip_path` setting points at it. Columns are German + capacity is in **kW**; verified in `scripts/probe_mastr_*.py`.
- **Supabase migrations:** this network is IPv4-only and the direct DB host (`db.<ref>.supabase.co`) is IPv6-only. Push via the **session pooler**: `npx supabase db push --db-url "postgresql://postgres.<ref>:<pw>@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"`. App/adapters use the REST API (works fine over IPv4).
- **PostgREST caps reads at 1000 rows** — paginate with `.range()`. A `select s.*` **view does not auto-pick-up new table columns** — recreate the view (drop + create) after adding columns.
