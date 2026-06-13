# gridwatch

Satellite-based construction monitoring for energy infrastructure in Germany — utility-scale solar parks (≥5 MW, Bayern + Baden-Württemberg) monitored with free Sentinel-2/Sentinel-1 data, compared against legal deadlines, queryable through an evidence-citing AI agent.

- **Plan & status:** [PLAN.md](PLAN.md)
- **Conventions:** [CLAUDE.md](CLAUDE.md)
- **Data sources:** [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)
- **Credentials setup:** [docs/SETUP.md](docs/SETUP.md)

## Quick start

```sh
cp .env.example .env            # fill in per docs/SETUP.md
uv sync --all-packages          # python workspace (backend + ingestion)
supabase db push                # apply migrations
uv run pytest                   # smoke tests
uv run python -m ingestion.run --list
```

### Run the dashboard (two terminals)

```sh
# 1. backend API (holds the service-role key; serves the frontend + agent)
uv run uvicorn app.main:app --app-dir backend --port 8000

# 2. frontend (deck.gl 3D map + agent command bar + site evidence drawer)
cd frontend && npm install && npm run dev      # http://localhost:5173
```

The map shows every German energy site as a capacity column coloured by construction
state; the command bar filters/flies the map by plain-English query; clicking a site
opens its satellite timeline with cited evidence.
