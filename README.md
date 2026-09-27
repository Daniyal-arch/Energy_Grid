# Germany InfraAtlas

Germany InfraAtlas is a source-backed intelligence workspace for understanding how
energy, infrastructure, trade dependencies, industrial exposure, and geopolitical
events interact across Germany.

The current frontend is a map-first animated atlas. It layers energy assets,
transmission infrastructure, planned corridors, substations, gas pipelines,
gas facilities, ports, airports, DB rail routes, rail operating points, bridges,
tunnels, federal-state boundaries, strategic industry, and cross-border power flows.

The backend still contains older asset and strategy endpoints, but the active
frontend direction is infrastructure geography and animated system representation,
not construction monitoring.

## Documentation

- [Product and migration plan](PLAN.md)
- [Engineering conventions](CLAUDE.md)
- [Dataset catalog](docs/DATA_SOURCES.md)
- [Credentials setup](docs/SETUP.md)

## Quick start

```sh
cp .env.example .env
uv sync --all-packages
supabase db push
uv run pytest
```

Run the API and frontend in separate terminals:

```sh
uv run uvicorn app.main:app --app-dir backend --port 8000
```

```sh
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The API is served at `http://localhost:8000`, with
OpenAPI documentation at `http://localhost:8000/docs`.

## Current boundary

Live/stored observations are currently strongest for electricity and energy assets.
The strategy catalog exposes researched sources for the broader scope, but candidate
sources are not treated as ingested facts. New adapters should promote those sources
into normalized observations with provenance before the analyst uses their values.
