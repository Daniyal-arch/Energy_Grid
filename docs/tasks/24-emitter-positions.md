# 24. Emitters with a position: EU ETS and UK ETS installations placed on the map

## Goal

The reported emissions per facility (dataset `emitters`, `ets.json` + EPA GHGRP) are drawn as
hexagons at every scale. Only the installations with a position can be drawn, and today few
have one:

- EU ETS: 2,234 of 9,668 stationary installations placed (Germany 78 of 1,818). Positions come
  only from the EEA industrial register, joined by the ETS identifier each country reported
  (`scripts/fetch_eu_ets.py`); most countries reported few identifiers.
- UK ETS: 747 installations, none placed (`scripts/fetch_uk_ets.py`: the registry report has no
  position, and the EEA register holds no UK site since 2020). The Great Britain dashboard's
  Emissions map is empty for this reason.

Place as many installations as published sources allow, the same way in every country, so the
Emissions map shows reported emissions consistently in the EU-27, the UK and the US.

## Sources (probe first: `scripts/probe_ets_positions.py`, show the output in the PR)

Positions only as a source publishes them. No geocoding of addresses, no positions made up from
a city or a postcode centroid (CLAUDE.md hard rule 1).

1. **The Union Registry / EUTL installation records**: check whether the installation export
   (or the EUTL account pages) carries latitude and longitude, and for how many installations
   per country.
2. **The EEA industrial register (EU Registry, Discodata)** beyond the ETS identifier: the
   permit number in other spellings (spaces, dashes, leading zeros), the installation's name
   and postcode against `ProductionInstallation` / `ProductionSite`. A match rule counts only
   when it is exact after documented normalisation; list each rule and how many it places per
   country. Ambiguous matches (two candidates) stay unplaced.
3. **UK**: the NAEI point sources (OGL v3.0; site name, operator, grid reference, CO₂ per year),
   the Environment Agency, SEPA, NRW and DAERA permit registers (site grid references by permit
   number). Join UK ETS installations by permit number or exact name and postcode; report what
   stays unplaced.
4. Any other open, licensed source of installation coordinates found while probing (national
   ETS authorities often publish installation lists with addresses and coordinates: DEHSt,
   NEa, CITEPA...). Record the licence of each.

## Files

- `scripts/fetch_eu_ets.py`, `scripts/fetch_uk_ets.py`: the new joins, each position with the
  source that gave it (a short code per row, e.g. `eea-id`, `eea-permit`, `eutl`, `naei`).
- `ets.json` keeps its schema; rows gain the position source. A `placed` count per country
  and per source in the file.
- docs/DATA_SOURCES.md: every new source, its licence, the match rules and the placed counts.

## Map and panels

Nothing new to draw: the Emissions map and the `emitters` hexagons read `ets.json`
(`lib/measures.ts` `emitters-t`). The Emissions card (components/AreaCards.tsx) says how many
installations in the area are placed and how many are listed without a position.

## Refresh

The ETS files refresh as today (yearly, after the April verification); the joins run in the
same scripts.

## Done-check

- The probe output and the placed counts per country, before and after, in the PR.
- Great Britain's Emissions map shows UK ETS installations; Germany's shows far more than 78.
- `uv run ruff check . && uv run ruff format .`, `uv run pytest`, `cd frontend && npm run build`.

## Out of scope

Modelled emissions (Climate TRACE, dataset `ctrace`) stay a separate dataset; no mixing of
modelled and reported figures in one map.
