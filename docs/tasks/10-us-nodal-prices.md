# 10. US prices at every node and the markets' live queues (gridstatus)

## Goal

Thousands of US price nodes instead of six hubs, and each market's own interconnection queue
(fresher than LBNL's yearly file), using the open-source `gridstatus` library (MIT) over the
markets' public APIs.

Keys: CAISO, MISO, SPP, NYISO need none. ERCOT, PJM and ISO-NE need free accounts; each is a
cloud network secret and a GitHub secret (names in `.env.example`). A market whose key is
missing is skipped and named in the PR.

## Probe first (`scripts/probe_gridstatus.py`)

`pip install gridstatus`; per market: day-ahead LMP for all nodes for one day (row count,
node ids, whether coordinates exist), the queue (`get_interconnection_queue`) row count and
columns. Node coordinates: most markets publish none; use the markets' own node location
files where they exist (CAISO price map, ERCOT settlement point list, MISO/SPP node lists);
nodes without a published location are counted, not placed.

## Files

- `scripts/fetch_us_nodes.py` → `frontend/public/data/eu/us_nodes/<date>.json` (per placed
  node: lon, lat, market, id, hourly day-ahead price, USD/MWh, source precision); daily in
  `eu-days.yml`, 30 days kept like `usday`.
- `scripts/fetch_us_queues.py` → `frontend/public/data/us/queues_live.json` (per market:
  project, MW, type, state/county, status, queue date); weekly.
- docs/DATA_SOURCES.md sections.

## Map and panels

- "A day in the US": a layer "Node prices" (fine dots coloured by price at the clock, a
  shared scale per day, legend with the day's range; calm, no glow).
- US panel "Queue" tab: the markets' live queues next to LBNL (label which is which).

## Done-check

ruff, pytest, `npm run build`; five node prices checked against the markets' sites (PR).
Merge `origin/main` before opening the PR.
