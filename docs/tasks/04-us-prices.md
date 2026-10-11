# 4. US wholesale prices (day-ahead, one trading hub per market)

## Goal

Prices in the US replay and the US live view, like Europe's: the hourly day-ahead price at
one trading hub per market, matched to the EIA region the market covers.

| Market | Hub (benchmark) | EIA region | Key |
|---|---|---|---|
| CAISO | TH_SP15_GEN-APND (SP15) | CAL | none (OASIS) |
| ERCOT | HB_HUBAVG | TEX | none (MIS public reports) |
| PJM | Western Hub | MIDA | `PJM_API_KEY` (free, apiportal.pjm.com); skip if absent |
| MISO | ILLINOIS.HUB | MIDW | none |
| SPP | SPPSOUTH_HUB | CENT | none |
| NYISO | N.Y.C. (zone J) | NY | none |
| ISO-NE | .H.INTERNAL_HUB | NE | none |

## Probe first

`scripts/probe_us_prices.py` exists. From the laptop only MISO answered (2026-10-08,
ILLINOIS.HUB at HE13 = 34.70 $/MWh; the others failed on the local network: DNS/timeouts).
Run it in the session, fix each source's URL/format until all answer, and show the output.

## Files

- `scripts/build_us_day.py`: add `"prices": {hub: {"country": region, "values": [$/MWh per
  hour]}}` to each `usday/<date>.json` (hours in the file's Eastern-Time grid; each market's
  own hour ending converted, documented). Keep the source's precision (two decimals).
- `scripts/fetch_us_prices.py` → `frontend/public/data/eu/us_prices.json` for today and
  tomorrow (day-ahead is published the day before), run from the daily archive workflow
  (`.github/workflows/eu-days.yml`, `store/eu/`).
- docs/DATA_SOURCES.md: each market, hub, hour convention, currency (USD/MWh).

## Map and panels

- "A day in the US": tower labels read "TEX 60 GW · $45" (the region's hub price at the
  clock; `frontend/src/map/build.ts` `towerLayers`, which already prints Europe's price from
  the price terrain). The "This hour" card (`UsDayNow` in `frontend/src/ui/Panel.tsx`) lists
  the hubs and prices. Captions may add `price_low`/`price_high` for the US (USD).
- US live: today's price at the current hour per hub in the US panel's Live tab.
- Label everything in $/MWh with the hub name; no average across hubs unless named
  ("median of 7 hubs").

## Done-check

ruff, pytest (a test for the hub-to-region rows), `npm run build`; three hub prices checked
against the markets' own websites for the same hour (in the PR).
