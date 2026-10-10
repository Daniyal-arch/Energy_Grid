# 2. US grid pack

## Goal

The United States on the same map at the same quality as Europe: every power plant, the
transmission lines, every wind turbine, and the interconnection queue (what is waiting to
connect). Base for the paid "site screening" use case.

## Sources (probe first, one probe per source)

- **EIA-860M** (monthly generator inventory, public domain): operating, planned and
  retired generators of 1 MW or more with plant coordinates. Excel from eia.gov.
  `scripts/probe_eia860m.py`: newest file name, sheets, columns, row counts.
- **LBNL "Queued Up"** (interconnection queues, yearly): projects by state, county,
  type, MW, status, queue year. Check the licence and the newest edition.
- **USWTDB** (US Wind Turbine Database, USGS/LBNL/AWEA, public): every turbine with
  capacity and hub height; API or CSV.
- **Transmission lines with voltage:** probe HIFLD first (its open portal changed in
  2025: check whether the "Electric Power Transmission Lines" layer is still public). If
  it is not, use the OSM lines already in `world-hv.pmtiles` and say so; do not scrape
  restricted data.

Ask before any download over 200 MB; large files are fetched by a GitHub Actions
workflow, not in the session.

## Files

- `scripts/fetch_us_grid.py` -> `frontend/public/data/us/plants.json` (plants with
  capacity per fuel and status), `us/queue.json` (per state and type: GW active in the
  queue, by status), `us/turbines.json` (compact columns, or PMTiles on R2 if over 5 MB).
- Transmission lines as PMTiles on R2 (public bucket), built in Actions with tippecanoe,
  like `world-hv.yml`.
- docs/DATA_SOURCES.md: one section per file, every column's source.

## Map

- "Power plants" in the US use the same style as GEM plants (status filter, fuel colours);
  avoid double-drawing with GEM in the US (EIA wins there; say so in the key).
- Lines by voltage with the same colour bands as Europe's grid.
- Turbines: fine dots from zoom 5, invisible zoomed out.
- Queue: on the US states, raised like the price terrain (height = GW waiting, colour by
  the largest type), only in its own story "US interconnection queue". Calm, no motion.
- A story "US grid" with a camera over the lower 48.

## Panels

A US panel (when the camera faces the US, like the World panel): installed capacity by
fuel (EIA-860M), planned additions and retirements by year, the queue by type and state.

## Refresh

EIA-860M monthly, the queue yearly, turbines quarterly: a `us-grid.yml` workflow on a
schedule plus manual dispatch.

## Done-check

Build passes; totals checked against EIA's published national total for the same month
(in the PR); the queue total checked against the LBNL report's headline figure.

## Out of scope

Hourly CO₂, EV chargers, outages, nodal prices (later tasks).
