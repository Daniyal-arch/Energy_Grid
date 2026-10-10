# 1. Europe's gas flows (ENTSOG)

## Goal

A gas version of the power-flow map: how much gas crosses each border and enters Europe
(Norway, North Africa, Azerbaijan, TurkStream, LNG), per gas day, and where it goes.
Story for LinkedIn: "Where Europe's gas comes from, today".

## Sources (probe first)

- ENTSOG Transparency Platform API, no key: `https://transparency.entsog.eu/api/v1/`.
  Write `scripts/probe_entsog.py` and show its output before building. Find out:
  - physical flows per point and direction, daily (`operationaldatas`, indicator
    "Physical Flow", periodType day), units (kWh/d) and how late the newest gas day is;
  - the point list (`points` / `interconnections` / `connectionpoints`): which carry
    coordinates, the countries / balancing zones on each side, and whether a point is a
    border, a production entry, an LNG terminal or a storage;
  - any country-level aggregate (`aggregatedData`) and whether its sums match the
    points;
  - rate limits and paging (`limit`, `offset`).
- Already in the repo: GEM gas pipelines (`gem/gas_pipelines.json`), GIE storage
  (`gas.json`, `dossier.json`), LNG send-out in `dossier.json`.

## Files

- `scripts/fetch_entsog.py` -> `frontend/public/data/eu/gas_flows.json`: for the newest
  complete gas day and the 30 days before it, per pair of countries (or entry source)
  the net flow in GWh/d, with each direction as published; the points summed into each
  pair listed. Sums are computed; values otherwise passthrough.
- docs/DATA_SOURCES.md: a section for the file, the rules (which indicator, which
  points, how pairs are summed, the gas-day definition 06:00-06:00 UTC+1).

## Map

- Layer "Gas flows" (group "Gas, oil & coal", coverage Europe, live mode): amber
  chevron arcs between country anchors, like the power flows (`FlowArrowLayer`), width by
  GWh/d, labels from a threshold. Entry flows start at the source (Norwegian shelf,
  Algeria, Libya, Azerbaijan, Turkey, LNG terminals) placed as fixed map points, named
  "placed for reading" in the source note.
- Calm: no glow beyond what power flows use; one colour family (amber), distinct from
  the power flows' cyan.
- Key in the Layers panel and in the on-map legend (`frontend/src/ui/MapLegend.tsx`).

## Panels

- Country panel, tab "Gas & LNG": a card "Gas in and out" (newest gas day, 30-day line).
- EU panel: "Where Europe's gas comes from" (entry sources, newest day and 30-day sums).

## Refresh

Add the fetch to `.github/workflows/eu-days.yml` (daily). It writes to the `eu-days`
branch through the workflow, never by hand.

## Done-check

`ruff`, `pytest`, `npm run build` pass; the probe output is in the PR; the layer draws
the newest gas day; three numbers in the PR are checked against the ENTSOG website for
the same point and day.

## Out of scope

Gas prices, storage changes (already shown), capacity bookings.
