# 16. Wrap-up: imbalance prices, US EV fast chargers, GB and Denmark live, resource atlases

One session, five parts. Read CLAUDE.md first; its hard rules and working rules apply. Probe
before building (a `scripts/probe_*.py`, its output in the PR). Heavy downloads and anything
ENTSO-E-heavy run in GitHub Actions: a new step can run before the merge with a `push:` trigger
limited to the session's branch that commits its small outputs back to the branch; remove that
trigger before the PR. A part whose source is closed, changed or behind a login stops there and
is described in the PR; the other parts carry on. Never estimate a missing value.

Keys: `ENTSOE_API_KEY` and `EPA_API_KEY` are in the cloud environment and are repo secrets.

## A. Imbalance prices per zone (ENTSO-E A85), started on main

`scripts/build_imbalance.py` and `scripts/probe_entsoe_imbalance.py` are on main (built and probed
from the owner's laptop on 2026-10-17). What the probe found:

- A85 answers a **zip** of XML documents per area; two series per area by
  `imbalance_Price.category`: A05 (deficit) and A04 (excess). Single-price areas send equal
  series (the builder keeps one and sets `same: true`).
- No data at ENTSO-E: DE-LU (Germany's reBAP is on netztransparenz.de, not ENTSO-E), GR, BG, LT,
  ME, SE4, SK, UA-IPS. Currencies as published: PL in PLN, CZ CZK, HU HUF, RO RON.
- Italy fills A05 with 0 throughout and publishes its price in A04: the builder flags a series
  that is 0 throughout (`all_zero`) and the app must not chart it as a price.
- ENTSO-E throttles repeated full runs from one address (18 zones came back empty on a second run
  minutes after the first): run it once a day in Actions only. The builder retries 6 times and
  logs every give-up.

To do:
1. Step in `.github/workflows/eu-days.yml` after the prices step: "Imbalance prices per zone
   (ENTSO-E A85, the last 30 days)", `timeout-minutes: 15`, `continue-on-error: true`,
   `python scripts/build_imbalance.py --out store/eu || echo "imbalance failed; keeping yesterday's"`.
2. Frontend: `lib/imbalance.ts` (types of the file), loader `imbalance: archive("imbalance.json")`
   in `app/data.ts`, and an **ImbalanceCard** in `components/PriceCards.tsx` shown in `ZoneBody`
   (`ui/Panel.tsx`) after `CaptureCard`: the last 7 days at 15 minutes (deficit line; excess as a
   second line only where it differs; never a series flagged `all_zero`), and over the 30 complete
   days: average (weighted by periods published, computed), lowest, highest, periods below zero,
   each in the source's currency. Zones in `none`: one line saying ENTSO-E has no imbalance price
   for the zone (for DE-LU: published by the four TSOs on netztransparenz.de).
3. Lake: imbalance history 2015– in `scripts/build_lake_entsoe.py` / `lake-entsoe.yml` as table
   `entsoe/imbalance_price` (columns ts, zone, category, price, currency, resolution_s; partition
   zone and year; the file standard in docs/DATA_LAKE.md). Update the A85 row in DATA_LAKE.md.
4. docs/DATA_SOURCES.md section (what is passed through, what is computed, zones without data).

## B. US EV fast chargers (NREL Alternative Fuels Data Center)

- Source: AFDC station locator `alt-fuel-stations/v1.json` (`fuel_type=ELEC`, `status=E`,
  `access=public`, `country=US`, `limit=all`). NREL keys are api.data.gov keys: try the repo
  secret `EPA_API_KEY` (pass it as `NREL_API_KEY`). The host `developer.nrel.gov` is now an alias
  of `developer.nlr.gov` (NREL was renamed); use whichever resolves. If the key is refused, stop
  this part and ask the owner for a key from https://developer.nrel.gov/signup/ (document
  `NREL_API_KEY` in `.env.example`).
- Probe first (`scripts/probe_nrel_afdc.py`): count, fields, size of `limit=all`, licence/terms.
- `scripts/fetch_ev_chargers.py` → `frontend/public/data/us/ev_chargers.json`: DC fast stations as
  points `[lon, lat, DC ports, network index, open year]`; per state: stations, level 2 ports, DC
  fast ports (sums computed). Level-2-only stations are counted, not drawn. Every station with
  every field to the lake (`lake/afdc/stations`).
- Layer "EV fast chargers" (group "Industry & data", coverage US): calm dots sized by DC ports;
  hover card (name, network, ports, opened); a card in "On the map" (US total, by state, largest
  networks). Monthly refresh in `.github/workflows/us-grid.yml` (the data job).

## C. Great Britain: carbon intensity now and the next 48 hours (NESO, no key)

- Source: the NESO Carbon Intensity API (api.carbonintensity.org.uk): national intensity (actual
  where published, forecast flagged as forecast), the 48 h forecast, the generation mix, and the
  14 regional values. Probe the licence and the update cadence.
- `scripts/fetch_gb_carbon.py` → `gb_carbon.json`, run in the snapshot loop of
  `.github/workflows/eu-snapshot.yml` (onto `eu-data`, like the other live files; add the key to
  `LIVE_KEYS`).
- A card in Great Britain's country panel: intensity now (gCO2/kWh, actual or forecast as
  labelled), a 48 h line, the mix in %, and the regions as a compact list (no new map layer).

## D. Denmark every 5 minutes (Energinet Energi Data Service, no key)

- Source: api.energidataservice.dk datasets `CO2Emis` (CO2 per kWh, DK1 and DK2, 5 min) and the
  5-minute production dataset (probe the current name; e.g. `ElectricityProdex5MinRealtime`).
- `scripts/fetch_dk_live.py` → `dk_live.json` in the snapshot loop (onto `eu-data`, `LIVE_KEYS`).
- A card in Denmark's country panel: CO2 intensity now and the last 24 h per area, production by
  type now. Values as published; label "Energinet, every 5 minutes".

## E. Solar and wind resource atlases (owner-approved downloads, Actions only)

Only if the owner approved in the session prompt. Global Solar Atlas PVOUT (World Bank / Solargis,
~362 MB GeoTIFF, CC BY 4.0) and Global Wind Atlas mean wind speed at 100 m (DTU, several GB,
CC BY 4.0), downloaded and processed only in Actions:
- Raster tiles (PNG, zoom 0–7, the source's own classes, a calm palette) as PMTiles on the public
  R2 bucket (`grid/` pattern, Cloudflare from repo secrets); layers "Solar resource" and "Wind
  resource" in the Weather group with a key and the source.
- A value lookup for "Check a site": a coarse grid file (for example 0.1°) of PVOUT (kWh/kWp per
  year) and wind speed (m/s) read in `components/SiteCards.tsx` ("Around it"), labelled with the
  grid size. The full rasters as Cloud-Optimized GeoTIFF in the lake (`lake/atlas/`).

## F. Wrap-up

- PLAN.md: mark done what this session finished; keep the waiting-on-owner list (PJM key, NYISO
  bot check, Alberta, Korea, Turkey keys).
- docs/tasks/README.md: row 16.
- Before the PR: `uv run ruff check . && uv run ruff format .`, `uv run pytest`,
  `cd frontend && npm run build`; merge `origin/main` and resolve conflicts keeping both sides.
  The PR describes what the map shows now, the new files in docs/DATA_SOURCES.md, the probe
  outputs, and anything stopped.

Out of scope: a backend, the agent, alerts, new countries' live grids (keys), PJM.
