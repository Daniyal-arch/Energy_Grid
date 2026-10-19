# Data sources

Every file the app reads lives in `frontend/public/data/eu/` (the US grid pack in
`frontend/public/data/us/`) and is built by a script in `scripts/`. Values are passthrough
from the source unless a row says otherwise.

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
| `capacity.json` | ~31 country borders, today and tomorrow (15 min) | `scripts/fetch_eu_capacity.py`: ENTSO-E A61 forecasted transfer capacity (day-ahead, contract type A01) per bidding-zone border and direction, else A31 offered capacity of the day-ahead implicit auction; a country border is the sum of its zone borders where all have a value (computed). Borders inside the Core flow-based region (Central Europe) are left out: their limits are set jointly and an A61 figure there (e.g. 0 MW DE>NL) is not the auction's limit; the Nordic flow-based borders publish neither. Probe: `scripts/probe_entsoe_capacity.py`. The flow arrows draw a bright core where the flow is 90 % or more of the capacity in its direction (computed) |
| `reference.json` | per country | ENTSO-E A68 installed capacity per production type (processType A33; this year, else last year; grouped by fuel), as each grid operator reports it: some count only part of small rooftop solar (Italy: 11.9 GW). A country ENTSO-E has nothing for (GB, UA) keeps its Energy-Charts figures from before the 2026-09-24 outage, named in its `source`. ENTSO-E A72 hydro reservoir energy (newest week, same week a year earlier) |
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
- **Prices on the map and in the EU card (computed in the app):** the EU card's "Price
  now" is the median of the bidding zones' day-ahead prices at the clock, with the
  number of zones named. With the price colour, the map shows under a country's name its
  zone's price, or the lowest–highest of its zones. The Prices layer
  (`frontend/src/map/priceTerrain.ts`) raises each country as a low slab: its height is
  its zone's price, or the median of its zones (computed), 100 €/MWh standing 50 km; its
  colour places that price between the lowest (from 0) and highest zone price of the
  replayed day (live: of the snapshot), named in the key; below zero lies flat in cyan. In 24 h the generation towers stand on the blocks
  and the flows arc from block to block. Between two 15-min values the height glides
  (drawing only, as the towers do); labels and the hover card (every zone's own price)
  show the slot's value.
- **Reporting errors left out** (`scripts/entsoe.py`, `drop_implausible`): a load value
  above twice the country's installed capacity, or one production type above all of it,
  is cleared (null) and counted in `left_out`. Installed capacity is the bundled
  `reference.json` (all types); a country without it gets a 150 GW limit, above any
  European country's record load. Example: Bulgaria, 2026-10-06 01:00–02:00 UTC, reported
  254 GW of coal and 256 GW of load against 18 GW installed (its usual: about 1.5 GW and
  3.5 GW). The rule only removes values; nothing is filled in.
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
| `day/<YYYY-MM-DD>.json` | 96 slots (15 min) of a local day (Europe/Berlin) | ENTSO-E A44 prices per zone (EUR/MWh, the source's two decimals; MW one decimal), A69 day-ahead wind and solar forecast per country (`forecast`: wind = offshore + onshore; from 2026-10-11), the transfer capacity per border as in `capacity.json` (`capacity_ab`, `capacity_ba`), A65 load and A75 generation per country, A11 flows per border, with the rules above; EU = per-slot sum over the member states with data (`eu.sum_of`). Days before 2026-10 came from Energy-Charts (EU hourly) |
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

## A day in the US (`scripts/build_us_day.py`, `usday/<date>.json`)

| File | Records | Source |
|---|---:|---|
| `usday/<YYYY-MM-DD>.json` | 13 EIA regions + the Lower 48, 24 hours (23/25 with DST) | EIA-930 Hourly Electric Grid Monitor via EIA API v2 (`EIA_API_KEY`, public domain), for a local day in Eastern Time: `region-data` demand (D), `fuel-type-data` generation by fuel (grouped as in `us.json`), `interchange-data` flows between regions and to Canada and Mexico |
| `usday/index.json` | days built | — |

- Same shape as the Europe day files, so the towers, flows, clock and captions replay it:
  `countries` are the regions, `eu` holds the Lower 48 as EIA reports it (respondent US48),
  `borders` the region pairs (one direction per pair, the other side's report sign-flipped,
  as in `us.json`), `names` EIA's region names.
- Computed: the renewable share of generation (solar + wind + hydro over every fuel's
  positive output in the hour) and the key moments (`scripts/day_highlights.py`; the price
  captions name the cheapest and dearest hub-hour of the day at the hub's own $/MWh, `usd`).
- `prices`: the day-ahead price at one trading hub per market (next section), keyed by hub,
  `{"country": EIA region, "market", "name", "values": [$/MWh per hour of the file]}`.
  `build_us_day.py --prices-only` adds them to days built before (EIA values untouched).
- Fuel-type data arrive about a day late and interchange about two, so the newest day is three
  days back; the daily archive run builds the missing days and rebuilds the two newest.
- On the map, 1 GW stands 7 km tall (half of Europe's scale: the regions are larger).

## US day-ahead prices (`scripts/fetch_us_prices.py`, `us_prices.json`, `usday` `prices`)

| Market | Hub (benchmark) | EIA region | Source (public, no key unless named) | Market hour → file hour |
|---|---|---|---|---|
| CAISO | `TH_SP15_GEN-APND` (SP15) | CAL | OASIS `PRC_LMP`, `market_run_id=DAM`, `version=12`, zip of CSV, `LMP_TYPE=LMP` | `INTERVALSTARTTIME_GMT` (UTC) |
| ERCOT | `HB_HUBAVG` | TEX | MIS public report 12331 (DAM Settlement Point Prices), the file posted the day before delivery | hour ending, Central prevailing time; `DSTFlag=Y` is the repeated autumn hour |
| PJM | Western Hub (pnode 51288) | MIDA | Data Miner 2 `da_hrl_lmps`, `total_lmp_da` (`PJM_API_KEY`, header `Ocp-Apim-Subscription-Key`); skipped when the API answers 401 | `datetime_beginning_utc` |
| MISO | `ILLINOIS.HUB` | MIDW | market reports `<YYYYMMDD>_da_expost_lmp.csv`, row `LMP` | hour ending 1–24, Eastern Standard Time all year (MISO's market clock) |
| SPP | `SPPSOUTH_HUB` | CENT | portal file browser `da-lmp-by-settlement-location`, `By_Day/DA-LMP-SL-<YYYYMMDD>0100.csv`, column `LMP` | `GMTIntervalEnd` minus one hour (UTC) |
| NYISO | `N.Y.C.` (zone J) | NY | `damlbmp/<YYYYMMDD>damlbmp_zone.csv`, `LBMP ($/MWHr)` | hour beginning, Eastern prevailing time (the repeated autumn hour appears twice) |
| ISO-NE | `.H.INTERNAL_HUB` | NE | `histRpts/da-lmp/WW_DALMP_ISO_<YYYYMMDD>.csv`, column Locational Marginal Price | hour ending, Eastern prevailing time (`02X` is the repeated autumn hour) |

- Currency and unit: USD/MWh, the hub's total LMP (energy + congestion + losses), rounded to
  two decimals (CAISO serves five, SPP four, the others two). Passthrough otherwise.
- Hours: for the four local clocks the n-th hour of a market day starts n−1 hours after that
  day's local midnight, which handles 23- and 25-hour days. The western markets' days begin
  after Eastern midnight, so one Eastern day takes hours from two of their market days.
- `us_prices.json`: today and tomorrow in Eastern Time (`days[].prices`, same shape as in the
  day files); tomorrow fills in as the markets publish it (early afternoon the day before).
  Refreshed by the daily archive run (`eu-days`, `eu/us_prices.json`).
- On screen: "A day in the US" tower labels read "TEX 60 GW · $45" (the region's hub at the
  clock, rounded to the dollar); the "This hour" card and the US Live tab list each hub with
  its market and price to the cent. One hub per market, never averaged.

## Output per plant (`scripts/build_eu_units.py`, `units/<date>.json`)

| File | Records | Source |
|---|---:|---|
| `units/<YYYY-MM-DD>.json` | ~1,300 units in ~600 plants, 96 slots | ENTSO-E Transparency A73 "actual generation per generation unit" (processType A16, units of 100 MW and more), one request per country area and local day; Germany per control area (50Hertz, Amprion, TenneT DE, TransnetBW). Probe: `scripts/probe_unit_output.py` |
| `units/index.json` | days built, and the complete ones | a day is complete when Germany's four control areas, France, Spain, Poland, Czechia and the Netherlands have all reported |

- **Placement:** the unit's EIC code (as ENTSO-E reports it) looked up in the JRC Open
  Power Plants Database 1.0 (JRC-PPDB-OPEN, CC BY 4.0, Zenodo 3574566, `JRC_OPEN_UNITS.csv`,
  `eic_g`), which gives the coordinates, the plant (`eic_p`, `name_p`) and the unit's
  capacity (`capacity_g`). About 84 % of the units are placed; the rest are counted per
  country and not drawn. The JRC file dates from 2019: units built since are not placed,
  and a plant's capacity can differ from today's (a few plants report more output than it).
- **Values:** passthrough MW, on the day's 15-min slots like the day files (hourly series fill
  their four slots). Computed: a plant's units summed per slot, its capacity as the sum of
  its units' JRC capacities, its fuel as that of its largest unit, the card's total and the
  hover card's share of capacity. Between two slots the disc on the map glides (drawing only).
- **Publication:** Germany, the Nordic countries, Austria and Switzerland publish about five
  days late; Italy, Denmark, Great Britain and Croatia publish no output per unit. The daily
  archive run rebuilds the last 8 days so late publications fill in; the story "Plants
  through a day" opens on the newest complete day.

## US fossil plants hour by hour (`scripts/build_us_units.py`, `usunits/<date>.json`)

| File | Records | Source |
|---|---:|---|
| `usunits/<YYYY-MM-DD>.json` | ~1,260 plants (~3,800 units), 24 hours of an Eastern-Time day | EPA Clean Air Markets Program Data (CAMPD API, `api.epa.gov/easey`, `EPA_API_KEY`, public domain): `streaming-services/emissions/apportioned/hourly` (per unit and hour: gross load, CO₂ mass, operating time) and `streaming-services/facilities/attributes` (coordinates, primary fuel, the generators each unit drives with their nameplate MW). Regions: EIA-860M (the month `us/plants.json` was built from, "Balancing Authority Code" per plant) and the EIA-930 reference tables (BA → region). Probe: `scripts/probe_epa_campd.py` |
| `usunits/index.json` | days built | — |

Same shape as `units/<date>.json` (Europe), so the "Plant output" layer draws it on the US
replay, plus `co2_t` (tonnes per plant and hour).

- **Units:** those of EPA's emission-trading programmes (Acid Rain, CSAPR...): fossil
  units over 25 MW. Units that drive a generator or report gross load are kept; industrial
  boilers reporting only steam load are left out.
- **Clock:** CAMPD's `date` + `hour` are the facility's local standard time all year (the
  probe: the hour 2:00 exists on the spring DST day; PUDL converts the same data with each
  plant's January offset). The plant's time zone comes from its coordinates (`tzfpy`), its
  standard offset turns the hour into UTC, and the hour is placed on the Eastern-Time day of
  the US replay (00:00–24:00 EDT/EST). The day's file reads CAMPD's local day and the one
  before (the West's evening); in winter Puerto Rico's (AST) last Eastern hour falls on its
  next local day and stays null.
- **Gross load:** EPA multiplies hourly rates by the operating time before publishing, so
  `grossLoad` is the MWh generated in the hour, i.e. the hour's mean MW. Gross, not net:
  plant own use included. Checked: Barry (AL, facility 3), 2026-06-30 12:00 CST, units 4,
  6A, 6B, 7A, 7B, 8 in EPA's bulk file `emissions-hourly-2026-q2.csv` = 2,074 MW and 896.2
  short tons of CO₂; the file's 14:00 EDT slot holds 2,074.0 MW and 813.0 t.
- **Computed:** a plant's MW per hour = the sum of its units (a unit reporting the hour with
  zero operating time counts 0; no unit reporting = null); CO₂ in tonnes = short tons ×
  0.90718474, summed per plant; capacity = the sum of the distinct generators' nameplate MW
  its units list (combined-cycle units share a steam turbine, counted once; null when a unit
  lists none); fuel = the primary fuel of the largest unit by nameplate (coal includes
  petroleum coke and coal refuse; gas includes process and other gas); region = EIA region of
  the plant's balancing authority ("none" for the ~15 plants EIA-860M lists without one).
  "This hour" sums the plants' CO₂ per region and in total (computed, named on the card).
- **Lag:** units file a quarter within 30 days after it ends; the API serves dates to the end
  of the newest quarter as soon as some units have filed (on 2026-10-11: 573 units for Q3,
  against 3,954 for Q2). A quarter counts as complete when its last day has at least 90 % of
  the units reporting on the previous quarter's last day; the files are the newest 7 days of
  the newest complete quarter (on 2026-10-11: up to 2026-06-30, three months back).
- **Rate limit:** EPA answers HTTP 429 to quick successions (header `X-RateLimit-Limit: 1`);
  the scripts wait 1.5 s between requests and back off on 429. A whole day for the country is
  one request of ~73 MB (~10 s); the streaming services are not paged (`emissions-mgmt` is,
  500 rows a page).

The replay needs the EIA-930 day file of the same date (`usday/`): `.github/workflows/eu-days.yml`
builds the plant files daily (`EPA_API_KEY` secret) and then the missing `usday` files for
those dates (`EIA_API_KEY`); `build_us_day.py --recent 30` keeps day files that have a plant
file.

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

## Imbalance prices (`scripts/build_imbalance.py`, `imbalance.json`)

What a balance responsible party pays (short) or receives (long) per settlement period, as each
TSO publishes it to ENTSO-E: documentType A85, asked per area (`controlArea_Domain` = the
bidding zone's code), answered as a zip of XML documents. Daily in `eu-days` (the last 30 days;
on the `eu-days` branch), card "Imbalance price" in the zone panel (Prices tab).

| Field | Passed through | Computed |
|---|---|---|
| `chart` | every price of the last 7 days at the published 15 minutes, in the source's currency | |
| `daily` per Brussels day | | average (mean of the periods published), lowest, highest, periods below zero, periods published |
| `period` | | the same over the 30 complete days together (the card's tiles) |

Two series per area by `imbalance_Price.category`: **A05 deficit** and **A04 excess**. Under
single pricing they are equal and the file keeps one (`same: true`); the card draws the excess
line only where it differs. A series that is 0 in every period published is flagged `all_zero`
and never charted (Italy fills A05 with 0 and publishes its price in A04). Currencies as
published: PLN (PL), CZK (CZ), HUF (HU), RON (RO); the others EUR.

**No imbalance price at ENTSO-E** (the file lists them in `none`; zones ENTSO-E did not answer
go to `failed`, never to `none`): in the run of 2026-10-18 BG, DE-LU, LT and ME (Germany's reBAP
is published by the four TSOs on netztransparenz.de); 40 zones had prices. The probe of
2026-10-17 (`scripts/probe_entsoe_imbalance.py`) also found none for GR, SE4, SK and UA-IPS,
which answered on 2026-10-18. ENTSO-E throttles repeated full runs from
one address, so the builder runs once a day in Actions, retries 6 times and logs every give-up.

History 2015 onward: `lake/entsoe/imbalance_price` (below, "Lake: ENTSO-E"): built 2026-10-18,
13,728,572 rows, 26.0 MB, every zone answered in every year (rows per year: 2015 585,070;
2016 641,976; 2017 699,360; 2018 713,394; 2019 717,000; 2020 741,028; 2021 892,778; 2022
1,451,030; 2023 1,579,428; 2024 1,790,146; 2025 2,493,806; 2026 to 17 Oct 2,101,682). Zones
without data today published some years (SK in 2015, UA-IPS in 2024): the lake keeps what ENTSO-E
returns for each year.

## LNG send-out (`scripts/fetch_eu_dossier.py`, in `dossier.json`)

GIE ALSI (same key as AGSI+), daily for the EU and the 12 countries with terminals (BE,
DE, ES, FI, FR, GR, HR, IT, LT, NL, PL, PT), last ~400 days, passthrough:
- `sendOut`: LNG regasified into the grid, GWh/day
- `dtrs`: declared total reference send-out, the terminals' declared send-out
  capacity, GWh/day
- `inventory.gwh`: LNG in tanks

## LNG send-out per terminal (`scripts/fetch_alsi.py`, `lng_terminals.json`)

GIE ALSI per facility (`/api/about?show=listing` lists the terminals; one request per terminal
for the window), the last 30 gas days, daily on `eu-days`. Same key as AGSI+ (`AGSI_API_KEY`,
`x-key` header). Passthrough at GIE's precision, per terminal and gas day: `sendOut` (GWh/d),
`inventory.gwh` (LNG in tanks, GWh), `dtrs` (declared total reference send-out, GWh/d) and
GIE's `status` flag (C confirmed, E estimated, N no data). The terminal's position is ALSI's own
`longitude`/`latitude`. Gas day 06:00–06:00 CET (05:00–05:00 UTC in winter).

Left out: terminals not in operation (ALSI start date in the future or end date in the past),
the Spanish virtual balancing tank (TVB, country `ES*`: an account, not a place), and terminals
with no send-out reported in the window (the British terminals have reported none since
Brexit; Panigaglia in October 2026). Check (2026-10-10): the German terminals sum to
231.5 GWh/d, ALSI's Germany total 231.6 GWh/d (rounding of the rows).

Map: layer "LNG send-out" (disc = the newest gas day's send-out, ring = declared send-out; area
follows GWh/d). Panels: "On the map" and the Gas & LNG tab list each terminal with its 30-day
line (sum over the terminals listed, computed).

## CO₂ per installation, EU ETS (`scripts/fetch_eu_ets.py`, `ets.json`)

| What | Source |
|---|---|
| verified emissions per installation and year (t CO₂e), 2005– | Union Registry public extract `operators_yearly_activity_daily.csv.gz` (union-registry-data.ec.europa.eu, "Data download"; refreshed daily, no key) |
| installation, registry (country), activity, permit number | Union Registry `operators_daily.csv.gz` |
| position | EEA industrial sites register (EU Registry; CC BY 4.0) on Discodata SQL: `[IED].[latest].[ProductionInstallationETSIdentifier]` (the ETS id each country reported) and `[IED].[latest].[ProductionInstallation]` (`x_4326`, `y_4326`) |

Rules:
- Stationary installations only: aircraft operators (activity 10), maritime companies (50) and
  the ETS2 fuel suppliers (70) are left out. Kept: an installation with verified emissions in
  any of the five newest years; the newest year is the newest one most installations have
  reported (verified emissions arrive by 31 March). Values passed through in whole tonnes.
- Placing joins on official identifiers only: the reported ETS id is the registry's own id
  (`AT000000000000001` = Austria, installation 1) or exactly the installation's permit number
  in the same country. The newest EEA report wins. No placing by name or address: an
  installation without a match is listed in the panel and counted, not drawn.
- Coverage (snapshot 2026-10-12): 8,921 installations with 1,012.6 Mt in 2025; 2,234 placed
  with 400.8 Mt. Countries whose EEA reports carry no ETS ids (Netherlands, Czechia, Italy
  mostly, Nordics, Romania, Bulgaria, Hungary…) and most of Germany (its reports carry Land
  permit numbers, not the registry's) stay off the map; `scripts/probe_eu_ets.py` prints the
  share per country.
- Activity groups (colour): combustion 1/20 (power, heat and industrial boilers alike: the
  ETS does not separate them), refineries 2/21, iron and steel 3–5/22–25, aluminium and other
  metals 26–28, cement and lime 6/29/30, glass, ceramics, minerals 7/8/31–34, pulp and paper
  9/35/36, chemicals 37–44, other 45/46/99.
- Check against the Commission's `verified_emissions_2025_en.xlsx` (extracted 2026-04-01):
  7,270 installations equal, 61 differ (registry corrections after April; the extract is the
  newer, e.g. Neurath 12,073,464 t now, 12,074,600 t in April). Bełchatów 25,103,854 t,
  Voestalpine Linz 8,866,634 t, Versalis Ravenna 25,589 t equal in both.
- Refresh: Mondays on `eu-days` (and whenever the file is missing).

## What consumers pay (`scripts/fetch_retail_prices.py`, `retail.json`)

| Series | Source | Band |
|---|---|---|
| electricity, households | Eurostat `nrg_pc_204` | DC, 2,500–4,999 kWh a year |
| electricity, businesses | Eurostat `nrg_pc_205` | IC, 500–1,999 MWh a year |
| gas, households | Eurostat `nrg_pc_202` (price per kWh, GCV) | D2, 20–199 GJ a year |
| gas, businesses | Eurostat `nrg_pc_203` (price per kWh, GCV) | I3, 10,000–99,999 GJ a year |
| electricity per US state and sector | EIA API v2 `electricity/retail-sales` (Forms EIA-861, EIA-861M; `EIA_API_KEY`) | average price = revenue ÷ sales |

Eurostat (CC BY 4.0, no key): the newest eight half-years, EUR per kWh at Eurostat's precision
(4 decimals; the app shows euro cents with 2, the same digits), three tax levels: `I_TAX` (all
taxes and levies), `X_VAT` (without VAT and other recoverable taxes), `X_TAX` (without taxes
and levies), and Eurostat's flag per value (p provisional, e estimated, b break, d definition
differs…). Geo codes as the map's (EL → GR, UK → GB, EU27_2020 → EU; euro-area aggregates left
out). The split bar on the country card is the differences of the three levels (energy and
network = `X_TAX`; taxes and levies = `X_VAT` − `X_TAX`; VAT = `I_TAX` − `X_VAT`), computed. The
card's wholesale comparison is the zone's 12-month day-ahead average (Prices tab) ÷ 10.

EIA: the newest 25 months, cents per kWh with EIA's 2 decimals, sectors residential (RES),
commercial (COM), industrial (IND), all (ALL); 50 states, DC and `US` (EIA's national figure);
census divisions left out. Check (2026-10-12) against EIA's Electric Power Monthly, Table
5.6.A, July 2026: Texas residential 15.88, commercial 8.47, industrial 7.07; California
residential 33.61; US 18.31 ¢/kWh: all equal.

Map: "Colour countries by → Household electricity price": Europe's countries by Eurostat's
newest half-year, US states (outlines `us/states.json`) by EIA's newest month, one scale in
cents per kWh (euro cents in Europe, US cents in the US; the key says so). Panels: the
country Prices tab ("What consumers pay"), the Europe Prices tab (ranking), the US panel's
"Retail prices" tab. Refresh: Mondays on `eu-days`.

## Emissions per facility worldwide (`scripts/fetch_climate_trace.py`, `ctrace.json`)

Climate TRACE API v6 (`api.climatetrace.org/v6/assets`, CC BY 4.0, no key;
`scripts/probe_climate_trace.py`). Climate TRACE **models** each asset's emissions from
satellite and other data: estimates, not reported figures; the layer's key, hover and card say
"modelled by Climate TRACE". Passed through: `EmissionsSummary` CO₂e (100-year GWP, tonnes,
rounded to whole tonnes), `Centroid` (lon, lat; 4 decimals), `Country` (ISO3), `Sector` (the
subsector), `Owners` (the first two company names).

- Sectors power, manufacturing, fossil-fuel operations, mineral extraction; assets of at least
  100,000 t CO₂e in the newest complete year (the calendar year before the run: 2025 on
  2026-10-13): 16,679 assets, 27.02 Gt CO₂e. The API lists assets largest first, so paging stops
  under the threshold. The year before is joined by asset id (assets of 50,000 t and more).
- The API has one figure per asset and year; no monthly series per asset.
- Oil and gas production is modelled per basin ("Russia_Central Sub-basin - West Siberia"),
  placed at the basin's centroid; the hover says so.
- Colour groups: power and heat; steel and metals; cement and lime; chemicals and refining
  (incl. oil and gas refining); oil and gas production and transport; coal and mining; other
  industry.
- Checks (2026-10-13): Vindhyachal 2024 36,247,000 t equals `/v6/assets/25451489`; Bełchatów
  2025 24.4 Mt modelled against 25.1 Mt verified in the EU ETS (`ets.json`).
- Refresh: on the 1st of each month on `eu-days` (and whenever the file is missing).

## Grid capacity: GB, NL, ES (`scripts/fetch_connect_here.py`, `connect.json`)

| Country | Source | What |
|---|---|---|
| GB | NESO TEC register (CKAN resource `17becbab-…`, NESO Open Data Licence, twice weekly) | every project holding or seeking transmission entry capacity: site, MW connected, cumulative MW, plant type, status, effective date, TO, agreement |
| GB positions | NESO "GSP - Gnode - Direct Connect - Region Lookup" (2018, `bbe2cc72-…`) | GSP latitude/longitude per region name |
| NL | Netbeheer Nederland, landelijke capaciteitskaart, regional operators' supply areas, ArcGIS feature service `Capaciteitskaart_elektriciteitsnet_v2_afname` (Esri Nederland for Netbeheer Nederland; Esri NL terms of use) | per area: offtake (`afname`) and feed-in (`opwek`) status 0–3, queue MW (`wachtrij_*`), requests |
| ES | Red Eléctrica, "Capacidad de acceso de demanda disponible y ocupada en los nudos de la red de transporte" (`<date>_GRT_demanda.xlsx`, monthly) | per node the access capacity available for new requests (MW): demand CEP with/without voltage-dip ride-through, demand not CEP, storage MPE/MGES; tender nodes |

Rules:
- GB: "waiting" = cumulative total capacity − MW connected per project (computed); a hybrid
  counts under its first listed plant type. A site is placed only where its name, without
  voltage and the words GSP/substation, equals a region name in NESO's lookup (the GSP's
  position there); 2026-10-10: 210.1 of 740.5 GW cumulative capacity at placed sites. Most
  large 400 kV sites and planned "connection nodes" have no published position: counted in the
  card, not drawn. National Grid's own route-map shapefiles exclude commercial use; not used.
- NL: the capacity map's own legend (its renderer expression): 0 capacity available without a
  queue, 1 limited without a queue, 2 under study with a queue, 3 shortage with a queue; areas
  named "0" (no colour yet) left out. Outlines simplified to ~150 m (shapely, 0.0015°).
  2026-10-13: 923 area parts; offtake short in 435, feed-in short in 80. TenneT's high-voltage
  layer (27 congestion areas) is not included yet.
- ES: columns 85–89 of the sheet "Ficha Capacidades" (the "capacidad de acceso disponible para
  solicitudes, criterio general RdT" block); the file has no coordinates, so Spain is a card
  only. Nodes sharing a zone share capacity, so the card does not sum them.
- Refresh: Mondays on `eu-days`.

## Lake: ENTSO-E (`scripts/build_lake_entsoe.py`, `lake/entsoe/`)

Europe's power data in full detail for the agent, not drawn on the map: Parquet on R2
(private bucket `infraatlas-raw`, docs/DATA_LAKE.md section 6), 2015 to yesterday, one ordered
file per table and year. Source: ENTSO-E Transparency Platform API (`ENTSOE_API_KEY`, a repo
secret; `.github/workflows/lake-entsoe.yml`).

| Table | Document | Per | Notes |
|---|---|---|---|
| `prices` | A44 day-ahead | bidding zone (+ DE-AT-LU to 2018, IE-SEM) | every series kept; `sequence` = ENTSO-E's classification sequence (EXAA, intraday auctions), `currency` as published |
| `load` | A65 actual (A16) and day-ahead (A01) | country | one row per timestamp and resolution |
| `generation` | A75 actual (A16) | country, production type | `consumption_mw`: the outBiddingZone series (pumps, batteries charging) |
| `forecast_wind_solar` | A69 day-ahead (A01) | country, production type | |
| `flows` | A11 | border direction (`entsoe.BORDERS`) | measured, each direction its own rows |
| `unit_output` | A73 actual (A16) | unit (EIC); countries, Germany per control area | one request per area and day (the API answers nothing for longer windows) |
| `capacity` | A68 installed (A33) | country, production type | per year |
| `transfer_capacity` | A61 forecast (contract A01) and A31 offered (auction A01) | zone border direction (`fetch_eu_capacity.zone_pairs`) | both documents as published, `doc` says which |
| `outages` | A80 generation units | bidding zone | every revision, one row per point of the available-capacity curve; partition = year of the outage's start |
| `imbalance_price` | A85 imbalance prices | bidding zone (+ DE-AT-LU to 2018) | `category` A05 deficit / A04 excess read from each point, `price` DECIMAL(12,3) and `currency` as published, `resolution_s`; partition `zone` and `year` |
| `areas`, `units` | code lists; A71 per area | | units' positions from JRC-PPDB where it names the EIC code |

Rules: values as published at the resolution ENTSO-E publishes (`resolution_min`), no 15-min
grid and no resampling; A03 curves (which leave out points equal to the one before) are written
out point by point (`entsoe.points_of`). Times are UTC interval starts. A year's file holds
the points whose start falls in that year (UTC). Prices `DECIMAL(9,2)`, MW as `FLOAT`.
`--recent 3` (daily) fetches the last three days again and rewrites the current year's files.

Probe (`scripts/probe_lake_entsoe.py`, run in Actions 2026-10-13): A44 answers a whole year in
one request (DE-LU 2019: 43,188 points, 6 s); A75 for Germany a year in 103 s, a quarter in
16 s (the builder asks quarters); A73 answers one day per request (7 or 31 days: nothing); A80
pages of 200 documents (`offset`; DE-LU January 2023: 798 documents); requests take ~2 s each
(4 at a time: 30 a minute, 8: 67 a minute; ENTSO-E's limit is 400 a minute per key), so a
year runs with 10 at a time.

## Lake: the map's datasets in full (`scripts/build_lake_datasets.py`, `scripts/lake_catalog.py`)

Not drawn on the map: full detail for the agent as Parquet on R2 (private bucket
`infraatlas-raw`, prefix `lake/`; docs/DATA_LAKE.md). Each dataset keeps the source's own
columns (names lower-cased, other characters to `_`; types as DuckDB reads them) plus the
standard keys `iso2`, `iso3`, `admin1` where the source names a country or state.

| Dataset (`lake/…`) | Source | Tables | Refresh |
|---|---|---|---|
| `entsog` | ENTSOG Transparency `operationaldatas`, indicator Physical Flow, period day (gas day 06:00–06:00 CET), every point, direction and operator, kWh/d as published | `flows` (year), `points`, `operator_point_directions` | daily, last 7 days rewrite the year (`eu-days.yml`); backfill by year |
| `eia930` | EIA-930 API v2 `electricity/rto`: `region-data` (demand, forecast, generation, interchange), `fuel-type-data`, `interchange-data`, hourly UTC | `demand`, `generation_by_fuel`, `interchange` (year), `bas` | daily, last 3 days (`eu-days.yml`); backfill 2015– |
| `eia860m` | EIA-860M workbook, every sheet (Operating, Planned, Retired, …) as published, `sheet` names it | `generators` (snapshot = release month) | with each release (`us-grid.yml`) |
| `lbnl_queue` | LBNL Queued Up, the complete data sheet | `requests` (release) | with each release (`us-grid.yml`) |
| `irena` | IRENASTAT PxWeb, Country ELECSTAT table: every country, technology, data type (capacity MW, generation GWh), grid connection, year, with IRENA's codes and labels | `capacity`, `generation` (release) | daily check, partition per release (`eu-days.yml`) |
| `power_plants_eu` | JRC-PPDB-OPEN 1.0 (units, performance), powerplantmatching `powerplants.csv` | `jrc_units`, `jrc_performance`, `ppm_plants` | by hand (`lake-datasets.yml`) |
| `gem` | Global Energy Monitor trackers (the private R2 copies), every data sheet | one table per tracker and sheet (release) | with each release (`gem.yml`); never public |
| `osm` | PyPSA-Eur (Zenodo 18619025) lines, buses, links; undersea cables and data centres as the map's fetchers read them from OpenStreetMap (ODbL) | `eu_lines`, `eu_buses`, `eu_links`, `cables`, `datacentres` (GeoParquet, snapshot) | monthly (`eu-days.yml`) |
| `euets` | EU Union Registry public extracts (operators, yearly activity), EEA industrial register ETS identifiers and positions | `installations` (snapshot), `verified_emissions`, `eea_link` | Mondays (`eu-days.yml`) |
| `neso_tec`, `nl_capacity`, `ree_nodes` | NESO TEC register CSV; Netbeheer Nederland capacity map (every attribute and the area outline); REE "Ficha Capacidades" | `projects`, `areas` (GeoParquet), `nodes` (snapshot) | Mondays (`eu-days.yml`) |

`lake/_catalog.json` (every dataset, table, rows, bytes) and `lake/lake.duckdb` (one view per
table, schema = dataset, and the topic views `plants`, `prices`, `outages`, `emissions`,
`grid_capacity`, `water_risk` with a `source` column) are written daily by
`.github/workflows/lake-catalog.yml`. A topic view passes each source's own values under common
column names (e.g. `outages.value` is EAGLE-I's customers out, or ENTSO-E's available MW during the outage, with `unit` saying which); nothing is converted between sources.

## US outages (`scripts/build_us_outages.py`, `us_outages.json`, `us/counties.json`)

| What | Source |
|---|---|
| Customers without power per county every 15 minutes, 2014 (from 1 Nov) to 2025 | EAGLE-I recorded electricity outages, Oak Ridge National Laboratory, figshare article 24237376 (CC BY 4.0), one CSV per year (0.08–1.4 GB; the 2023 file names its count column `sum`, 2024 adds `total_customers`) |
| Customers per county | EAGLE-I's `MCC.csv` (ORNL's modelled customer count per county) |
| County outlines | US Census Bureau cartographic boundary file, counties 1:20m, 2020 (public domain): Connecticut's eight old counties, as EAGLE-I and MCC use |

Built in GitHub Actions (`.github/workflows/us-outages.yml`, one job per year, by hand and when
the script changes). "Customers" are utility meters, not people; EAGLE-I lists a county only
while customers are out there, so a missing row is zero.

Rules (all computed, labelled on the map):
- Customer-hours per county and year = sum of customers out × the interval (15 min).
- Hours per customer (hover) = customer-hours ÷ MCC customers.
- National peak per day = largest sum over counties at one timestamp; the state with the most
  customers out at that moment.
- Event = a run of timestamps in one state with ≥ 10,000 customers out (sum over its
  counties), gaps up to 60 min; peak, start, end (+ one interval). Top 50 over all years.
  Events across New Year are split (one job per year).
- Newest month: national customers out at each timestamp of the newest month.
- Values as EAGLE-I publishes them, never smoothed: the files hold single-interval spikes
  (e.g. New York, 1.2 M customers at 2018-07-10 20:00 for one 15-min step) and peaks above the
  utilities' own reports (Florida, Irma, 2017: 9.7 M), which show up as events. 2018 had no
  county reported twice at one time (checked in the year job, logged for every year).

Lake: `lake/eaglei/` (docs/DATA_LAKE.md section 6): `outages` (every row as published, per
year), `counties` (names and MCC), `coverage` (`coverage_history.csv`) and `dqi` (`DQI.csv`),
as published.

## Water risk (`scripts/build_aqueduct.py`, `water.json`)

| What | Source |
|---|---|
| Baseline water stress, riverine and coastal flood risk, drought risk per river basin | WRI Aqueduct 4.0 water risk atlas (World Resources Institute, CC BY 4.0), `aqueduct-4-0-water-risk-data.zip` (262 MB, release 2023-07-05); data dictionary github.com/wri/Aqueduct40 |

Built in GitHub Actions (`.github/workflows/water-risk.yml`). The map shows WRI's own category
(`*_cat`) and label (`*_label`) per HydroBASINS level-6 basin (`pfaf_id`, 16,395 basins; the
outlines from the GDB layer `baseline_monthly`, simplified with shapely until the file stays
under 5 MB: 0.06°, 2 decimals; 16,052 basins keep an outline). The categories come from the
`baseline_annual` units (basin × province × aquifer); where a basin's units differ the map
takes the highest: none do for these four indicators (2026-10-13). For site screening.

Lake: `lake/aqueduct/` (source_version 4.0): `baseline_annual` (GeoParquet, every column as
published, 68,506 units), `basins` (GeoParquet outlines), `baseline_monthly` (one row per basin
and month), `future_annual` (one row per basin, scenario bau/opt/pes and year 2030/2050/2080).
Basin tables carry the country and province holding most of the basin's area (sum of
`area_km2`, computed) as `iso3`/`admin1`.

## Germany: every unit (`scripts/build_mastr.py`, `mastr/units_large.json`, `mastr/municipalities.json`)

| What | Source |
|---|---|
| Every generating and storage unit in Germany | Marktstammdatenregister (Bundesnetzagentur), daily bulk export `Gesamtdatenexport_<date>_<version>.zip` (3.2 GB, ~66 GB of UTF-16 XML), Datenlizenz Deutschland – Namensnennung 2.0 (dl-de/by-2-0, named on the download page) |
| Municipality outlines | BKG VG5000, municipalities (`VG5000_GEM`, GF = 4: land areas), UTM 32N → lon/lat, simplified ~200 m; dl-de/by-2-0 |

Built in GitHub Actions (`.github/workflows/mastr.yml`, monthly): one download (the server
resets parallel downloads and serves ~1 MB/s, so ~55 min), then six parts streamed from the zip
(never unpacked) in parallel processes. Codes (status, Land, energy carrier, …) are named from
the export's own `Katalogwerte`.

Rules (computed, labelled on the map and in the panel):
- Units counted: status "In Betrieb" (in operation); MW = gross capacity (`Bruttoleistung`, kW
  / 1000) summed per municipality (`Gemeindeschluessel`) and technology (the XML file a unit
  comes from: solar, wind, storage, biomass, hydro, combustion, nuclear, other = geothermal,
  mine gas, pressure relief).
- Units without a municipality key are counted in `no_ags`, not drawn: offshore wind
  (`offshore`, `WindAnLandOderAufSee` = "Windenergie auf See") and the large thermal units,
  which the public export lists with their Land only (no municipality, postcode or
  coordinates; 2026-10-13: 70.5 GW of combustion units in operation, e.g. Boxberg, Lünen).
- Large units: in operation, ≥ 1 MW gross, with coordinates (MaStR publishes them only for
  larger units); drawn from zoom 6.
- New units per month: units whose commissioning date (`Inbetriebnahmedatum`) falls in each of
  the last 24 months, any status but "In Planung", gross MW summed. Units are registered up to
  a month late, so the newest months still grow.
- The register lists wind per turbine and solar down to balcony panels; its sums are not
  ENTSO-E's A68 figures (grid operators' figures per type), which the panel shows beside them.

Lake: `lake/mastr/` (docs/DATA_LAKE.md section 6), every column as published plus the
standard columns, partition `snapshot` (and `land` for solar), sorted by `ags, mastr_nr`;
`operators`, `grid_connection_points`, `locations`, `catalog_values`. Snapshots kept: the
newest, the first of each year, and every one younger than a year.

## US prices at every node (`scripts/fetch_us_nodes.py`, `us_nodes/<date>.json`)

Day-ahead prices at every location of six markets, read with `gridstatus` (MIT) from the
markets' public files, no key: CAISO (all nodes, `locations="ALL"`, incl. the Western utilities
in its market), ERCOT (settlement point prices), MISO, SPP, NYISO (generator nodes), ISO-NE.
PJM is skipped while `PJM_API_KEY` is missing. Runs in GitHub Actions (ERCOT blocks many non-US
addresses); probe `scripts/probe_us_nodes.py`, `.github/workflows/probe-us-nodes.yml`.

- **Hours:** the file's day is an Eastern-Time day, the US replay's clock. Each market's interval
  starts (with their own time zone) are put on that day's UTC hours, so a western market's first
  hours come from its previous market day. 23/25-hour days at the DST changes.
- **Values:** USD/MWh as each market publishes them (CAISO 5 decimals, the others 2-4).
- **Positions:** only CAISO publishes node coordinates, in its price contour map
  (`wwwmobile.caiso.com/.../PriceContourMap1`: node name, latitude, longitude, balancing area). A
  node is placed when its name equals a map node's name exactly: 2026-10-15, 6,442 of CAISO's
  9,731 priced locations (California 4,177; PacifiCorp East 839, West 476; Portland General 397;
  Bonneville, NV Energy, LADWP, PNM and others). CAISO's aggregated "APnodes" (`…-APND`) are
  not on the map; no other market publishes node positions, so their nodes are counted, not placed.
- **Computed:** per market and hour the minimum, 10th percentile, median, 90th percentile and
  maximum over its priced locations; the map's colour range, the 2nd to 98th percentile of the
  placed nodes' prices over the day.
- **Check (2026-10-15, 12:00 ET):** medians CAISO $25.03, ERCOT $38.76, MISO $57.36, SPP $23.53,
  NYISO $32.36, ISO-NE $28.12; locations CAISO 9,731, ERCOT 1,130, MISO 2,628, SPP 1,620,
  NYISO 748, ISO-NE 1,207.
- **Lake:** every price, `lake/us_lmp/day_ahead` (ts UTC, market, node, node type, LMP and its
  energy, congestion, loss components where published; partitions market, year, month; one
  file per day): ~409,000 rows, 2.7 MB a day.
- **Refresh:** daily on `eu-days` (the missing days of the last 30, newest first, 8 a run).

## US live queues (`scripts/fetch_us_queues.py`, `us/queues_live.json`)

Each market's own interconnection queue, read with the open-source `gridstatus` library (MIT)
from the markets' public files (`scripts/probe_us_nodes.py`, run in Actions because ERCOT blocks
many non-US addresses): CAISO, ERCOT, MISO, SPP, ISO-NE. Missing, and listed as such in the
panel: NYISO (its site answers automated downloads with a bot check, HTTP 202) and PJM (needs
`PJM_API_KEY`; PJM's DNS failed on 2026-10-17).

- Passthrough per request: queue id, state, generation type, capacity (MW), queue date, status.
- Computed: requests whose status is "active" (any case) summed per state and per type. Types
  are mapped onto LBNL's names (`TYPE_RULES`); a hybrid ("Photovoltaic + Storage", "SUN BAT",
  "Hybrid - Solar/Storage") counts under each of its types with its full capacity, LBNL's own
  rule, so type sums exceed the request total. State names are turned into postal codes.
- Probe (2026-10-17): CAISO 2,278 requests (261 active), ERCOT 1,758 (1,169), MISO 3,938 (1,137),
  SPP 3,078 (216), ISO-NE 1,751 (56).
- Lake: every market's full table, all columns as published (text), `lake/iso_queues/requests`,
  partitions `snapshot` and `market`.
- Refresh: weekly (`.github/workflows/us-queues.yml`, committed to main).

## Check a site (computed in the app: `frontend/src/lib/site.ts`, `components/SiteCards.tsx`)

Right-click a place (or "Check a site", or type "latitude, longitude" in the search): the panel
lists what the map's own files say about it. No new data; the link (`?sel=site:lon,lat`) opens
the same site.

| Figure | Source | Computed |
|---|---|---|
| Country, US state, US county | `countries.json` (Europe), `world.json`, `us/states.json`, `us/counties.json` | point in outline |
| Nearest line of 220 kV and more (and of 345 kV and more) | `grid/world-hv.pmtiles` on R2 (OpenStreetMap via Overture, `scripts/fetch_world_hv_overture.py`) | straight-line distance (haversine scale, local flat projection) to the nearest segment in the nine zoom-9 tiles around the site; lines farther than the edge of those tiles are not reported ("none within N km"). Tiles simplified by 6 tile units (about 0.1 km) |
| Nearest line of 100 kV and more (US) | `grid/us-lines.pmtiles` (`scripts/fetch_us_lines.py`) | the same |
| Nearest substation of 220 kV and more, substations within 50 km (Europe) | `grid.json` (PyPSA-Eur) | great-circle distance |
| Room to connect: NL | `connect.json` (capacity map) | the area holding the site, its published states and queues |
| Room to connect: GB | `connect.json` (TEC register) | MW contracted and not yet connected per site, sites within 50 km |
| Waiting to connect: US | `us/queue.json` (LBNL, per state: MW summed over types, each part of a hybrid under its own type), `us/queues_live.json` (markets, per state and type; not added up because a hybrid counts under each type) | none beyond the files' sums |
| Power plants within 50 km: operating, under construction, planned | Europe: `plants.json` (operating) and `world_plants.json` (building, planned); US: `us/plants.json`; elsewhere `world_plants.json` | sums of the map points within 50 km (great-circle) |
| Day-ahead price, hours below zero (Europe) | `prices.json`, every zone of the country (no zone outlines in the files) | as in the Prices tab |
| Retail prices | `retail.json` (Eurostat bands IC and DC, all taxes; EIA per state) | newest value |
| Water risk | `water.json` (WRI Aqueduct 4.0) | the basin holding the site |
| Customer-hours without power (US) | `us_outages.json` (EAGLE-I) | the county holding the site, newest year |
| Renewable share, carbon intensity | `transition.json` (Ember) | newest year with a value |
| Data centres within 50 km | `datacentres.json` (OpenStreetMap) | count and distance |
| Solar resource (PVOUT), mean wind speed at 100 m | `grid/atlas-pvout-0.1deg.i16`, `grid/atlas-wind100-0.1deg.i16` on R2 (Global Solar Atlas, Global Wind Atlas; "Resource atlases" below) | the mean of the source pixels in the site's 0.1° cell (built in Actions), read with one range request; a year of PV = the daily total × 365, as the atlas gives it |

## Country report (computed in the app: `frontend/src/components/CountryReport.tsx`)

"Report" in a country's panel (or `?report=DE`, `?report=BRA`) opens one printable page of the
country's figures from the files above, each section naming its source; "CSV" downloads the
same rows (section, item, value, unit, note, source). Sections appear where the files hold data:
generation in Ember's newest year (shares of the total computed; renewable, wind and solar, coal
shares and carbon intensity as published, and the same ten years earlier), now (ENTSO-E, the
snapshot), twelve months of day-ahead prices per zone (`prices.json`), what consumers pay
(Eurostat; EIA's US average), installed capacity (ENTSO-E A68, IRENA), power plants by status
(GEM sums), US generators, queue and solar arrays (EIA-860M, LBNL, USPVDB sums), emissions (EU
ETS sum, Climate TRACE count, sum and largest five), substations by voltage (PyPSA-Eur counts),
gas storage (GIE AGSI+), offshore wind farm areas (EMODnet counts), access (World Bank) and data
centres mapped (OpenStreetMap). Printing hides the map.

## Offshore wind farms (`scripts/fetch_emodnet_wind.py`, `offshore_wind.json`)

| What | Source |
|---|---|
| Offshore wind farms in European seas: name, country, status, MW, turbines, year, distance to the coast | EMODnet Human Activities, "Wind farms" (data originator CETMAR, updated yearly; CC BY 4.0 per the EMODnet catalogue record 8201070b-4b0b-4d54-8910-abcea5dce57f), WFS `ows.emodnet-humanactivities.eu/wfs`, layers `emodnet:windfarmspoly` (600 areas) and `emodnet:windfarms` (631 points), no key. Probe: `scripts/probe_emodnet.py` |

- Passthrough: every field above as published (distance to the coast converted from m to km,
  0.1 km); statuses Production (shown as Operating), Construction, Approved, Planned, Test site,
  Dismantled.
- Computed: areas simplified (shapely, 0.002°, 4 decimals); a label point inside each area; a
  point record is kept only when no area lies within 0.01° (about 1 km) of it (492 of 631 kept,
  mostly planned in the Mediterranean and the Atlantic); ISO alpha-3 of the country (pycountry).
- The panel counts areas per status and does not sum capacity: the source lists some farms once
  per phase with the whole farm's MW (Hornsea Project 2: four areas at 1,386 MW) and its point
  list repeats some farms (Fryslân twice). Planned areas include zones offered for tender.
- Refresh: by hand (`uv run python scripts/fetch_emodnet_wind.py`), EMODnet updates yearly.
  Lake: none (API rule: the WFS answers the whole layer in seconds and filters server-side).

## Gas flows (`scripts/fetch_entsog.py`, `gas_flows.json`)

| File | Records | Source |
|---|---:|---|
| `gas_flows.json` | ~80 pairs: borders, pipeline sources outside Europe, each country's LNG terminals; 31 gas days | ENTSOG Transparency Platform API (`transparency.entsog.eu/api/v1`, no key): `operationaldatas`, indicator "Physical Flow", period type day, kWh/d per operator, point and direction (shown in GWh/d, rounded to 1 MWh). Sides and point types from `interconnections`, `connectionpoints` and `operatorpointdirections`. Probe: `scripts/probe_entsog.py` |

**Gas day:** 06:00 to 06:00 Central European time (CET/CEST), as ENTSOG publishes it
(05:00–05:00 UTC in winter, 04:00–04:00 UTC in summer). The file holds the newest
complete gas day and the 30 before it. **Complete:** every point that reported the day
before has reported this day too. On 2026-10-10 the probe saw about 70 % of the points
for the gas day that had ended 7 hours earlier, and all of them for the day before; the
morning run (07:23 UTC) therefore usually ends on the day before yesterday.

**Rules** (values are never changed, only grouped, summed or left out):

- **Points:** cross-border transmission points (borders and pipelines from outside) and
  LNG entry points. Storage (also storage across a border), production, distribution,
  final consumers and trading points are left out: this is gas moving between countries
  and into Europe, not the whole balance.
- **Sides:** each operator's country and the country across come from ENTSOG's
  interconnection list; points missing from it use the operator's own entry. TAP AG is
  registered in Switzerland and is placed in Greece for those points; ENTSOG's "UK" is GB.
- **Left out as double reports:** a pipe-in-pipe operator that names the operator whose
  pipe it shares (both report the same gas; e.g. Gasunie Deutschland at Dornum next to
  Open Grid Europe), points flagged as double reporting, an operator's physical points on
  a border where it reports a virtual interconnection point (VIP) for that border (the
  VIP bundles them: e.g. GTS's VIP TTF-THE-H = Bocholtz + Bunde), and **Dornum GASPOOL**,
  which repeats Dornum / NETRA (OGE) to the decimal every day (the script warns if that
  ever changes). ENTSOG's own `aggregatedData` sums Dornum twice and is not used.
- **One side per border:** a border is the sum of one country's operators' reports, both
  directions: the side whose own reports show the larger net flow into its country over
  the window (the importing side). Where both sides report, the other side's net is kept
  in `other_side_net`; over 2026-09-07..10-09 the two agree within 1 GWh/d a day on
  most borders (DE–NL, BE–GB, GB–IE, CZ–DE…). Larger gaps: AT–DE (Austria's sum has
  Überackern, Germany's has VIP Oberkappel and Lindau; 44 GWh/d), BE–NL (23), DK–PL (16), ES–FR (9).
- **Net flow** a→b = the a→b sum minus the b→a sum (computed). Some operators report a
  VIP as one net direction (GTS) where the other side reports both (Gasunie Deutschland),
  so the two directions differ by side while the net agrees.
- **Sources outside Europe** (the countries on this map, less Norway, whose gas comes from
  the shelf) are named by the system across the border, with the origin ENTSOG gives the
  import point (`importFromCountryKey`) where it differs: Kipi and Kipoi (Türkiye → Greece)
  carry gas from **Azerbaijan**, Strandzha 2 (Türkiye → Bulgaria) **Russian gas through
  TurkStream**, Kotlovka (Belarus → Lithuania) Russian gas for Kaliningrad. Tarifa: ENTSOG
  names Algeria, but the Maghreb–Europe pipeline now carries gas from Spain to Morocco.
  TAP enters Italy at Melendugno from Albania; it crosses Greece and Albania without a
  reported point there, so Albania shows gas leaving and none arriving.
- **LNG** per country = the transmission operators' entries at the LNG points (the LNG
  operators' own rows report the same gas). Against GIE ALSI send-out (the LNG card), gas
  day 2026-10-03: BE, FR, LT, NL, PT within 0.5 %, DE 270 vs 275, ES 578 vs 558, PL 62
  vs 56, IT 386 vs 457 GWh/d; Croatia's operator reports 0 at Krk while ALSI reports 84.
- **Map:** the sources outside Europe and each country's LNG terminals are drawn at fixed
  points placed for reading (`frontend/src/lib/gasFlows.ts`), not at a measured place;
  arcs from 5 GWh/d. Gas entering Europe (pipelines from outside and LNG) is drawn wider and
  brighter than gas between European countries. Each source carries its total into Europe on
  the gas day: the sum of its arcs (computed; LNG per country, labelled from 150 GWh/d);
  flows between countries are labelled from 400 GWh/d. The EU card sums the sources (computed) and
  the last 30 gas days (computed, TWh).

ENTSOG answers a whole month of every point in one request (`limit=-1`, ~30 MB, ~7 s).
`limit` counts rows before the server drops empty ones, so `limit`/`offset` paging skips
rows; the script asks one window with `limit=-1`. Eight requests in a row all answered.
Refreshed daily by `.github/workflows/eu-days.yml` onto the `eu-days` branch; the app
prefers that copy when it is newer than the bundled one.

## World tab (`scripts/fetch_world.py`, `scripts/fetch_aemo.py`)

| File | Records | Source |
|---|---:|---|
| `world_stats.json` | 216 countries + world, 2000-2024 | World Bank WDI `EG.ELC.ACCS.ZS`, access to electricity (% of population), CC BY 4.0, as published. The map colours each country by its newest year (the tooltip names it) |
| `datacentres.json` | 4,500 sites | OpenStreetMap (ODbL) via Overpass: `telecom=data_center` or `building=data_center`, one point per site (ways and relations at their centre; points sharing a 3-decimal position count once). Countries assigned with Eurostat GISCO outlines (computed): 4,434 fall inside one. Hubs (computed): sites per 1-degree cell at the cell's mean position, drawn when zoomed out. A mapped subset: counts follow mapping effort, not capacity. PeeringDB's facility list would add coverage, but its terms forbid passing the data on in bulk or commercial use, so it is not used |
| `aemo.json` | 5 regions, 6 interconnectors | AEMO's public NEM summary, the newest 5-minute dispatch: price (AUD/MWh), total demand, net interchange, scheduled and semi-scheduled generation per region, interconnector flows with AEMO's sign (positive = from the first region in the name). Refreshed with every snapshot run. Region markers are placed for reading |
| `brazil.json` | 4 subsystems, 6 flows | ONS "Energia Agora" balance (`scripts/fetch_brazil.py`, no key; `scripts/probe_more_grids.py`): per subsystem (Southeast/Centre-West, South, Northeast, North) load, generation by source (hydro, thermal, wind, solar, nuclear, Itaipu, distributed MMGD), imports and exports; flows between subsystems with ONS's names and sign (positive = from the first named to the second, checked against the subsystems' import/export). `norteFic` is ONS's junction node at the Imperatriz substation; `internacional` is the link with Argentina and Uruguay. Refreshed with every snapshot run. Markers are placed for reading |
| `taiwan.json` | ~190 units, 11 types | Taipower open data (data.gov.tw dataset 8931, `scripts/fetch_taiwan.py`, no key; `scripts/probe_taipower.py`), every 10 minutes: per unit its type, name, installed capacity (MW), net generation (MW) and status note; per type Taipower's subtotal row (installed and net MW), passed through. Battery charging (儲能負載) is summed separately as `charging_mw` (negative). Computed: the island total = sum of the type subtotals (Taiwan has no interconnectors, so this is its whole supply). Type names and notes are translated; unit names stay as published, with the plant's English name where listed. Refreshed with every snapshot run. The marker is placed for reading |
| `ontario.json` | demand, price, ~190 generators, 5 neighbours | IESO public reports (`scripts/fetch_ontario.py`, no key; `scripts/probe_ieso.py`): RealtimeTotals "ONTARIO DEMAND" and RealtimeOntarioZonalPrice (CAD/MWh) every 5 minutes; GenOutputCapability, every generator's hourly output with its fuel; IntertieScheduleFlow actual flows every 5 minutes (positive = export from Ontario, checked against the export/import schedules). Computed: fuel totals = sums of the generators reporting for the newest hour with output from at least 80 % of them; each neighbour's flow = sum of its interties (Québec: all `PQ.*` interties; Manitoba: `MANITOBA` + `MANITOBA SK`) at the newest interval reported by every intertie. IESO's clock is Eastern Standard Time all year, hours ending. Refreshed with every snapshot run. Markers are placed for reading |
| `wind_world.json` | 181 × 81 points, 9 steps | ECMWF open data, IFS 0.25° (`scripts/fetch_ecmwf.py`, no key, CC BY 4.0; `scripts/probe_ecmwf.py`): the newest run whose first 27 hours are published; three fields per step fetched with HTTP range requests from the run's `.index`: `100u`, `100v` (wind at 100 m) and `ssrd` (surface solar radiation downwards, accumulated J/m²). Kept: the 0.25° points that fall on a 2° grid, 80° S to 80° N (no averaging; the 180° column repeats −180°). Computed: speed = √(u² + v²) (0.1 m/s), direction the wind blows from, and sunshine = (ssrd at the step − ssrd 3 h earlier) / 10,800 s, the average W/m² of the 3 hours before the step. Steps +3 h to +27 h. Fetched once per snapshot workflow run (ECMWF runs every 6 h); the live wind and sunshine layers read it for the whole globe |
| `irena.json` | 224 countries × up to 26 technologies × 26 years | IRENA statistics, IRENASTAT PxWeb API (`scripts/fetch_irena.py`, no key; `scripts/probe_irena.py`): table "Electricity statistics by Country/area, Technology, Data Type, Grid connection and Year" (newest release), "Electrical Installed Capacity (MW)", grid connection "All", per IRENA technology as published (its own categories, incl. its "Total Renewable" and "Total Non-Renewable"); series without any value left out. IRENA's certificate chains to GoDaddy's 2025 root (`scripts/certs/godaddy-tls-root-r1.pem`, exported from the Windows trust store, SHA-256 25:CF:3D:A8:…:71:9F), added to Python's trusted roots. Computed in the app: wind = onshore + offshore. Rebuilt daily by `eu-days.yml` |
| `us.json` | 13 EIA regions + Lower 48 | EIA-930 Hourly Electric Grid Monitor via EIA API v2 (`EIA_API_KEY`, public domain), `scripts/fetch_us.py`: hourly demand (D), net generation (NG), total interchange (TI, positive = net export), generation by fuel, and the flow between regions and to Canada and Mexico. Each value keeps its own hour: demand is about 1 h behind, generation and the mix about a day, flows about two days (`scripts/probe_eia.py`). Fuels grouped like the rest of the app; storage is negative while charging. Flows: the newest hour in which every region pair has a value, one direction per pair (the other side's report sign-flipped), EIA's sign (positive = from the first region to the second). Refreshed with every snapshot run. Region markers are placed for reading |
| `world_plants.json`, `world_plant_names.json` | 139,740 plant points; per country and world totals | Global Energy Monitor, Global Integrated Power Tracker, September 2026 release (CC BY 4.0; fetched through GEM's download form by `scripts/fetch_gem.py` into `data/world/gem/integrated-power/`, never committed; the release is recorded in `scripts/gem_releases.json` and `.github/workflows/gem.yml` rebuilds the file when GEM publishes a new one), `scripts/build_world_plants.py`. 183,404 units of 8 types. Computed: statuses grouped (operating; construction; planned = pre-construction + announced; retired = retired + mothballed; cancelled and shelved left out), units summed per GEM location, type and status into one point (capacity = sum; year = earliest start, or latest retirement for retired), and capacity by type and status per country (GEM's ISO alpha-3) and for the world. Names in a second file, loaded on the first hover |
| `gem/pipelines_gas.json`, `gem/pipelines_oil.json` | 3,213 gas and 1,416 oil/NGL pipelines | Global Energy Monitor, Global Gas Infrastructure Tracker (gas pipelines) and Global Oil Infrastructure Tracker (oil/NGL pipelines), routes from GEM's GeoJSON (CC BY 4.0; `scripts/fetch_gem.py`, `scripts/build_gem_layers.py`). Per pipeline: name and segment, GEM's status, capacity (bcm/y for gas; barrels of oil equivalent a day for oil), merged length (km), first start year, countries, all as published. Drawing only: touching route segments joined into lines, simplified (Douglas-Peucker, 0.01°, about 1 km) and rounded to 0.001°. Status classes for the style: operating; construction; planned = proposed, announced, pre-construction; idle = mothballed, idle. Cancelled, shelved and retired pipelines are left out (counted in `left_out`) |
| `gem/lng.json` | 584 points | GEM, Global Gas Infrastructure Tracker, LNG terminals. Computed: a terminal's units with the same type (import/export) and status are one point, capacity = their sum (Mtpa), year = the earliest actual or planned start. Status classes as for pipelines |
| `gem/coal_terminals.json` | 432 terminals | GEM, Global Coal Terminals Tracker: name, terminal type, status, capacity (Mt), start year, as published. Status classes as for pipelines |
| `gem/fields.json` | 6,892 fields | GEM, Global Oil and Gas Extraction Tracker, field-level data: name, fuel type, status, production start year, as published (no size: the map draws every field the same) |
| `gem/coal_mines.json` | 5,141 mines | GEM, Global Coal Mine Tracker, non-closed mines: name, mine type, status, capacity (Mtpa; production where no capacity is given), opening year |
| `gem/steel.json` | 1,539 points | GEM, Global Iron and Steel Tracker: plant coordinates from the plant sheet; computed: a plant's capacity rows with the same status are one point, crude steel capacity summed (kt/y); main production equipment (e.g. EAF, BF-BOF) as published |
| `gem/cement.json` | 3,690 plants | GEM, Global Cement and Concrete Tracker: plant type, operating status, cement capacity (Mt/y), start year |
| `gem/chemicals.json` | 868 plants | GEM, Global Chemicals Inventory: plant location and primary products. The inventory has no status column: plants are drawn as operating |
| `gem/iron_ore.json` | 945 mines | GEM, Global Iron Ore Mines Tracker: status, production 2025 (kt/y; design capacity where no production is given), start year |
| `gem/methane.json` | 3,473 plumes | GEM, Global Methane Emitters Tracker, satellite methane plumes: origin location, emission rate (kg/h), type of infrastructure, observation year, nearby GEM asset. Each plume is one observation, drawn as operating and sized by its rate |
| `gem/finance.json` | 3,963 deals: 208 flows between countries, 377 projects, 400 financiers | GEM, Global Coal Project Finance Tracker and Gas Finance Tracker (CC BY 4.0; `scripts/build_gem_finance.py`). Each row is one financier's share of one deal for a coal unit, a gas plant or an LNG terminal, with the financier's home country and the deal's close year. Coordinates: coal from the tracker; gas joined by GEM's unit IDs to the LNG terminal tracker and the Integrated Power Tracker. Computed: amounts in US$ million (coal US$ / 10⁶); deals marked "Stopped" and rows without a financier or amount left out; sums per project (with its three largest financiers), per financier, and per financier country → project country and fuel for deals crossing a border ("flows"), plus each country's money at home, abroad and from abroad. A flow starts at the middle of the lending country's largest outline (a fixed point for small countries the outlines lack) and ends at the money-weighted middle of the projects it financed: both map placements. Multilateral financiers have no home country: counted in projects and rankings, never drawn. The map draws flows from US$ 300 million; all count in the panel |
| R2: `grid/world-hv.pmtiles` | every OSM power line of 220 kV and more | OpenStreetMap (ODbL) via Overpass, `scripts/fetch_world_hv.py`, box by box (boxes that time out are split into quarters), each line once with its highest voltage. Built into vector tiles by `.github/workflows/world-hv.yml` (500 kV+ shown from zoom 0, 300 kV+ from zoom 1, the rest from zoom 3) and uploaded to R2. The World tab's grid layer, coloured by voltage. Probe: `scripts/probe_osm_hv.py` |
| R2: `grid/world-grid.pmtiles` (optional "Predicted local grid" layer, off by default) | 3.68 M lines as vector tiles, zoom 0-8 | Gridfinder (Arderne et al. 2020, Zenodo 3628142, CC BY 4.0): transmission and distribution lines, each either mapped in OpenStreetMap (`source=openstreetmap`) or predicted by Gridfinder from night-time lights and roads (`source=gridfinder`); no voltage attribute. Built by `.github/workflows/world-grid.yml` on GitHub's runner (725 MB download, tippecanoe, densest features dropped at low zoom) and uploaded to the R2 bucket `infraatlas-data`; the map reads only the tiles in view. Probe: `scripts/probe_gridfinder.py` |
| `cables.json` | 1,966 cables | OpenStreetMap (ODbL) via Overpass, `scripts/fetch_cables.py`: ways tagged `power=cable` with `location=underwater` or `submarine=yes`. Class computed from the tags: HVDC (`frequency=0`), AC from 110 kV, smaller (mostly offshore wind farm cables), untagged. Some ways tagged underwater run mostly over land (tagging errors): a cable is kept, whole and with its landfall, only when at least half its length lies outside the land outlines (GISCO 1:20M, computed); cables in lakes and narrow fjords drop out. Simplified to about 500 m. Well mapped around Europe, sparse elsewhere. Shown on the World tab and as the live map's "cables" chip |

Renewable share in the World country card: Ember yearly data (`transition.json`), the
newest year with a figure.

## United States (`scripts/fetch_us_grid.py`, `scripts/fetch_us_lines.py`)

Every power plant, the interconnection queue, every wind turbine and the transmission lines,
in `frontend/public/data/us/` and on R2. No key. Probes: `scripts/probe_eia860m.py`,
`scripts/probe_lbnl_queue.py`, `scripts/probe_uswtdb.py`, `scripts/probe_hifld.py`,
`scripts/probe_us_lines.py`. `.github/workflows/us-grid.yml` checks every month for new
releases (EIA-860M monthly, the queue yearly, USWTDB quarterly), rebuilds only those files
and commits them to main; it rebuilds the line tiles quarterly. Each file records the
release it was built from (`release`).

```sh
uv run python scripts/fetch_us_grid.py            # files whose source has a new release (--force: all)
uv run python scripts/check_us_totals.py          # plants vs EIA's published national total
env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY uv run python scripts/fetch_us_lines.py --out data/us/us-lines.geojsons
```

### `us/plants.json`: EIA-860M

U.S. Energy Information Administration, Form EIA-860M, Preliminary Monthly Electric Generator
Inventory (public domain), the newest month on https://www.eia.gov/electricity/data/eia860m/
(August 2026: published 23 Sep 2026). Generators of 1 MW and more with their plant's
coordinates; sheets Operating, Planned, Retired and their Puerto Rico twins. The page lists
the coming months' files inside HTML comments: those placeholders are skipped.

| Field | Source / rule |
|---|---|
| `points[]` = [lon, lat, type, status, MW, year, plant, units] | one point per EIA plant, fuel group and status (computed): lon/lat = the plant's `Longitude`/`Latitude`; MW = sum of the units' `Net Summer Capacity (MW)`; year = earliest `Operating Year` (operating), earliest `Planned Operation Year` (under construction, planned) or latest `Retirement Year` (retired); units = number of generators summed |
| `types` (fuel group) | from `Energy Source Code`: SUN solar; WND wind; NG, OG, BFG, PG, SGP gas; DFO, RFO, JF, KER, PC, WO oil; BIT, SUB, LIG, ANT, RC, WC, SGC, SC coal; NUC nuclear; WAT hydro; MWH storage; WDS, WDL, BLQ, OBS, OBL, OBG, LFG, AB, MSW, SLW bioenergy; GEO geothermal; the rest other. `Technology` "Hydroelectric Pumped Storage" is storage |
| `statuses` | operating = the Operating sheet (EIA's OP operating, SB standby, OA and OS out of service); under construction = Planned sheet `Status` U, V, TS; planned = P, L, T; retired = the Retired sheet. The Canceled or Postponed sheet is left out (counted in `left_out`) |
| `plants[]` = [name, state, EIA plant id] | `Plant Name`, `Plant State`, `Plant ID` |
| `totals`, `states`, `status_detail` | sums of net summer capacity by status and fuel: nationally (50 states and DC, without Puerto Rico, as EIA's national totals), per `Plant State` (Puerto Rico included as PR), and per EIA status code |
| `additions` | sums by `Planned Operation Year`, status and fuel (Planned sheet) |
| `retirements_planned` | sums of operating units by `Planned Retirement Year` and fuel |
| `retired` | sums of the Retired sheet by `Retirement Year` and fuel, from 2010 |
| `left_out` | canceled or postponed units; units without coordinates (in the sums, not on the map; e.g. early reactors listed without a plant ID); units without a net summer value (counted as 0 MW, as in EIA's totals: mostly parts of combined-cycle plants) |

Check (`scripts/check_us_totals.py`): EIA's Electric Power Monthly Table 6.1 gives
1,315,876.2 MW of utility-scale net summer capacity in service at the end of July 2026; the
same build from the July 2026 EIA-860M file gives 1,316,203.6 MW (+0.025 %). Per fuel the two
differ by at most 1 % (coal +900 MW, storage −400 MW): EIA's table groups by technology, this
file by energy source code. The map shows the newest month (August 2026: 1,318.8 GW).

### `us/queue.json`: LBNL Queued Up

Lawrence Berkeley National Laboratory and GridTracker (Interconnection.fyi), "Queued Up"
interconnection queue data file: "licensed CC BY 4.0 ... attribute it to Lawrence Berkeley
National Laboratory and GridTracker" (LBNL's publication page; the workbook itself carries
only the DOE copyright notice), the newest
`lbnl_ix_queue_data_file_thru<YEAR>.xlsx` (2026 edition, May 2026: requests through the end
of 2025; 7 ISOs/RTOs and 50 non-ISO balancing areas, ~98 % of US capacity). emp.lbl.gov
answers Cloudflare's block page to scripts; the file comes from eta-publications.lbl.gov.
Sheet "03. Complete Queue Data", one row per request.

| Field | Source / rule |
|---|---|
| `types` | `type_1`, `type_2`, `type_3` as published (Solar, Battery, Gas, Wind, Offshore Wind, Nuclear, Other Storage, Geothermal, Coal, Hydro, Hydrogen, Diesel, Oil, Other); storage = Battery and Other Storage |
| `total.active`, `states.*.active` | sums of `mw_1..3` under their own `type_1..3` (a hybrid counts under each of its types, as LBNL's "by type" tables do) for `q_status` = active, nationally and per `state` |
| `total.suspended`, `states.*.suspended` | the same for `q_status` = suspended |
| `*_n` | number of requests |
| `phase` | sums of active MW by `IA_phase_clean` as published ("Not reported" where it is empty) |
| `by_year` | sums of active MW by `prop_year` (proposed online year) |
| `no_state` | active requests without a `state`: in the national total only |

Check: active generation (every type but storage) sums to 1,312.0 GW, LBNL's headline
figure (1,312 GW). Storage sums to 552.7 GW; the report's ~749 GW adds LBNL's estimate for
hybrid projects that report no storage size, which the data file leaves out (its codebook
says so) and the map does not show. On the map each state with active requests carries
a tower of its active GW stacked by type (1 GW = 1.4 km). The state is shaded by its active
GW ÷ the GW of plants it runs today, i.e. the operating net summer capacity of all fuels in
`us/plants.json` (computed in the app, shown as "2.9× its plants"; drawn without a shade
where a state has no operating plants in EIA-860M).

### `us/turbines.json`: USWTDB

U.S. Wind Turbine Database (USGS, Lawrence Berkeley National Laboratory, American Clean
Power; public domain), the CSV download on https://energy.usgs.gov/uswtdb/data/ (V9.1,
2026-09-28: 77,839 turbines, 129 offshore). One entry per turbine in each column, passthrough.

| Field | Source / rule |
|---|---|
| `lon`, `lat` | `xlong`, `ylat` (rounded to 0.0001°) |
| `kw`, `hh`, `rd` | `t_cap` (kW), `t_hh` (hub height, m), `t_rd` (rotor diameter, m); empty where USWTDB has none |
| `model`, `models` | `t_model`, listed once |
| `offshore` | `t_offshore` |
| `project`, `projects[]` = [name, state, year, turbines, MW] | `p_name`, `t_state`, `p_year`, `p_tnum`, `p_cap`, listed once per project name and state |
| `mw`, `states` | sums of `t_cap` over the turbines that have one (computed): nationally and per `t_state` with the turbine count |

### `us/solar.json`, `us/solar_outlines.json`: USPVDB

The U.S. Large-Scale Solar Photovoltaic Database (USGS and LBNL, public domain), release v4.0
(2026-04-14): 6,611 ground-mounted PV facilities of 1 MW (DC) and more, digitised from aerial
imagery, 131.6 GW AC in all. GeoJSON zip (~10 MB) from energy.usgs.gov/uspvdb/data/
(`scripts/fetch_uspvdb.py`, probe `scripts/probe_uspvdb.py`).

- Passthrough per facility: name, state, county, year, AC and DC capacity (MW), tracking axis,
  system type, site type (greenfield, landfill, ...), agrivoltaic, battery, EIA plant id, image
  date, the published centre point.
- Computed: outlines simplified (shapely, 0.0003°, about 30 m; 4 decimals) in a second file the
  map loads only from zoom 7.5; the panel's sums per state and shares by tracking.
- Its own count, not EIA-860M's: USPVDB maps arrays, EIA lists generators.
- Refresh: the monthly `us-grid.yml` run rebuilds both files when the data page names a new
  release.

### `us/states.json`: outlines

U.S. Census Bureau cartographic boundary file, states 1:20,000,000, 2024 (`cb_2024_us_state_20m`,
KML, public domain): `STUSPS`, `NAME`, polygons rounded to 0.001°; the label point is a point
inside each state's largest polygon (computed with shapely). Used for the queue slabs, and to
leave GEM's plants out inside the US while the EIA plants layer is on.

### R2: `grid/us-lines.pmtiles`: transmission lines

HIFLD's "Electric Power Transmission Lines" is no longer public: since HIFLD Open's 2025
change the HIFLD geoplatform holds no open copy (its organisation has only a 2023 user
upload), and Esri's copy ("U.S. Electric Power Transmission Lines (Archive)") is archived,
last updated 30 Sep 2024 and licensed under the Esri Master License Agreement
(`scripts/probe_hifld.py`). `grid/world-hv.pmtiles` holds no North American lines (its North
America job never finished). So the lines are OpenStreetMap's (ODbL), the source of the world
grid layer, read through Overture Maps.

Overture Maps, base theme, type infrastructure (newest release, 2026-09-23.1), classes
power_line and cable, as GeoParquet on Overture's public S3 bucket read with DuckDB box by
box (lower 48, Alaska, Hawaii). Kept: lines whose OSM `voltage` tag's highest value is 100 kV
or more (NERC's bulk electric system threshold; world-hv starts at 220 kV, but 115–161 kV
lines carry much of the US grid) and that touch a US state (Census outlines; lines crossing a
border are kept whole). Per line: `kv` (highest voltage), OSM `name`, `dc` (`frequency` 0:
HVDC), `cable` (underground or submarine); coordinates rounded to 0.0001°. 2026-09-23.1:
174,801 lines (24,292 of 345 kV and more, 35,317 of 200–344 kV, 115,192 of 100–199 kV); left
out 36,356 without a voltage tag, 103,511 below 100 kV, 10,048 outside the US. Tiles: 345 kV+
from zoom 0, 200 kV+ from zoom 3, 100 kV+ from zoom 5, to zoom 11 (18 MB). The map colours
them with Europe's voltage bands (380 kV+, 275–379, 200–274) and a darker 100–199 kV band.

## Great Britain: carbon intensity (`scripts/fetch_gb_carbon.py`, `gb_carbon.json`)

NESO Carbon Intensity API (api.carbonintensity.org.uk, no key, CC BY 4.0 as stated on
carbonintensity.org.uk; `scripts/probe_gb_carbon.py`), every half hour. In the snapshot loop of
`eu-snapshot` (onto `eu-data`, reloaded every 10 minutes by the app); a card in Great Britain's
country panel (Now tab).

| Field | Endpoint | Notes |
|---|---|---|
| `now` | `/intensity/{t}/pt24h` | the newest period with an **actual** value (gCO2/kWh); when none is published yet, the current forecast, labelled `kind: forecast` |
| `past` | `/intensity/{t}/pt24h` | the last 24 h: forecast and actual per half hour |
| `ahead` | `/intensity/{t}/fw48h` | the national forecast for the next 48 h and NESO's index (very low … very high) |
| `mix` | `/generation` | the generation mix of the current half hour in % per fuel, as published |
| `regions` | `/regional` | the 14 DNO regions (and England, Scotland, Wales, GB): **forecast only**, the API publishes no regional actual |

Probe 2026-10-18: 48 of 48 half hours of the last day had an actual value, the newest ending at
the last full half hour (05:00Z at 05:21Z); 96 periods ahead; a day 400 days back answers too.
Nothing is computed; the card's "lowest ahead" is the smallest published forecast value.

## Denmark every 5 minutes (`scripts/fetch_dk_live.py`, `dk_live.json`)

Energinet's Energi Data Service (api.energidataservice.dk, no key, CC BY 4.0 per its terms
page; `scripts/probe_dk_live.py`). In the snapshot loop of `eu-snapshot`; a card in Denmark's
country panel (Now tab), labelled "Energinet, every 5 minutes".

| Field | Dataset | Notes |
|---|---|---|
| `co2.DK1`, `co2.DK2` | `CO2Emis` | g CO2 per kWh **consumed**, per price area, every 5 min, the last 24 h on a 5-min grid (gaps stay empty). Energinet's initial values; the declared values follow in `DeclarationGridEmission` |
| `production.DK1/DK2.mw` | `ElectricityProdex5MinRealtime` | MW, the newest 5 minutes per area: plants ≥ 100 MW, plants < 100 MW, offshore wind, onshore wind, solar, and the exchange per neighbour (positive = import into the area, Energinet's convention; Great Belt between DK1 and DK2) |

Values as published: initial figures from upscaled real-time measurements that Energinet does
not correct. The API returns 32-bit floats (87.129997); they are kept to 2 decimals. Probe
2026-10-18: both datasets update every 5 minutes, the newest record 3 minutes old; the last 24 h
are 576 records for each.

## US EV fast chargers (`scripts/fetch_ev_chargers.py`, `us/ev_chargers.json`): waiting for a key

NREL's Alternative Fuels Data Center station locator, `alt-fuel-stations/v1.json` with
`fuel_type=ELEC`, `status=E`, `access=public`, `country=US`, `limit=all`
(`developer.nrel.gov` is now an alias of `developer.nlr.gov`; `scripts/probe_nrel_afdc.py`).
Planned: DC fast stations as points `[lon, lat, DC ports, network index, open year]` with names;
per state stations, DC fast stations, level 2 ports and DC fast ports (sums, computed); per
network DC fast stations and ports (sums); every station with every field to
`lake/afdc/stations` (GeoParquet, partition `snapshot`); monthly in `us-grid` (data job).

**Not built yet**: the probe in Actions (2026-10-18) got no key: the repo secret `EPA_API_KEY`
reached the step empty and the API answered `API_KEY_MISSING`. It needs `NREL_API_KEY`
(an api.data.gov key, https://developer.nrel.gov/signup/) as a repo secret; the layer "EV fast
chargers" is listed once the file exists. The station fields were read from a 40-station sample
with the public `DEMO_KEY` (to write the builder; nothing from it is on the map).

## Resource atlases (`scripts/build_atlas.py`, `grid/atlas-*.pmtiles`, `atlas.json`)

Downloaded and processed only in GitHub Actions (`.github/workflows/atlas.yml`, by hand; the
owner approved the downloads). `scripts/probe_atlas.py` reads both files' headers by range
requests:

| Atlas | File | Values |
|---|---|---|
| Global Solar Atlas 2.13 (World Bank, Solargis; CC BY 4.0 per the atlas's terms of use) | `World_PVOUT_GISdata_LTAy_AvgDailyTotals_GlobalSolarAtlas-v2_GEOTIFF.zip`, 362 MB (2026-05-06), `PVOUT.tif` EPSG:4326 | PVOUT: long-term average of daily totals of PV output, kWh/kWp (free-standing c-Si at optimum tilt), 1994/1999/2005/2007/2018/2019 (by region) to 2025 |
| Global Wind Atlas 3 (DTU; CC BY 4.0) | `wind_speed_cog_100m.tif`, 14.07 GB, float32 COG, 0.0025° (~250 m), 80° N to 64° S, no data = NaN; globalwindatlas.info redirects to figshare.com, which answers a bot check (AWS WAF), the same file through `ndownloader.figshare.com` answers | mean wind speed at 100 m, m/s |

| Output | Where | Computed |
|---|---|---|
| Layers "Solar resource", "Wind resource" (Weather) | `grid/atlas-pvout.pmtiles` (28.7 MB), `grid/atlas-wind100.pmtiles` (74.5 MB) on the public bucket | warped to Web Mercator at zoom 7 (mean of the source pixels in each tile pixel), coloured by class, PNG tiles zoom 0–7 (lower zooms by nearest pixel, so classes stay classes). Classes: solar the atlas legend's own 0.2 kWh/kWp-a-day steps from 2.0 to 6.4; wind 1 m/s steps over the atlas's own 0–10 m/s scale (the wind atlas draws a continuous scale, no classes) |
| Check a site, "Around it" | `grid/atlas-pvout-0.1deg.i16`, `grid/atlas-wind100-0.1deg.i16` (int16, 3600 × 1800, row-major from 90° N 180° W; PVOUT × 1000, wind × 100; −32768 = none) | the mean of the source pixels in each 0.1° cell (cells with a value: solar 1,246,598, wind 2,888,422); the card reads one cell by range request. PVOUT a year = daily × 365, as the atlas's own map gives yearly totals (730 = 2.0 × 365) |
| The full rasters | `lake/atlas/atlas-pvout.tif` (COG, 489.5 MB), `lake/atlas/atlas-wind100.tif` (the downloaded COG, 14.07 GB) in the private bucket; `lake/atlas/_catalog.json` lists them under `rasters` | none |

Check 2026-10-18 against the atlas's own site API (`api.globalsolaratlas.info/data/lta`, a
point): Madrid 1,655 kWh/kWp a year at the point, 1,663 in our 0.1° cell (4.555 a day); Berlin
1,071 at the point, 1,069 in the cell.

## Wind and sun layers (`scripts/fetch_wind.py`)

| File | Records | Source |
|---|---:|---|
| `wind.json` | 30 hours (6 back, 24 ahead) x 720 points | Open-Meteo forecast API (best-match weather models, CC BY 4.0, free for non-commercial use): hourly `wind_speed_100m` and `wind_direction_100m`, i.e. at wind-turbine hub height, on a 2-degree grid over lon -25..45, lat 34..72. Model values, not measurements |
| `wind/<YYYY-MM-DD>.json` | the hours of one local day x 720 points | the same, for the archive days (one request per batch over the whole window; on the `eu-days` branch, the newest days bundled) |

Values are passthrough: wind speed at 100 m in 0.1 m/s, its direction in degrees (where
the wind blows from), shortwave radiation in W/m² (global horizontal, the average of the
preceding hour: the sun layer) and total cloud cover in %. The same requests return all
four, so the sun layer costs no extra calls. Archive days fetched before the sun layer
are refetched once by the next archive run. The particles on the map move through a field interpolated between grid points
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

## Shapes and names (`scripts/build_shapes.py`, `zones.json`, `cities.json`)

- **NUTS 2024** (Eurostat GISCO, 1:20M, all levels; © EuroGeographics for the administrative
  boundaries): lake `shapes/nuts` (1,798 regions: 39 / 115 / 299 / 1,345 per level). Passthrough.
- **Bidding zones** built from NUTS 3 regions (the open zone geometries are AGPL): each zone of
  `prices.json` is the union of the regions in `ZONES` (DK1 = Syddanmark, Midtjylland, Nordjylland;
  IT zones by Terna's regions; NO and SE zones by county, approximate where a zone border cuts a
  county); single-zone countries are the country without overseas regions. `zones.json` (simplified
  0.01°) shades the zones in the Prices view, labelled "approximate outline (NUTS regions)";
  lake `shapes/bidding_zones`. Refresh by hand (NUTS changes every few years).
- **Admin-1** (geoBoundaries CGAZ ADM1, CC BY 4.0, 360 MB, Actions only): lake `shapes/admin1`
  (3,224 regions) and `shapes/admin1_simplified` (0.01°).
- **Cities** (GeoNames cities15000, CC BY 4.0): lake `places/cities` (34,167); the 6,284 of
  100,000 people and more in `cities.json` for the search box. Refresh by hand.

## US plant performance (`scripts/build_us_perf.py perf`, `us/plants_perf.json`)

EIA-923 through PUDL's public Parquet (Catalyst Cooperative, CC BY 4.0), read in place with DuckDB:
per EIA plant the newest full year's net generation (2025; sum of
`core_eia923__monthly_generation_fuel`) and the capacity factor: PUDL's own, capacity-weighted over
the plant's generators, where every generator has one (12,697 plants), else computed as generation ÷
(nameplate × 8,760 h) and labelled (1,936). Plus EPA eGRID2023 (public domain): CO₂ (short tons)
and CO₂ rate (lb/MWh) as published; lake `egrid/plants` (12,612 plants, every column). Shown in
the US plant hover. Refresh: by hand (`wave5.yml` group B) when eGRID or the year changes.

## US industrial emitters (`scripts/build_us_perf.py ghgrp`, `us/ghgrp.json`)

EPA GHGRP 2023 (public domain): emissions from the data summary spreadsheet (Direct Point Emitters,
t CO₂e, AR4 GWP, as reported), positions from Envirofacts `PUB_DIM_FACILITY` (all 6,470 found).
Layer "US industrial emitters" (dot area = t CO₂e, colour = the first sector listed, on Climate
TRACE's colours), card in "On the map" (sums computed); lake `ghgrp/facilities`. Refresh by hand
when EPA publishes the next year.

## German redispatch (`scripts/build_germany.py`, `de_redispatch.json`)

netztransparenz.de's open archive `redispatch export 2013-2020` (40,118 measures as the four TSOs
publish them). Computed: energy per month (by the measure's start, UTC), by direction and by
requesting TSO. Card "Redispatch" in Germany's panel; lake `netztransparenz/redispatch`. Measures
since 2021, costs and curtailment (EinsMan) are only in the registered API
(`NETZTRANSPARENZ_CLIENT_ID`, `NETZTRANSPARENZ_CLIENT_SECRET`, api-portal.netztransparenz.de).

## SMARD (`scripts/build_smard_catalog.py`, catalogue only)

Bundesnetzagentur's SMARD chart API (CC BY 4.0, no key): stays an API (no lake copy, no UI);
`agent/catalog/smard.yaml` lists 15 German series (load, generation by source, day-ahead price),
their weekly files from 2014-12-28 and the newest values as examples.

## Planned grid projects (`scripts/build_tyndp.py`, `tyndp.json`)

ENTSO-E TYNDP 2024: the project map's `/api/maps/all` (363 investments and storage projects of 206
projects, as GeoJSON) and each project page (`/api/public/Projects/{type}/{id}`): status,
commissioning year, promoter, and per investment capacity (MW), voltage (kV) and element as the
promoters submitted them (capacity given for 99). Computed: geometry simplified (0.005°). Layer
"Planned grid projects" (Power grid), card in "On the map" (counts by status; capacities not
summed); lake `tyndp/projects`. Refresh by hand (`wave5.yml` group D) when ENTSO-E updates the TYNDP.

## Lines out of service (`scripts/build_transmission_outages.py`, `transmission_outages.json`)

ENTSO-E A78 (unavailability of transmission infrastructure) per border (79 borders, both
directions; per area it answers nothing; German borders under the four TSO control areas and
DE-LU, as Germany publishes them), planned (A53) and forced (A54), the last 30 days and the
next 30, one request at a time in 30-day windows; the card lists a border on both countries; newest revision
per report, withdrawn ones left out. Passthrough: element, type, voltage where named, start, end,
reason, lowest available MW. Card "Lines out of service" in the country panel; lake
`entsoe/transmission_outages`. Daily in `eu-days`, skipped while a Lake ENTSO-E run is active
(the key was banned when both ran).

## Wind and solar seen from space (`scripts/build_grw.py`, R2 `grid/grw.pmtiles`, `grw_countries.json`)

Global Renewables Watch v1.0 (Microsoft, Planet; MIT): 375,197 wind turbines (points) and 86,345
solar arrays (polygons) detected in satellite images up to 2024 Q2, GeoPackages in Web Mercator
(453 MB, Actions only), transformed to lon/lat. Passthrough: every published field (country,
construction year and quarter, land cover, area). Computed: the country outline (`world.json`)
holding each feature's centre, a polygon's area in km², per country and construction quarter the
counts and solar area (sums; the files publish no MW). Tiles by tippecanoe (30.3 MB; small arrays
from zoom 6); layer "Wind and solar seen from space" (Power plants), card in "On the map"; lake
`grw/solar`, `grw/wind`. Refresh by hand when a new release appears.

## Profiles (`scripts/build_profiles.py`, `profiles/*.json`, `us/steo.json`)

- **Eurostat energy balances** (`nrg_bal_c`, CC BY 4.0, API): final energy by sector and fuel,
  newest year (2024), ktoe as published → "Final energy use" in the country report. API only.
- **EIA SEDS** (API v2): per state consumption and production by source, 2024, billion Btu as
  published → US country report and the "Energy by state" card (US panel, Energy tab). API only.
- **EIA STEO** (API v2): residential price and power-sector generation, monthly from 2024; months
  from the release month are labelled forecast → "Short-term outlook" card. API only.
- **EDGAR 2025** (JRC, CC BY 4.0), the GHG booklet: Mt CO₂e (GWP-100 AR5) per country, sector and
  substance 1970–2024 → lake `edgar/ghg_by_sector`; the country report sums the substances per
  sector for 2024 (computed).
- **Energy Institute Statistical Review** (free with attribution), `EI-Stats-Review-ALL-data.xlsx`:
  the site answers scripts with a Cloudflare challenge, so `scripts/browser_fetch.py` downloads it
  with Chromium in Actions and keeps it in `r2://infraatlas-raw/sources/ei/`. Every sheet's values
  as published → lake `ei_review/series` (277,731 values); the country report shows nine items
  (total energy supply, oil, gas, coal, nuclear, hydro, renewables in EJ, electricity in TWh, CO₂
  from energy in Mt) for the newest year, 2025, for 79 countries. Country names are matched to
  ISO3 (pycountry plus a short alias list in the script); regions and totals stay unmatched.
- Refresh: Eurostat, SEDS, STEO, EDGAR by hand (`wave5.yml` group F) when a new year appears; the
  Energy Institute file monthly (`browser-fetch.yml`, rebuilt only when the file changed).

## Files behind a browser check (`scripts/browser_fetch.py`, `browser-fetch.yml`)

Some sites answer scripts with a JavaScript challenge. `browser_fetch.py` opens the source's page in
Chromium (headed under xvfb in Actions), finds the file link, downloads it and keeps it in the
private bucket `r2://infraatlas-raw/sources/<name>/` with `latest.json` (url, sha256, date). An
unchanged file is not uploaded or rebuilt. If the browser is refused too, the owner uploads the file
to `sources/<name>/manual/` and the newest file there is used. A new source is one `SOURCES` entry
(pages, link pattern, refresh, build command). Sources: `ei` (above).

## Japan and Mexico day-ahead prices (`scripts/build_markets.py`, `jepx.json`, `cenace.json`)

- **JEPX** spot summary CSV (Shift-JIS; the download answers only with the spot page as
  referrer): system and nine area prices per 30 minutes, JPY/kWh as published; the card shows the
  newest delivery day's average, lowest and highest (computed). Terms of use not found (jepx.jp's
  site-policy page answers 404). Lake `jepx/spot`.
- **CENACE** SWPML web service, day-ahead PML (MXN/MWh) for every node of CENACE's node catalogue
  (SIN 2,458, BCA 121, BCS 31 nodes on 2026-10-18), 20 nodes per request; per system and hour the
  lowest, median and highest (computed). Nodes are counted, not placed. Lake `cenace/pml`.
- Both daily in `eu-days` (onto the eu-days branch).

## People (`scripts/build_population.py`, `profiles/population.json`, R2 `grid/population-0.1deg.i32`)

JRC GHSL GHS-POP R2023A, epoch 2025, 30 arc-seconds (CC BY 4.0, 484 MB, Actions only). Computed:
people per NUTS 3 and per admin-1 region (sum of the cells whose centre lies inside; 4,569
regions → lake `ghsl/population`); per country the sum of its admin-1 regions, their geodesic
land area and people per km² ("People" in the country report); a 0.1° grid of people per cell
(sum of 12 × 12 source cells, int32, 26 MB on the public bucket) read by "Check a site" for the
people in the cells whose centre lies within 50 km. Refresh by hand.

## Notes

- ENTSO-E allows 400 requests a minute; the scripts ask four at a time. A full snapshot
  (~270 requests) took about a minute on 2026-10-05; single answers range from 0.3 s
  to 50 s.
- Energy-Charts answers 429 to bursts. `scripts/fetch_eu_reference.py` still asks it
  one request at a time for installed capacity.
