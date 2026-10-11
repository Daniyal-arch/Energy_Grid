# 5. US fossil plants hour by hour (EPA CAMPD)

Needs `EPA_API_KEY` in the cloud environment (free: https://api.data.gov/signup/).

## Goal

The US equivalent of Europe's "Plants through a day": every fossil unit of 25 MW and more,
its hourly gross load (MW) and CO₂, as glowing discs on the US replay; CO₂ per region and hour
in the "This hour" card.

## Probe first (`scripts/probe_epa_campd.py`)

EPA Clean Air Markets (CAMPD) API, `https://api.epa.gov/easey/`:
- hourly apportioned emissions (`streaming-services/emissions/apportioned/hourly`): gross
  load, CO₂ mass per unit and hour; how far back the newest published hour is (CAMPD data
  are submitted quarterly, so the newest days may be months old: report the lag);
- facility attributes with latitude/longitude (`facilities-mgmt` or `streaming-services/facilities/attributes`);
- rate limits and paging.

## Files

- `scripts/build_us_units.py` → `frontend/public/data/eu/usunits/<date>.json` in the same
  shape as `units/<date>.json` (`UnitOutputFile` in `frontend/src/app/types.ts`), so the
  existing "Plant output" layer draws it: plants (facility), fuel, capacity (CAMPD's
  `maxHourlyHIRate` is not capacity: use EIA-860M's nameplate via the ORIS/plant id from
  `frontend/public/data/us/plants.json`, or leave the ring out), hourly MW on the day's
  Eastern-Time grid, plus `co2_t` per plant and hour.
- Build the newest days CAMPD has; a story "US fossil plants through a day" (United States
  section) opens on the newest one (`dayRegion: "us"` with these days; extend `build_us_day.py`
  for those dates if the replay has no day file for them).
- docs/DATA_SOURCES.md section; `.github/workflows/eu-days.yml` step with the
  `EPA_API_KEY` repo secret (the owner adds it in GitHub too).

## Map and panels

Reuse `plantOutputLayers` (`frontend/src/map/build.ts`) for the US files; the tooltip adds
CO₂ t/h. The "This hour" card: CO₂ of the fossil units summed per region (computed, named).

## Done-check

ruff, pytest, `npm run build`; one facility's hour checked against CAMPD's own data
download (in the PR).
