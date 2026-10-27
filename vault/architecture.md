---
title: Architecture
tags: [overview]
updated: 2026-10-27
paths: [frontend/, scripts/, .github/workflows/, agent/, docs/]
---

# Architecture

An interactive, source-backed map of the world's power system (Europe and the US first). Every
number is passthrough from a named source or computed in a build script ([[rules]]).

## Parts
- **Static site** (`frontend/`): React + Vite + TypeScript, MapLibre GL (globe, land, labels,
  vector and raster tiles) with deck.gl drawn inside MapLibre's context (MapboxOverlay,
  interleaved), zustand stores, Tailwind. Built and served by Cloudflare (Workers Builds) on every
  push to `main`: https://energy-grid.infraatlas.workers.dev. See [[map-rendering]],
  [[state-and-datasets]], [[styles-and-maps-view]], [[panels-and-cards]].
- **Map files**: static JSON in `frontend/public/data/eu/` and `frontend/public/data/us/`
  (bundled with the site), live and archive files on the data branches `eu-data` and `eu-days`
  (read from raw.githubusercontent.com), geometry and lookup grids on R2 (public `pub-…r2.dev`).
  Loaders in `frontend/src/app/data.ts`. See [[pipeline-and-workflows]].
- **Scripts** (`scripts/`, Python 3.13, uv): fetch and build every file; probes
  (`scripts/probe_*.py`) before any new source.
- **Workflows** (`.github/workflows/`): live figures, the day archive, big downloads, the lake.
  They own the data branches.
- **Lake** (R2 bucket `infraatlas-raw`, prefix `lake/`): full-detail Parquet for the agent. See [[lake]].
- **Agent catalogue** (`agent/catalog/*.yaml`, 56 files): the meaning of each dataset for the agent.
- **Backend** (`backend/`, built 2026-10-27; deploy waits on AWS setup): FastAPI data service,
  LangGraph agent and MCP server on AWS Lambda. See [[agent-backend]].

## Docs
`docs/DATA_SOURCES.md` (every file and source), `docs/DATA_LAKE.md`, `docs/AGENT.md`,
`docs/VISUALIZATION.md` (the owner's map design and its state), `docs/VIDEO.md`, `docs/COVERAGE.md`,
`docs/tasks/` (cloud briefs), `PLAN.md` (phases).
