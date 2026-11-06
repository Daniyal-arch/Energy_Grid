---
title: Product features
tags: [product, frontend, backend]
updated: 2026-11-06
paths: [docs/product/, backend/tools/report.py, backend/tools/feeds.py, backend/app/main.py, frontend/src/ui/ComparePage.tsx, frontend/src/ui/Embed.tsx, frontend/src/ui/Downloads.tsx, frontend/src/ui/CoverageExplorer.tsx, scripts/weekly_brief.py, scripts/build_downloads.py]
---

# Product features (brief 30 Track 6)

MVPs, each with a spec in `docs/product/<name>.md`. Built on [[instant-answers]] and the
coverage registry ([[coverage-and-gaps]]).

- **Site report**: `GET /api/report?lon&lat&radius_km&task` (printable HTML, Save as PDF) and
  `/api/report.json`; the task skill's checklist (`agent/skills/*-siting`, ...) in order, each
  step with computed tables and the coverage cells it names; no score. `backend/tools/report.py`.
- **Watchlists and feeds**: `GET /api/feed/{area}.json|.rss`; one profile snapshot a day per
  area in the store (`agent/feeds/<key>/`), changes = rows that differ. The area card's
  "Watch this area" keeps watched names and last-visit dates in localStorage
  (`atlas.watch`) and lists what changed since then.
- **Compare**: `?compare=France;Germany` (2-6 places; `?compare=1` stays the Maps view),
  `frontend/src/ui/ComparePage.tsx` over `/api/quick/compare`.
- **Embeds**: `?embed=1` (map, compact key, sources line, "Open in InfraAtlas"); embed code in
  the Dashboards menu (`frontend/src/ui/Embed.tsx`, `EMBED` flag in `store.ts`).
- **Weekly brief**: `scripts/weekly_brief.py` (templates over prices, queues, outages, records;
  no model) to `frontend/public/brief/latest.{json,html}`, `weekly-brief.yml` (Wednesdays).
- **Data API**: OpenAPI at `/api/openapi.json`, `/api/docs`; `X-API-Key` budgets
  (`DATA_API_KEYS`) and per-address budgets on `DATA_ROUTES` (`backend/app/main.py`).
- **Download centre**: `?downloads` (`frontend/src/ui/Downloads.tsx` over
  `public/data/downloads.json` from `scripts/build_downloads.py`); only redistributable
  licences get links; re-run the script when datasets change.
- **Coverage explorer**: `?coverage`, the registry as a matrix with each cell's evidence;
  absent neighbour cells read "not assessed".
