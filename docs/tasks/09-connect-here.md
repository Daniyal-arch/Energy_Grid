# 9. "Connect here?": grid capacity and connection queues in Great Britain, the Netherlands, Spain

## Goal

Where a new plant, battery or data centre can still connect to the grid, from the grid
operators' own published data. One layer, "Grid capacity" (group "Power grid"), and cards.
No keys.

## Sources (probe each first: `scripts/probe_connect_here.py`)

- **GB, NESO TEC register** (twice weekly; CKAN API `api.neso.energy`, resource
  `17becbab-e3e8-473f-b303-3806f43a6a10`; NESO Open Data Licence): every project holding
  transmission capacity: name, MW, technology, connection site, date, status, Gate 1/2.
  Connection sites need coordinates: join to NESO's or the transmission owners' published
  substation lists by name/code (no geocoding by guesswork; count what cannot be placed).
- **Netherlands, Netbeheer Nederland capaciteitskaart**: feed-in and offtake capacity by
  area, TenneT HV layer (data export; information model 2.1 at
  modellen.netbeheernederland.nl). Find the export URL and format; else the operators'
  PDOK WFS (Liander and others).
- **Spain, REE/CNMC capacity at each transmission node** (generation access capacity monthly
  since 2021; demand capacity maps since Feb 2026): free MW per node.

## Files

`scripts/fetch_connect_here.py` → `frontend/public/data/eu/connect_gb.json`,
`connect_nl.json`, `connect_es.json` (or one file with a `country` field); weekly or monthly
refresh in `.github/workflows/eu-days.yml`. docs/DATA_SOURCES.md sections.

## Map and panels

- GB: connection sites as circles sized by MW in the queue, coloured by technology; NL: areas
  shaded by remaining capacity (feed-in / offtake switch in the legend); ES: nodes sized by
  free MW. Calm; keys compact; every value names its operator and date.
- Country panel card "Connecting to the grid" (GB: MW by technology and year; NL: share of
  area congested; ES: free MW at the largest nodes).

## Done-check

ruff, pytest, `npm run build`; three values checked against the operators' own pages (PR).
Before opening the PR, merge `origin/main` into the branch and resolve conflicts.
