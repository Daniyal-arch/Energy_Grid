# Europe InfraAtlas - project conventions

An interactive, source-backed map of Europe's power system (grid, plants, gas,
cross-border flows, prices, generation mix). **Read [PLAN.md](PLAN.md) first.**
The earlier Germany atlas (backend, ingestion, agent) is archived in the git tag
`germany-atlas-final`; do not reintroduce it.

## Layout

- `frontend/` — React + Vite + TS + MapLibre GL + deck.gl + Tailwind. One view:
  `src/components/EuropeView.tsx`. Custom GPU layers in `src/lib/` (`flowArrowLayer.ts`
  chevron flows, `flowLayers.ts` path geometry and the flow clock).
- `frontend/public/data/eu/` — static JSON the app reads (built by `scripts/`).
- `scripts/` — data fetch/build scripts and probes (Python).
- `frontend/scripts/record-video.mjs` — video recorder (virtual clock, see docs/VIDEO.md).
- `.github/workflows/eu-snapshot.yml` — refreshes live figures onto the `eu-data` branch.
- `docs/` — DATA_SOURCES.md (every file and its source), VIDEO.md (recording + rules).

## Commands

```sh
uv sync                                          # Python deps for scripts/
uv run ruff check . && uv run ruff format .      # lint + format
uv run pytest                                    # tests/
cd frontend && npm install && npm run dev        # app on http://localhost:5173
cd frontend && npm run build                     # typecheck + production build
uv run python scripts/fetch_eu_snapshot.py       # refresh flows/prices/generation locally
uv run python scripts/build_eu_day.py 2026-09-24 # one day for the time-lapse (?day=)
```

## Hard rules

1. **Every number shown is sourced.** Values are passthrough from the source or computed
   in a build script, documented in docs/DATA_SOURCES.md, and labelled in the UI (e.g.
   "sum over a 24 km hexagon"). Never invent, smooth into new values, or estimate.
2. **Probe before implementing.** For uncertain external behaviour (API quirks, rate
   limits, formats), write a small `scripts/probe_*.py`, show the output, then build.
3. **Stop and ask for credentials.** When a step needs an account or key, tell the user
   where to register and which env var to set; keep `.env.example` documenting each.
4. **Explain large downloads first** and show progress.
5. **Type hints everywhere;** `ruff` clean and `npm run build` passing before committing.
6. **Small commits per feature;** never commit videos or images (`recordings/` is ignored).
7. **No over-engineering:** static site, scripts, one workflow. No backend unless a
   feature truly needs one.

## Data notes (this environment)

- **uv** is installed user-level and not on PATH. In PowerShell prepend
  `$env:Path = "$env:APPDATA\Python\Python313\Scripts;$env:Path"`.
- **Energy-Charts** answers HTTP 429 to bursts: one request at a time, ~3 s apart,
  honour Retry-After. Its newest 15-min interval is often partial; use the newest
  complete one (`newest_complete_index` in `scripts/fetch_eu_snapshot.py`).
- **ENTSO-E** (`ENTSOE_API_KEY`) is slow for many requests; used only for reservoirs.
- **powerplantmatching** lists German units individually (MaStR): German wind is per
  turbine and sums ~12 % above the official capacity; the panel shows both.
- **Windows** needs the `tzdata` package for `zoneinfo` (already a dependency).
