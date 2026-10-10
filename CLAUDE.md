# Europe InfraAtlas - project conventions

An interactive, source-backed map of Europe's power system (grid, plants, gas,
cross-border flows, prices, generation mix). **Read [PLAN.md](PLAN.md) first.**
The earlier Germany atlas (backend, ingestion, agent) is archived in the git tag
`germany-atlas-final`; do not reintroduce it.

## Layout

- `frontend/` — React + Vite + TS + MapLibre GL + deck.gl + Tailwind + zustand. One map:
  `src/app/` state, loaders, colours (`store.ts` holds layers and stories); `src/map/`
  the map (`MapCanvas.tsx` render loop, `build.ts` every deck.gl layer, `style.ts`
  MapLibre style and labels); `src/ui/` panels (Layers, context panel, time bar).
  `src/components/` cards, `src/lib/` data helpers and custom GPU layers
  (`flowArrowLayer.ts` chevron flows, `flowLayers.ts` path geometry and the flow clock).
  `src/components/EuropeView.tsx` is the earlier view, kept for `?capture` recordings.
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

## Working rules (every session, on a laptop or in the cloud)

- **Branches and PRs.** Pushing `main` deploys the live site (Cloudflare builds it). Cloud
  sessions work on their own branch and open a pull request; the owner merges. The data
  branches `eu-data` and `eu-days` are written by GitHub Actions: never commit to them or
  force-push them.
- **Commits** carry no AI attribution (no `Co-Authored-By` or generated-with lines).
- **Secrets** stay in the environment (`.env` locally, repo secrets in Actions, the cloud
  environment's settings): never print, log or commit a key. Cloudflare and the GEM form
  details live as repo secrets; a session that needs R2 or GEM triggers the workflow
  (`gh workflow run ...`) rather than holding the key.
- **Raw licensed files** (GEM downloads) live only in the private R2 bucket
  `infraatlas-raw`; never commit or republish them. Big downloads run in GitHub Actions.
- **Visual style:** reference-clean, calm maps; the grid stays the hero; no busy, blurred
  or blinking layers; animation only where it carries data (flows, the clock). Keys and
  legends compact and off the land; one Layers panel and one context panel, no new
  floating panels per dataset. A new dataset is a layer (with its key and source) plus a
  card in the existing panels.
- **Every figure on screen** names its source; computed values say how ("median of 43
  zones", "sum of the member states reporting"). Prices keep the source's precision.
- **Before a PR:** `uv run ruff check . && uv run ruff format .`, `uv run pytest`,
  `cd frontend && npm run build`. In the PR, describe what the map shows now, the new
  files in docs/DATA_SOURCES.md, and the link of the session
  (`https://claude.ai/code/${CLAUDE_CODE_REMOTE_SESSION_ID/#cse_/session_}`).
- **Videos and screenshots** are never committed; recordings follow docs/VIDEO.md (only
  sourced values on screen).
- Task briefs for cloud sessions are in `docs/tasks/`.

## Data notes (this environment)

- **uv** is installed user-level and not on PATH. In PowerShell prepend
  `$env:Path = "$env:APPDATA\Python\Python313\Scripts;$env:Path"`.
- **ENTSO-E** (`ENTSOE_API_KEY`) is the source of every live figure since 2026-10-05
  (`scripts/entsoe.py`): four requests at a time, ~1 min for a snapshot, ~2 min for a
  30-day archive. Newest intervals arrive late and in parts (Italy zone by zone); the
  rules for picking the newest complete interval are in docs/DATA_SOURCES.md.
- **Energy-Charts** has answered HTTP 503 since 2026-09-24; only installed capacity
  still comes from it (carried over while it is down). It answers 429 to bursts.
- **Ember** serves all countries in one request (`scripts/fetch_transition.py`); its
  aggregates are asked by name (`entity=EU`), countries by ISO alpha-3 code.
- **powerplantmatching** lists German units individually (MaStR): German wind is per
  turbine and sums ~12 % above the official capacity; the panel shows both.
- **Windows** needs the `tzdata` package for `zoneinfo` (already a dependency).
