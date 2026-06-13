# gridwatch — Build Plan

**Single source of truth for architecture, phases, and current status.** Update the Status section at the end of every working session.

## What we are building

A satellite-based construction monitoring platform for energy infrastructure in Germany. **Scope: all utility-scale generation technologies ≥5 MW, nationwide** — ground-mounted solar, wind (turbines clustered into farms), biomass, hydro, geothermal, combustion, and battery storage. We:

1. Pull approved projects from the Marktstammdatenregister (MaStR) and derive AOI polygons.
2. Monitor each site with free satellite data (Sentinel-2 optical, Sentinel-1 radar via Google Earth Engine), reduced server-side to per-site time series (NDVI, BSI, VH backscatter).
3. Run a rule-based per-site state machine: `no_activity → clearing → earthworks → construction → complete`, with persistence rules, seasonal baselines, and weather masking (DWD).
4. Compare actual progress against legal deadlines (EEG auctions) and cross-check completion with grid data (ENTSO-E / SMARD).
5. Answer user questions through an AI agent that **only retrieves and narrates stored analysis records** — every answer cites evidence (scene IDs, dates, chips, confidence). The agent never computes or guesses facts.

Customers: project developers, grid operators, lenders.

## Core principles

- **Provenance everywhere.** All analytics are produced by pipelines and stored with provenance (`evidence` rows linking scene IDs, sensors, metrics). The agent queries stored records only.
- **Pluggable data sources.** Every source is one adapter class implementing `BaseSource` + a registry entry. Adding a source never touches core pipeline code.
- **Rule-based detection first, ML later.**
- **No over-engineering.** One backend, one frontend, one ingestion package. No multi-tenancy, billing, k8s, microservices.

## Architecture

```
/backend      FastAPI app (Python 3.11+, uv). Serves API + agent. Shares models with ingestion.
/ingestion    Source adapters + pipeline jobs. CLI runner: python -m ingestion.run --source <name>
/frontend     React + Vite + TypeScript + MapLibre GL + Tailwind. Single dashboard page.
/supabase     SQL migrations (run via supabase CLI). Postgres + PostGIS + Storage (image chips) + Auth.
/docs         DATA_SOURCES.md, ADRs.
/scripts      One-off probe scripts for uncertain external APIs.
```

- **Shared models:** Pydantic domain models live in `backend/app/models/domain.py`. `ingestion` depends on `backend` via the uv workspace and imports only `app.models` / `app.config` / `app.db` (never routers).
- **Scheduler:** start with the CLI runner + GitHub Actions cron ([.github/workflows/ingest.yml](.github/workflows/ingest.yml)). Swapping to Celery/cloud scheduler later touches only the runner, nothing else.
- **Image chips** go to Supabase Storage (bucket `chips`); only URLs are stored in the DB.

### Database schema (Supabase migrations)

| Table | Purpose |
|---|---|
| `sites` | id, mastr_id, name, geom (PostGIS MultiPolygon), capacity_mw, state (DE state), owner, status (satellite construction state), technology, mastr_status (registry status), commissioning_date, planned_commissioning_date, municipality, district, unit_count, aoi_method |
| `deadlines` | site_id, source, deadline_date, type |
| `timeseries` | narrow table: site_id, date, sensor, metric, value — unique + indexed on (site_id, date, sensor, metric) |
| `detections` | site_id, detected_at, from_state, to_state, confidence, evidence_ids[] |
| `evidence` | id, site_id, scene_id, sensor, acquired_at, chip_url, metrics jsonb |
| `weather` | site_id, date, rain_mm, snow, temp_c |
| `power_output` | plant_id (EIC/MaStR unit), site_id (nullable), date, mwh, source |
| `agent_conversations` / `agent_messages` | chat history; messages carry a `sources` jsonb array of cited evidence IDs |

A view `sites_with_centroid` exposes lat/lon (ST_Centroid) for point-based APIs (weather).

### Detection logic (Phase 1–2)

- Time-series breakpoints on NDVI ↓ (clearing), BSI ↑ (earthworks), VH backscatter ↑ (structures/construction), stabilization + power output (complete).
- **Persistence rule:** a state change requires N consecutive confirming observations (default N=3).
- **Seasonal baselines:** compare same-season windows, never raw year-vs-recent.
- **Weather masking:** skip/flag observations on snow/frozen days (DWD via Bright Sky).
- **Dual-sensor confidence:** S2 + S1 agreement → high confidence; single sensor → medium.
- Every transition writes a `detections` row linked to `evidence` rows.

### Agent (Phase 2, backend `/agent` module)

Anthropic API (Python SDK, model `claude-opus-4-8`, adaptive thinking) with tool use. Tools: `list_sites`, `get_site_status`, `get_timeseries`, `get_detections`, `get_evidence`, `compare_to_deadline`, `generate_report`. System prompt forbids uncited claims; API responses include a structured `sources` array.

## Phases & acceptance criteria

### Phase 1 — core loop (CURRENT)
MaStR sites in DB → GEE backfill (since 2021, then weekly) → time series stored → state machine produces detections with evidence chips → minimal dashboard (map + charts).
**Done when:** 3 commands produce real nationwide sites with computed statuses on a map.

Tasks:
- [x] Repo scaffold, PLAN.md, CLAUDE.md, DATA_SOURCES.md
- [x] Supabase migrations (core tables + MaStR fields + centroid view)
- [x] Pluggable source framework (`BaseSource`, registry, CLI runner with subset filters)
- [x] Bright Sky adapter (no key needed) + smoke tests
- [x] Supabase project created, migrations pushed (6/6), `chips` bucket created, keys in `.env`
- [x] GEE service account verified + adapter validated end-to-end (real NDVI/BSI/VH stored)
- [x] MaStR adapter — loads **5,402 sites nationwide** (all tech ≥5 MW, ground-mounted; wind clustered into farms) from the open-mastr Zenodo snapshot. Smoke tests cover transform + clustering.
- [~] GEE backfill — pilot running on 50 recent solar sites (5-year). Then scale to "In Planung" set.
- [ ] State machine + detection writer (NDVI/BSI/VH breakpoints, persistence, seasonal baseline, weather mask)
- [ ] Evidence chip export to Supabase Storage
- [ ] Minimal dashboard: map with state-colored markers, site drawer with NDVI/BSI/VH charts

### Phase 2 — the moat
EEG auction deadline parsing (Bundesnetzagentur Excel/PDF) → `deadlines`; weather masking in detection; ENTSO-E + SMARD cross-check; agent with cited answers; monitoring feed; weekly cron enabled.
**Done when:** "which sites are behind their EEG deadline?" returns a correct, evidence-cited answer.

### Phase 3 — polish
PDF report export, Supabase auth (magic link), stub adapters for Netztransparenz/UVP/netzausbau.de/news, ESA WorldCover + Copernicus DEM enrichment, state orthophoto WMS chips, deploy notes (Fly.io/Railway backend, Vercel frontend).

## Conventions

See [CLAUDE.md](CLAUDE.md). Highlights: type hints everywhere, Pydantic models shared via workspace, pytest smoke tests per adapter (external calls mocked), ruff, small commits per feature, probe scripts before implementing uncertain APIs, stop and ask the user when credentials/accounts are needed.

## Status — 2026-06-13 (session 2)

- **Scope expanded to all generation technologies, nationwide** (was solar / BW+BY).
- **Data sourcing:** official MaStR bulk server is throttled to ~6 KB/s (server-side, not our connection) — unusable. We use the **open-mastr Zenodo snapshot** (2025-02-09, full boxed zip in `data/`, gitignored), downloaded via [scripts/download_mastr.py](scripts/download_mastr.py). Probe scripts in `scripts/probe_mastr_*.py` verified the schema (German columns; capacity in kW; `Lage=='Freifläche'` = ground-mounted; 100% geocoded).
- **Sites loaded: 5,402** — wind 2,098 farms (5,747 turbines clustered), solar 1,644, combustion 1,046, storage 273, hydro 222, biomass 104, geothermal 15. 3,768 operating / 1,619 in planning.
- **GEE validated** end-to-end on real Earth Engine (sane NDVI 0.5–0.9 / BSI / VH dB). **50-site solar pilot backfill running** (5-year, since 2021).
- **Infra note:** this network is IPv4-only; Supabase direct DB host is IPv6-only → use the **session pooler** for `db push` (`aws-0-eu-west-1.pooler.supabase.com:5432`, user `postgres.<ref>`). App traffic uses the REST API (fine).
- 13 tests pass; ruff clean.
- Next: confirm pilot timeseries → build the state machine + detection writer → evidence chips → dashboard. Then scale backfill to the "In Planung" set.
