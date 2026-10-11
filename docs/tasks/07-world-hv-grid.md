# 7. The rest of the world's high-voltage grid (Overture, in GitHub Actions)

## Goal

`world-hv.pmtiles` on R2 today covers Europe, the Middle East/Africa and Oceania; North
America, Asia, Africa, South America and the north timed out on Overpass. Build the whole
world's lines of 220 kV and more from Overture Maps instead, in GitHub Actions (public S3 in
us-west-2: fast from a runner, too slow from the owner's laptop).

## Probe first

`scripts/probe_overture_power.py` exists (it timed out from the laptop). Run it in the
session or a workflow run: the `base/infrastructure` theme, `subtype = 'power'`,
`class = 'power_line'`, and whether `source_tags['voltage']` survives (OSM's voltage); count
lines and km per continent; how long one continent takes.

## Files

- `scripts/fetch_world_hv_overture.py`: DuckDB over Overture's newest release → GeoJSONSeq
  with `kv` (highest voltage of the line, from the OSM tag, kV) for lines ≥ 220 kV; the same
  layer name (`hv`) and property (`kv`) the app's style reads (`frontend/src/map/style.ts`),
  so the frontend does not change.
- `.github/workflows/world-hv.yml`: switch to this script (keep the Overpass path only if
  Overture lacks voltages somewhere; say where), tippecanoe as in `us-grid.yml`, upload to
  the R2 bucket `infraatlas-data` as `grid/world-hv.pmtiles` (repo secrets
  `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`; the session triggers the workflow with
  `gh workflow run`, it never holds the token).
- docs/DATA_SOURCES.md: the new source, release, licence (ODbL via Overture), coverage.

## Done-check

The workflow run is green; the file on R2 is larger and the PR lists km of lines per
continent; the map (World stories) shows lines in the US, India, China, Brazil.
