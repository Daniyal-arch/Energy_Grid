# gridwatch

Satellite-based construction monitoring for energy infrastructure in Germany — utility-scale solar parks (≥5 MW, Bayern + Baden-Württemberg) monitored with free Sentinel-2/Sentinel-1 data, compared against legal deadlines, queryable through an evidence-citing AI agent.

- **Plan & status:** [PLAN.md](PLAN.md)
- **Conventions:** [CLAUDE.md](CLAUDE.md)
- **Data sources:** [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)
- **Credentials setup:** [docs/SETUP.md](docs/SETUP.md)

## Quick start

```sh
cp .env.example .env            # fill in per docs/SETUP.md
uv sync                         # python workspace (backend + ingestion)
supabase db push                # apply migrations
uv run pytest                   # smoke tests
uv run python -m ingestion.run --list
uv run uvicorn app.main:app --reload --app-dir backend
cd frontend && npm install && npm run dev
```
