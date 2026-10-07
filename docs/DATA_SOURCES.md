# Data sources

Every file the app reads lives in `frontend/public/data/eu/` and is built by a script
in `scripts/`. Values are passthrough from the source unless a row says otherwise.

## Static layers (`scripts/fetch_eu_energy.py` → `scripts/build_eu_grid.py`)

| File | Records | Source |
|---|---:|---|
| `grid.json` | 9,162 lines >= 220 kV, 39 HVDC links, 6,863 substations | PyPSA-Eur prebuilt network from OpenStreetMap ([Zenodo 18619025](https://zenodo.org/records/18619025)), ODbL |
| `plants.json` | 7,838 operating units >= 20 MW | powerplantmatching (PyPSA). One threshold for all countries, because the German input is unit-level (MaStR); German wind is listed per turbine, so it falls under the cut at continent scale |
| `plants/<ISO>.json` | 61,872 units >= 1 MW | powerplantmatching, loaded when a country is focused (columns from 10 MW, flat dots below; "Beams & fields" sums units under 200 MW per 24 km hexagon in the browser and labels it so) |
| `gas.json` | 4,840 pipe segments, 29 LNG, 216 storages | SciGRID_gas IGGIELGN (2021, [Zenodo 4767098](https://zenodo.org/records/4767098)), CC BY 4.0; clipped to the mapped countries; capacities only where the dataset marks them as not estimated. Predates the 2022+ German LNG terminals |
| `countries.json` | 35 countries: land, coast, borders | Eurostat GISCO countries 1:20M (2024); overseas territories dropped |
| `world.json` | land of all other countries | Eurostat GISCO countries 1:20M, coarse outlines for the globe's base; no data shown on them |

```sh
uv run python scripts/fetch_eu_energy.py   # ~50 MB into data/eu/ (gitignored)
uv run python scripts/build_eu_grid.py
```

## Live figures (`scripts/fetch_eu_snapshot.py`, `scripts/fetch_eu_reference.py`)

Since 2026-10-05 the time series come straight from the **ENTSO-E Transparency
Platform** (`scripts/entsoe.py`, needs `ENTSOE_API_KEY`). Energy-Charts, which
republished the same ENTSO-E data, has answered HTTP 503 ("No server is available")
since 2026-09-24. Probes: `scripts/probe_entsoe_core.py`, `scripts/probe_entsoe_coverage.py`,
`scripts/probe_entsoe_italy.py`.

| File | Records | Source |
|---|---:|---|
| `flows.json` | 73 borders | ENTSO-E A11 physical flows, both directions per border; net flow = one direction minus the other (computed). Newest measured 15-min value per border, plus 24 h of 15-min values for the replay |
| `stats.json` | 29 countries + EU, 43 price zones | ENTSO-E A65 actual total load and A75 actual generation per production type per country; A44 day-ahead price per bidding zone |
| `reference.json` | per country | Energy-Charts `/installed_power` (newest year with values, fetched before the outage) and ENTSO-E A72 hydro reservoir energy (newest week, same week a year earlier) |
| `dossier.json` | gas storage: EU + 19 countries; Ember: 36 countries | GIE AGSI+ daily gas storage (fill % of working gas volume, TWh, trend), last ~400 days; Ember yearly electricity data (CC BY 4.0): generation by source since 2000, published renewable share and carbon intensity of generation. `scripts/fetch_eu_dossier.py` (AGSI_API_KEY, EMBER_API_KEY) |

**Rules applied to ENTSO-E data** (values are never changed, only grouped, summed or
skipped):

- **Resolution:** every series is placed on a 15-min grid; a 30- or 60-min value fills
  each 15-min slot it covers. A03 curves (a point holds until the next one) are expanded.
- **Day-ahead price:** where a zone has several A44 series (EXAA for DE-LU and AT,
  Spain's intraday auctions), the coupled day-ahead auction is used: the series
  without a classification sequence, else sequence 1. The probe showed DE-LU
  sequence 1 tracking NL and FR, and AT sequence 1 tracking SI.
- **Generation:** only generation series (`inBiddingZone`); consumption series such as
  pumping and battery charging are left out. Grouped by fuel as before.
- **Renewable share of generation (computed):** biomass, geothermal, hydro run-of-river,
  hydro reservoir, marine, other renewable, solar and wind, divided by all generation
  types reported for the interval. Pumped storage and waste count as not renewable.
- **Newest interval:** the newest 15-min interval in which the country's load and every
  reporting type have a value. A type silent for 4 hours counts as not reporting:
  Italy, for example, sends no coal values while its coal units are off. An interval
  whose load or total generation is below 60 % of the highest value of the 2 hours
  before is still arriving in parts, so the snapshot steps back past it. Italy, for
  example, publishes zone by zone over several hours. Each country card shows its own
  interval time.
- **EU (computed):** the sum over the EU member states on the map that have data, at the
  newest interval where every one of them is complete; the card names how many members
  were summed. Cyprus and Malta are not mapped.
- **Coverage gaps:** ENTSO-E has no load or generation for GB (Elexon fills it), UA, MD and XK, no
  generation for MK, and Romania's data arrives more than two days late. There are no
  flows on MD–RO, RO–UA, RS–XK and MK–XK (GB–DK comes from Elexon). There are no prices for IE, BA, XK and MD.

**Great Britain** (`scripts/gb.py`, Elexon Insights API, no key): ENTSO-E has no GB load or
generation since Brexit. Generation by fuel comes from `FUELINST`, every 5 minutes, for
transmission-connected units; the reading at the start of each quarter-hour is used.
Demand is the half-hourly initial national demand outturn, filling both quarters.
Rooftop solar and small wind are not metered at this level, so GB's renewable share is
computed over transmission-connected generation. Border flows also come from `FUELINST`
(positive = import into GB). Each border is the sum of its links (computed):
- GB–FR = IFA + IFA2 + ElecLink
- GB–IE = East-West + Greenlink
- GB–NL = BritNed, GB–BE = Nemo, GB–NO = North Sea Link, GB–DK = Viking

These replace ENTSO-E's GB borders. Moyle (Scotland to Northern Ireland) is inside the
UK on this map and is not drawn.

**Plants offline** (`scripts/fetch_outages.py`, `outages.json`): ENTSO-E A80 unavailability
of generation units per bidding zone. Each request returns a zip of outage documents.
Units of 100 MW and more must report.
- The newest revision of each document is used; cancelled (A09) and withdrawn (A13)
  ones are left out.
- Offline now = nominal power − available capacity at this moment (computed); units
  with less than 1 MW offline are left out.
- Totals per zone, country and Europe are sums of the units (computed). "Planned" (A53)
  and "forced" (A54) are as reported.
- A unit reporting more than 2,000 MW nominal is left out as mis-reported, because no
  single generating unit in Europe is that large. Italy's operator, for example, sends
  kW labelled as MW. The number left out is shown.
- The units carry no coordinates, and powerplantmatching has almost no EIC codes to
  join on (26 of 165,064), so outages are shown per country and listed, never placed
  on a plant.

`.github/workflows/eu-snapshot.yml` refreshes these every 30 min onto the `eu-data`
branch; the app reads that copy from raw.githubusercontent.com and falls back to the
bundled one (newer wins). It needs the repo secret `ENTSOE_API_KEY`.

## One day for the time-lapse (`scripts/build_eu_day.py`)

| File | Records | Source |
|---|---:|---|
| `day/<YYYY-MM-DD>.json` | 96 slots (15 min) of a local day (Europe/Berlin) | ENTSO-E A44 prices per zone, A65 load and A75 generation per country, A11 flows per border, with the rules above; EU = per-slot sum over the member states with data (`eu.sum_of`). Days before 2026-10 came from Energy-Charts (EU hourly) |
| `day/index.json` | list of built days | — (`?day=latest` opens the newest) |
| `week/<ISO>.json`, `week/EU.json` | newest 7 built days per country | the day files' values concatenated, unchanged (load, renewable share, generation by source, prices of the country's zones); written by `build_eu_day.py` with every archive run, or `--weeks-only` |
| `day/<date>.json` → `highlights` | ~9 key moments per day | computed by `scripts/day_highlights.py` from the same file: min/max of EU load, solar, wind, gas; lowest/highest zone price; largest border flow; highest renewable share at the solar peak. The captions only word these values |

**Rolling archive:** `.github/workflows/eu-days.yml` runs every morning
at 07:23 UTC (`build_eu_day.py --recent 30`): it builds yesterday, rebuilds the two newest days
for late corrections and drops days older than 30, on the `eu-days` branch. All
missing days are fetched in one window (one request per series), so a 30-day
backfill costs about as much as one day. The app merges that archive with the days
bundled in `frontend/public/data/eu/day/` and offers them in a date picker.

The time-lapse clock shows the market's own time (CET/CEST) of the slot on screen.
The "price range, all zones" chart is the lowest and highest zone price per slot.

## Prices tab (`scripts/build_prices.py`)

| File | Records | Source |
|---|---:|---|
| `prices.json` | 43 bidding zones | ENTSO-E A44 day-ahead prices (the coupled auction, as above) and A75 actual solar (B16) and wind (B18 offshore + B19 onshore) generation per bidding zone, over the last twelve full calendar months |

Computed in the build script, over the last twelve **full** calendar months:

- **Average price:** the mean of all 15-min prices (hourly zones fill all four quarters).
- **Hours below zero:** the number of 15-min intervals with a negative price × 0.25 h,
  in total and per month.
- **Lowest / highest:** the extreme 15-min price and its interval (passthrough).
- **Capture price:** Σ(price × output) / Σ(output) over the intervals that have both,
  for solar and for wind. This is what a MWh of that source earned on average.
  **Capture rate:** capture price / average price. The TWh behind each weighting are
  shown. Solar is missing for ME, NO2–NO5 and RS, and wind for AL and NO5: ENTSO-E has
  no generation there. UA has no prices in EUR.
- **Price by time of day:** the average of the prices in each local hour of the day
  (CET/CEST), per month and per season (winter Dec-Feb, spring Mar-May, summer Jun-Aug,
  autumn Sep-Nov of the twelve months).

Zone markers for countries with several zones (DK, IT, NO, SE) are placed for reading,
not at an official zone centre. The `eu-days` workflow checks daily and rebuilds the file
when a new month is complete (on the `eu-days` branch; the app prefers that copy when
it is newer).

## LNG send-out (`scripts/fetch_eu_dossier.py`, in `dossier.json`)

GIE ALSI (same key as AGSI+), daily for the EU and the 12 countries with terminals (BE,
DE, ES, FI, FR, GR, HR, IT, LT, NL, PL, PT), last ~400 days, passthrough:
- `sendOut`: LNG regasified into the grid, GWh/day
- `dtrs`: declared total reference send-out, the terminals' declared send-out
  capacity, GWh/day
- `inventory.gwh`: LNG in tanks

## World tab (`scripts/fetch_world.py`, `scripts/fetch_aemo.py`)

| File | Records | Source |
|---|---:|---|
| `world_stats.json` | 216 countries + world, 2000-2024 | World Bank WDI `EG.ELC.ACCS.ZS`, access to electricity (% of population), CC BY 4.0, as published. The map colours each country by its newest year (the tooltip names it) |
| `datacentres.json` | 4,500 sites | OpenStreetMap (ODbL) via Overpass: `telecom=data_center` or `building=data_center`, one point per site (ways and relations at their centre; points sharing a 3-decimal position count once). Countries assigned with Eurostat GISCO outlines (computed): 4,434 fall inside one. A mapped subset: counts follow mapping effort, not capacity |
| `aemo.json` | 5 regions, 6 interconnectors | AEMO's public NEM summary, the newest 5-minute dispatch: price (AUD/MWh), total demand, net interchange, scheduled and semi-scheduled generation per region, interconnector flows with AEMO's sign (positive = from the first region in the name). Refreshed with every snapshot run. Region markers are placed for reading |
| `us.json` | 13 EIA regions + Lower 48 | EIA-930 Hourly Electric Grid Monitor via EIA API v2 (`EIA_API_KEY`, public domain), `scripts/fetch_us.py`: hourly demand (D), net generation (NG), total interchange (TI, positive = net export), generation by fuel, and the flow between regions and to Canada and Mexico. Each value keeps its own hour: demand is about 1 h behind, generation and the mix about a day, flows about two days (`scripts/probe_eia.py`). Fuels grouped like the rest of the app; storage is negative while charging. Flows: the newest hour in which every region pair has a value, one direction per pair (the other side's report sign-flipped), EIA's sign (positive = from the first region to the second). Refreshed with every snapshot run. Region markers are placed for reading |

Renewable share in the World country card: Ember yearly data (`transition.json`), the
newest year with a figure.

## Wind layer (`scripts/fetch_wind.py`)

| File | Records | Source |
|---|---:|---|
| `wind.json` | 30 hours (6 back, 24 ahead) x 720 points | Open-Meteo forecast API (best-match weather models, CC BY 4.0, free for non-commercial use): hourly `wind_speed_100m` and `wind_direction_100m`, i.e. at wind-turbine hub height, on a 2-degree grid over lon -25..45, lat 34..72. Model values, not measurements |
| `wind/<YYYY-MM-DD>.json` | the hours of one local day x 720 points | the same, for the archive days (one request per batch over the whole window; on the `eu-days` branch, the newest days bundled) |

Values are passthrough (speed in 0.1 m/s, direction in degrees, where the wind blows
from). The particles on the map move through a field interpolated between grid points
and between hours, for drawing only; the legend names it as model data. Open-Meteo
counts one call per location (600 a minute, 10,000 a day), so the grid goes in two
batches a minute apart; a 30-day archive costs about as much as one day.

## Transition tab (`scripts/fetch_transition.py`)

| File | Records | Source |
|---|---:|---|
| `transition.json` | 209 countries + 8 aggregates, 2000-2025 | Ember yearly electricity data (CC BY 4.0), two bulk requests: generation by source (TWh), published shares of generation (renewables, wind and solar, coal), published total generation, carbon intensity of generation. About half of the countries have no 2025 figures yet; they are drawn grey for 2025 |
| `monthly.json` | 90 countries and aggregates, last 24 months | Ember monthly electricity data (CC BY 4.0), the same three published shares per month (renewables, wind and solar, coal); shown in the World tab's country card |
| `world.json` | outlines + ISO alpha-3 | Eurostat GISCO 1:20M (coarse), the code joins Ember's entity code |

The ranking in World view lists the 30 countries with the largest published total
generation in the year shown.

## Notes

- ENTSO-E allows 400 requests a minute; the scripts ask four at a time. A full snapshot
  (~270 requests) took about a minute on 2026-10-05; single answers range from 0.3 s
  to 50 s.
- Energy-Charts answers 429 to bursts. `scripts/fetch_eu_reference.py` still asks it
  one request at a time for installed capacity.
