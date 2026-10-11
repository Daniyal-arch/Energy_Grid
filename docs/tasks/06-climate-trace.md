# 6. Emissions per facility worldwide (Climate TRACE)

## Goal

Where the world's CO₂ comes from, facility by facility: power plants, steel mills, cement
plants (and oil and gas fields if the volume allows), as a world layer and cards. No key.

## Sources (probe first: `scripts/probe_climate_trace.py`)

Climate TRACE API (`https://api.climatetrace.org/`, newest version; CC BY 4.0): list the
endpoints for assets (facilities) with coordinates, sector, country, owner, and emissions per
year and month; the newest complete year; how many assets per sector; paging and limits.
Climate TRACE values are **modelled estimates** (satellites, machine learning): pass them
through and label them as such ("modelled by Climate TRACE"), like the weather model data.

## Files

- `scripts/fetch_climate_trace.py` → `frontend/public/data/eu/ctrace.json` (or several files
  per sector if one exceeds ~5 MB): per facility lon, lat, sector, country (ISO3), name,
  CO₂e of the newest full year (t), and the monthly series for the largest facilities.
  A size threshold (e.g. ≥ 0.1 Mt CO₂e a year) keeps it light; say so in the key.
- Refresh: yearly/quarterly as Climate TRACE releases, in `.github/workflows/eu-days.yml`
  (skip when the release has not changed) or its own small workflow.
- docs/DATA_SOURCES.md section.

## Map and panels

- Layer "Emissions per facility" (group "Industry & data", coverage World): dots sized by
  annual CO₂e (area ∝ tonnes), coloured by sector, calm (no glow beyond the GEM style).
- World panel and country panels: "Largest emitters" card (top 10, sector, Mt CO₂e) and the
  sum per sector in the country (computed, named).
- Hover: facility, sector, owner if given, annual and the newest month.

## Done-check

ruff, pytest, `npm run build`; three facilities checked against climatetrace.org (in the PR).
