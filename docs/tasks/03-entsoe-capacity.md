# 3. ENTSO-E: cross-border capacity, wind and solar forecasts, installed capacity

Needs `ENTSOE_API_KEY` in the cloud environment (the owner adds it there).

## Goal

1. Show **why prices split**: on each border, the flow against the capacity offered, so
   a full line is visible. (The post of 7 Oct: zones share one price until the link
   between them is full.)
2. **Forecast vs actual** wind and solar per country (day-ahead forecast against what
   came).
3. **Installed capacity per production type** from ENTSO-E, replacing Energy-Charts
   (HTTP 503 since 2026-09-24) in `reference.json`.

## Sources (probe first)

`scripts/probe_entsoe_capacity.py`, using `scripts/entsoe.py`:

- Transfer capacities: A61 (forecasted / estimated NTC), A31 (offered capacity), and for
  the Core flow-based region what is published at all. List per border what exists, at
  what resolution, and how late. Many borders have no NTC under flow-based coupling: the
  map then shows nothing for them, and the key says why.
- Wind and solar day-ahead forecast: A69 (processType A01), per country, against A75.
- Installed capacity per production type: A68 (yearly, processType A33).

## Files

- `fetch_eu_snapshot.py` / `build_eu_day.py`: add the capacity per border and slot where
  published, and the forecast per country; `fetch_eu_reference.py`: installed capacity
  from A68 (carry over the last good value per country, as now).
- **Prices keep two decimals** in the day files (`build_eu_day.py` rounds every value to
  0.1 today; prices are published to 0.01 €/MWh).
- docs/DATA_SOURCES.md: each new series and rule.

## Map

- On the flow arrows: utilisation = |flow| / capacity (computed), only where a capacity is
  published. A thin bright core on arrows above 90 %, nothing else changes. The tooltip
  gives flow, capacity and both sources.

## Panels

- Country "Now" and "7 days": forecast vs actual wind and solar (one line chart, the
  forecast dashed).
- Installed capacity card reads the new reference.

## Done-check

Build passes; the probe output lists border coverage; five capacity values and one
forecast checked against the ENTSO-E website (in the PR); the 7 Oct day rebuilt with
two-decimal prices shows 254.23 € for DE-LU at 18:45.

## Out of scope

Imbalance prices, intraday, flow-based parameters beyond what the map shows.
