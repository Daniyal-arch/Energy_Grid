# 11. Every generating unit in Germany (Marktstammdatenregister)

## Goal

Germany's official register of every unit (solar, wind, storage, CHP, …; 8 M+ records):
installed capacity by technology per municipality, and the large units as points. No key
(bulk download).

## Probe first (`scripts/probe_mastr.py`)

The daily bulk XML dump (Bundesnetzagentur, MaStR "Datendownload"; the `open-mastr` package
reads it): size (several GB zipped: say so before downloading, and run the download in GitHub
Actions, not the session), tables, licence (dl-de/by-2-0 expected: confirm), coordinates
(only units above a size have them; small units carry a postcode and municipality).

## Files

- `.github/workflows/mastr.yml` (monthly + dispatch): download, aggregate, commit the small
  outputs to main. `scripts/build_mastr.py` → `frontend/public/data/eu/mastr/units_large.json`
  (units ≥ 1 MW with coordinates: lon, lat, technology, MW, commissioning, status) and
  `mastr/municipalities.json` (MW per technology per Gemeinde, AGS code) with Gemeinde
  outlines from BKG VG250 (dl-de/by-2-0) simplified, or centroids if outlines are too heavy.
- docs/DATA_SOURCES.md: compare totals with ENTSO-E A68 and the panel's powerplantmatching
  note (German wind per turbine).

## Map and panels

Layer "Germany: every unit" (coverage DE): municipalities shaded by MW of the chosen
technology (solar / wind / storage) and large units as dots from zoom 6. Germany's panel:
units and MW by technology, newest additions per month.

## Done-check

ruff, pytest, `npm run build`; national totals against Bundesnetzagentur's published figures
(PR). Merge `origin/main` before opening the PR.
