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
| `open/countries.json`, `open/world.json` | the same two files from Natural Earth (behind `?shapes=open`) | Natural Earth admin-0 countries 1:10m v5.1.2, public domain, same simplification (`scripts/build_open_shapes.py`); side-by-side check in `docs/research/gisco-replacement.md`; GISCO stays the default until the owner decides (`docs/owner-questions.md`) |

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

## Room to connect, ten more countries (`scripts/build_connect_eu.py`, `connect/<cc>.json`)

The operators' own figures, passed through, one file format: Austria (APG, available feed-in and
offtake per substation, HTML table, monthly; no positions), Bulgaria (ESO, free MW per substation
for generation and consumption by voltage, and "grid expansion needed"), Czechia (ČEPS,
suitability per substation for 2031 and 2036), Germany (TransnetBW only: ranges per substation;
50Hertz and Amprion publish PDFs), Denmark (Energinet and the DSOs, MW per station), Estonia
(Elering, expandable or not, extra fee), Lithuania (Litgrid, free MW for solar, wind, storage per
year), Luxembourg (Creos, per station and voltage, 2026/2030/2035), Malta (Enemalta, kVA and kWp
per substation), Sweden (Svenska kraftnät, per county), Spain's distribution nodes (e-distribución,
CNMC monthly CSV) and GB's six DNO embedded capacity registers (1 MW and more). Computed: the map
class (four MW classes on the feed-in value, or the operator's category), WGS84 positions from
UTM / OSGB / ED50 as each file gives them. Layer "Grid capacity", card per country, site analysis
rows; lake `connect_eu/<cc>`. Refresh: by hand (`wave7.yml` family A). Coverage: docs/COVERAGE.md.

## Every unit, national registers (`scripts/build_registers.py`, `registers/<cc>.json`)

UK: DESNZ REPD (quarterly CSV, every renewable and storage project from 150 kW, operational to in
planning; refused, withdrawn, expired left out) and DUKES 5.11 (major power producers) for the
fuels REPD does not cover (gas, coal, nuclear, oil); OGL v3.0. Denmark: Energistyrelsen's master
data of every wind turbine (monthly xlsx). Sweden: Vindbrukskollen, every turbine built, permitted
or in planning (ArcGIS). Ireland: SEAI wind farms connected (June 2022, CC BY 4.0), at their node's
coordinates. France: ODRÉ national register (Licence Ouverte), no positions: summed per region and
group. Belgium: Elia ods179 contracted units (no positions). Portugal: DGEG's licensed plants (wind,
solar, thermal, small hydro; ArcGIS, CC BY 4.0; wind = the turbines' generator kW summed per park,
others installed kVA, shown as MVA). Czechia: ERÚ's licensed plants (monthly XML), no positions.
Finland's register page answers scripts with 403 (not built).
Computed: fuel groups, totals per status and group, WGS84 positions (OSGB, UTM 32, Irish Grid).
Layers "UK: every project", "Denmark/Sweden: every wind turbine", "Ireland: wind farms" (Power
plants), a register card in the Plants tab; lake `registers/<cc>`. Refresh by hand (`wave7.yml` B).

## CO₂ per kWh from the operators (`scripts/fetch_live_co2.py`, `live_co2.json`, `us/co2.json`)

France: RTE éCO2mix national real time (ODRÉ `eco2mix-national-tr`, Licence Ouverte), every 15 min,
`taux_co2` (g/kWh) and the mix, last 48 h. Spain: REE REData, the national system's daily emission
factor (t CO₂-eq/MWh; shown × 1000 as g/kWh) and emissions per technology, last 30 days. Ireland:
EirGrid Smart Grid Dashboard CO₂ intensity (g/kWh), every 15 min, Ireland and the island. US:
EIA-930 grid monitor files per region (14 xlsx, ~0.5 GB), "CO2 Emissions Intensity for Generated /
Consumed Electricity" (lb/kWh, EIA's estimate; × 453.592 = g/kWh), last 14 days. Passthrough,
only unit conversions. Cards "CO₂ per kWh" (country Now tab; US Live tab). Refresh: every 30 min
in `eu-snapshot.yml` (fr, es, ie), weekly in `us-queues.yml` (us). No lake copy (the sources keep
their history; API-or-Parquet rule).

## Redispatch, countertrading, congestion costs, curtailment (`scripts/build_congestion.py`, `congestion.json`)

ENTSO-E (`ENTSOE_API_KEY`), per control area (Germany per TSO), one request at a time: redispatching
internal (A63, A85) and cross-border (A63, A46, per border and direction), countertrading (A91) and
costs of congestion management (A92). GB: NESO "Constraint Breakdown Costs and Volume" (daily, NESO
Open Data Licence). California: CAISO production and curtailments data (5-min wind and solar
curtailment, yearly xlsx). Computed: MWh = MW × interval, summed per month (up and down shown
together); costs and NESO figures summed per month. Card "Redispatch and congestion" (country Now
tab), "Constraint costs" (GB), "Wind and solar curtailed, California" (US Live tab). Refresh: daily
in `eu-days.yml` (35 days, merged into the year; ENTSO-E skipped while a Lake ENTSO-E run is
active); lake `entsoe/congestion_*`, `neso/constraint_breakdown`, `caiso/curtailment`.

## Prices with the same coverage: GB, Ireland's SEM, US real time (`build_gb_prices.py`, `build_imbalance.py`, `fetch_us_rt.py`)

Ireland: the SEM day-ahead price (ENTSO-E A44, zone IE-SEM, EUR) joins `prices.json` and the day
files. Great Britain (no ENTSO-E prices since 2021): Elexon Market Index Data (APXMIDP, half-hourly,
GBP/MWh, no key) over the twelve months of `prices.json`, converted to EUR with the ECB euro
reference rate of the day (the last published rate on days without one; computed), statistics as
every zone (`build_prices.zone_stats`; no capture prices), the GBP average kept; Elexon system
buy/sell prices (GBP, half-hourly) as GB's imbalance prices in `imbalance.json`, kept in GBP.
US: real-time LMP at the day-ahead file's hubs (gridstatus: CAISO 15 min, ERCOT 15 min, MISO, SPP,
NYISO 5 min, ISO-NE hourly), yesterday and today, as published; card "Real time vs day-ahead".
Refresh: daily in `eu-days.yml`.

## What UK consumers pay (`scripts/fetch_gb_retail.py`, GB in `retail.json`)

DESNZ "International domestic / non-domestic energy prices" (Quarterly Energy Prices, OGL v3.0):
the UK's price per half-year in Eurostat's own bands, pence per kWh. Electricity households (DC,
table 5.6.2) and gas households (D2, 5.10.2) with and without taxes; gas businesses (I3, 5.8.2)
excluding VAT and without taxes. DESNZ has no 500-1,999 MWh electricity band (IC): left empty.
Computed: EUR = pence / 100 / the ECB's average GBP per EUR over the half-year; the pence figures
are kept in `eu.gb`. Card "What consumers pay" (GB says DESNZ). Refresh: Mondays in `eu-days.yml`,
after `fetch_retail_prices.py`. Ofgem's price cap is a ceiling, not an average, so it is not used.

## UK ETS emissions per installation (`scripts/fetch_uk_ets.py`, GB in `ets.json`)

UK Emissions Trading Registry, public report "Compliance Report Emissions and Surrenders" (OGL
v3.0, reports.view-emissions-trading-registry.service.gov.uk, section 5): recorded (verified)
emissions per installation and year, t CO2e, passed through. Operator holding accounts only
(aircraft and maritime left out). Northern Ireland's power stations stay in the EU ETS (XI). The
report has no position or activity and the EEA register has no UK site since 2020, so GB's 747
installations are listed in the panel and the country report (group "Activity not published")
and are not on the map; sums are computed. Refresh: Mondays in `eu-days.yml`, after
`fetch_eu_ets.py`.

## Great Britain's plants offline (`scripts/fetch_gb_outages.py`, GB in `outages.json`)

Elexon REMIT messages (Insights API, no key): events running now (`/remit/list/by-event`, latest
revision), read 40 at a time. Kept: production unavailability, status Active, begun and not ended.
Offline = the message's unavailable capacity (MW, as published); planned or unplanned (shown as
forced). Closures stay published as open-ended outages (Ratcliffe, Fiddlers Ferry, to 2050): an
event begun over 365 days ago or ending over ten years ahead is left out and counted
(`gb.long_term`, shown on the card). Europe's totals are recomputed as the sum of the countries.
Every ENTSO-E zone that answers is now listed, with 0 MW when nothing is offline (`fetch_outages.py`).
Refresh: every 30 min in `eu-snapshot.yml`, after `fetch_outages.py`.

## EV charging in Europe (`scripts/build_ev_eu.py`, `ev_eu.json`)

Counts: European Alternative Fuels Observatory (European Commission), public recharging points per
country and year, AC and DC (`<country>/recharging_points.csv`; the newest year is the year so far),
and per power class now (EU table), for EU-27 and the UK. Where: Germany, BNetzA Ladesäulenregister
(CC BY 4.0, points per facility in operation); France, data.gouv.fr consolidated IRVE file (Etalab
2.0, one row per point); the Netherlands, NDW open data charging point locations (points per
location summed over its connector groups); every other country, OpenStreetMap `amenity=charging_station` (ODbL,
Overpass), one per mapped station, not per point. Computed: points or stations summed per 0.1° cell;
each country says its source and unit. Layer "EV charging" and card. Refresh: by hand (`wave7.yml`
family I); lake `ev_eu/<cc>` (every point or station).

## Gas on the US side (`scripts/fetch_us_gas.py`, `us/gas.json`, `us/gas_pipes.json`)

EIA API v2 (`EIA_API_KEY`, public domain): weekly working gas in storage per region (Bcf, Lower 48
and EIA's regions), Henry Hub spot price (daily, USD/MMBtu), citygate price per state (monthly,
USD/Mcf; EIA publishes no other regional hub price as open data). Computed: the change on the week
and the five-year range (min and max of the same ISO week in the five years before), as EIA's
storage report shows it. Pipelines: EIA "Natural Gas Interstate and Intrastate Pipelines" (U.S.
Energy Atlas, federal ArcGIS org), generalised by ArcGIS to 0.01° and rounded to 3 decimals; layer
"US gas pipelines". LNG terminals stay GEM's world layer. Card "Gas" (US Live tab). Refresh: weekly
in `us-queues.yml`.

## Power cuts, SAIDI and SAIFI (`scripts/fetch_reliability.py`, `reliability.json`)

World Bank, Doing Business "Getting electricity" (API, CC BY 4.0): SAIDI (hours without power per
customer a year, `IC.ELC.SAID.XD.DB1619`) and SAIFI (interruptions per customer,
`IC.ELC.SAIF.XD.DB1619`) for EU-27, the UK and the US, data years 2014 to 2019, measured in the
largest business city (US: New York and Los Angeles); passed through. The series ended with Doing
Business in 2021. CEER's benchmarking reports give national values as PDF tables only and BNetzA's
SAIDI is a press release, so neither is read (not_published as data, docs/COVERAGE.md). Card
"Power cuts" (country Now tab) and the country report. Refresh: on the 1st of the month in `eu-days.yml`.

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

Right-click a place (or "Check a site", or type "latitude, longitude" in the search): a site
analysis of the area around it. The user picks the area's radius (5, 10, 25, 50 or 100 km; 50 by
default); the panel sums what the map's own files hold inside it, and the map frames the area,
dims everything outside it and draws what lies inside: high-voltage lines by voltage (from the
line tiles, every section that comes within the radius), substations, plants by fuel (filled:
operating; rings: building or planned; the largest named), data centres, GB TEC sites, the Dutch
capacity-map area, the link to the nearest line and rings at the radius and half of it. No new
data; the link (`?sel=site:lon,lat,radius`) opens the same analysis.

| Figure | Source | Computed |
|---|---|---|
| Country, US state, US county | `countries.json` (Europe), `world.json`, `us/states.json`, `us/counties.json` | point in outline |
| Nearest line of 220 kV and more (and of 345 kV and more) | `grid/world-hv.pmtiles` on R2 (OpenStreetMap via Overture, `scripts/fetch_world_hv_overture.py`) | straight-line distance (haversine scale, local flat projection) to the nearest segment in the zoom-9 tiles around the site (enough tiles to cover the radius and at least 50 km, at most 3 each way); lines farther than the edge of those tiles are not reported ("none within N km"). Tiles simplified by 6 tile units (about 0.1 km) |
| Nearest line of 100 kV and more (US) | `grid/us-lines.pmtiles` (`scripts/fetch_us_lines.py`) | the same |
| Nearest substation of 220 kV and more, substations within the radius (Europe) | `grid.json` (PyPSA-Eur) | great-circle distance |
| Room to connect: NL | `connect.json` (capacity map) | the area holding the site, its published states and queues |
| Room to connect: GB | `connect.json` (TEC register) | MW contracted and not yet connected per site, sites within the radius |
| Waiting to connect: US | `us/queue.json` (LBNL, per state: MW summed over types, each part of a hybrid under its own type), `us/queues_live.json` (markets, per state and type; not added up because a hybrid counts under each type) | none beyond the files' sums |
| Power plants within the radius: operating, under construction, planned | Europe: `plants.json` (operating) and `world_plants.json` (building, planned); US: `us/plants.json`; elsewhere `world_plants.json` | sums of the map points within 50 km (great-circle) |
| Day-ahead price, hours below zero (Europe) | `prices.json`, every zone of the country (no zone outlines in the files) | as in the Prices tab |
| Retail prices | `retail.json` (Eurostat bands IC and DC, all taxes; EIA per state) | newest value |
| Water risk | `water.json` (WRI Aqueduct 4.0) | the basin holding the site |
| Customer-hours without power (US) | `us_outages.json` (EAGLE-I) | the county holding the site, newest year |
| Renewable share, carbon intensity | `transition.json` (Ember) | newest year with a value |
| Data centres within the radius | `datacentres.json` (OpenStreetMap) | count and distance |
| Solar resource (PVOUT), mean wind speed at 100 m | `grid/atlas-pvout-0.1deg.i16`, `grid/atlas-wind100-0.1deg.i16` on R2 (Global Solar Atlas, Global Wind Atlas; "Resource atlases" below) | the mean of the source pixels in the site's 0.1° cell (built in Actions), read with one range request; a year of PV = the daily total × 365, as the atlas gives it |

## Area dashboard (computed in the app: `frontend/src/lib/area.ts`, `components/AreaCards.tsx`)

The Dashboard tab counts what the map's files hold inside an area: the country clicked, a
dashboard's countries (Europe's GISCO outlines from `countries.json`, the world's coarse ones from
`world.json` elsewhere), a polygon drawn on the map (`?poly=`) or a circle around a place
(`?circle=`; a city from the search opens 25 km around it). Nothing is estimated; each card says how
it counts. Countries are counted by the records' own country (a code or a name on each record, or
the file's per-country totals): fast, and it includes records without a position (EU ETS: Germany
1,818 installations, 78 placed on the map). A drawn polygon or a circle counts by position. The
grids read by range request (people, resources, flood) are read only for areas under 2 million km².

| Card | Files | Computed |
|---|---|---|
| The area | outline; `grid/population-0.1deg.i32`; atlas lookups | size on the sphere from the outline (Germany: 355,268 km² from the 1:20M outline, 357,600 official); people: sum of the GHSL 0.1° cells whose centre lies inside (every row, one range request per row; not summed when the area spans more than 900 rows); solar and wind: mean of the atlases' 0.1° cells inside (every n-th row and column past 240 rows, said on the tile) |
| Electricity (country areas) | `stats.json`, `reference.json`, `transition.json` | demand and generation by source now: sums of the countries' newest intervals; renewable share = Σ(country share × its generation) / Σ generation; installed capacity (ENTSO-E A68) summed; Ember TWh by source summed for the newest year all countries have |
| Power plants | `plants.json`, `us/plants.json`, `world_plants.json` | MW and map points inside by type and status. Europe: powerplantmatching (operating, 20 MW+); the US: EIA-860M (every status); elsewhere, and building or planned in Europe: GEM. GEM points inside the US, and GEM operating points inside Europe's outlines, are left out (no double count). Checked 2026-10-22: 679 points / 99,444 MW inside Germany's outline vs 678 rows / 99,443 MW tagged DE |
| Transmission grid | `grid.json` (Europe) | km of AC lines per voltage band and of HVDC links: segments whose midpoint lies inside; substations of 220 kV+ inside. Germany: 25,610 km, 779 substations (2026-10-22) |
| Room to connect | `connect.json` (GB), `connect/<cc>.json` | GB: MW of TEC projects not yet connected, summed per site inside; other operators: the count of published points inside (their values stay on the map) |
| Every unit | `registers/<cc>.json`, `mastr/municipalities.json`, `us/turbines.json`, `us/solar.json` | units and MW inside per register group; Germany per municipality by its label point |
| Demand and industry | `datacentres.json`, `ev_eu.json`, `us/ev_chargers.json`, `hydrogen.json`, `gem/*` | counts inside; EV points in Europe summed over the 0.1° cells whose centre lies inside; GEM capacity summed over operating records |
| Emissions | `ets.json`, `us/ghgrp.json`, `ctrace.json` | sums over the facilities placed inside; reported and modelled kept apart |
| Gas, oil and coal | `gem/pipelines_*.json`, `gem/*`, `gas.json` | operating pipeline km by segment midpoints; counts inside |
| Land and risk | flood lookups (`constraints.json`), `protected.json`, `offshore_wind.json` | flood: share of the lookup cells inside with any depth mapped (every n-th row and column past 120 rows, said on the tile); Natura 2000 for country areas: the EEA's per-country counts and km² summed |

Files load only when an area needs them: a country's register or capacity map when the area
reaches that country (its outline's box), Europe's files when the area reaches Europe.

## Country figures at continent scale (`frontend/src/map/summaryLayers.ts`)

While the countries are not coloured by something else and the map is zoomed out (below zoom
5.4), the first dataset on that has a per-country figure shades each country by its rank and
writes the figure under its name; zoomed in, the points take over. The Datasets panel's key says
which figure. Figures: verified CO₂ per country, every installation (EU ETS registry totals, newest
year); installed capacity (ENTSO-E A68 in Europe, Global Energy Monitor's operating plants
elsewhere, GW); public charging points (EAFO, newest year, AC + DC); data centres per country
(OpenStreetMap, `datacentres.json`); modelled CO₂e (Climate TRACE rows summed per country);
offshore wind farm areas per country (EMODnet, every status).

## Hexagon maps at country scale (`frontend/src/lib/measures.ts`, `map/hexLayers.ts`)

Below zoom 7.2 (countries and regions) a dataset's records are summed into flat-top hexagons laid
out on a local grid for the latitude in view (5° steps); the circumradius follows the zoom (45 km at
zoom 4.5 down to 10 km at zoom 7, said in the key and the tooltip as "about N km across"). From zoom
7.2 (cities, sites) every record is drawn again. With a dashboard area under 3 million km² only the
records inside it are summed. One variable: a hexagon is coloured by its largest type, its strength
the square root of its share of the largest hexagon. Two variables: a 3×3 bivariate colour, each
variable's classes the thirds of the hexagons with a value (the breaks are in the key). Variables
(lib/measures.ts): operating capacity (MW; Europe's powerplantmatching file, EIA-860M in the US,
Global Energy Monitor elsewhere, GEM's points inside the Europe and US boxes left out), units in the
national registers (MW; MaStR per municipality by its label point, REPD, Energistyrelsen,
Vindbrukskollen, SEAI, DGEG, USWTDB, USPVDB; operating units), verified CO₂ (EU ETS placed
installations, newest year; EPA GHGRP), modelled CO₂e (Climate TRACE), charging points (EU per 0.1°
cell, US DC fast ports), data centres (OpenStreetMap), MW waiting to connect (GB, NESO TEC).

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
| `korea.json` | 1 grid, 13 sources | KPX (Korea Power Exchange) real-time pages (`scripts/fetch_kpx.py`, no key; `scripts/probe_kpx.py`), every 5 minutes: demand, supply capacity, reserve (MW and %) and generation by source (MW, passed through, rounded to 0.1 MW). Behind-the-meter and PPA solar are KPX's own estimates (listed in `estimated`); ESS and pumped storage are net. Computed: `total_mw` = sum of the source columns at the newest reported interval, `metered_total_mw` the same without the two estimated solar columns. Licence: KPX's generation data on data.go.kr (15106744) is marked no restriction on use, the KPX site footer says all rights reserved; shown on the owner's decision (2026-11-06, owner question 4). Refreshed with every snapshot run. The marker is placed for reading |
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
| `cables.json` | 1,712 cables (2,621 ways joined into 2,321 lines, 2026-10-22) | OpenStreetMap (ODbL) via Overpass, `scripts/fetch_cables.py`: ways tagged `power=cable` with `location=underwater` or `submarine=yes`. Ways of one class meeting end to end (a shared end node, no third way there) are joined into one line first (computed; kV the highest of its ways, name the most common), so a cable draws whole. Class computed from the tags: HVDC (`frequency=0`), AC from 110 kV, smaller (mostly offshore wind farm cables), untagged. Some ways tagged underwater run mostly over land (tagging errors): a cable is kept, whole and with its landfall, only when at least half its length lies outside the land outlines (GISCO 1:20M, computed); cables in lakes and narrow fjords drop out. Simplified to about 500 m. Well mapped around Europe, sparse elsewhere. Shown on the World tab and as the live map's "cables" chip |

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
next 30, in 30-day windows, four requests at a time (~1,000 requests, about 22 min); the card lists a border on both countries; newest revision
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

## Room to connect in one schema (`scripts/build_connect_harmonised.py`, `connect/harmonised.json`)

Brief 23. Every record each grid operator publishes is one row: `cc`, `operator`, `level`, `id`,
`name`, `kind` (node or area), position as published, `kv`, `mw_gen` / `mw_load` (free MW for new
generation / demand, as published), `mva_gen` / `mva_load` (where an operator publishes MVA or kVA:
not converted, that would need a power factor), `mw_queue` (MW waiting, as published or summed per
node, said per operator), `class` / `class_load` (available, limited, queue, none: the operator's
own classes mapped one to one, table below; an operator that publishes MW only: more than 0 MW
available, 0 MW none, no other threshold), and per operator `as_of`, `source`, `url`, `licence`.
Nodes without coordinates are placed on an OpenStreetMap substation (Overpass, ODbL) only where the
normalised name is unique (`matched` per operator). Nothing is estimated. Shown: the Grid capacity
layer (dots sized by free MW, outlines for areas, the four class colours, a demand/generation
switch), the colourings "Free capacity for new generation / demand" (MW summed per country, computed;
Red Eléctrica's nodes share capacity and are not summed) and the card "Room to connect". Builders:
`build_connect_h23.py` (the operators added by brief 23, one `connect/h_<key>.json` each) and the
earlier per-operator scripts. Lake `connect/harmonised`. Refresh: by hand (`wave7.yml` job R).

| cc | Operator | Level | Rows | On the map | Licence | Class mapping |
|---|---|---|---|---|---|---|
| AT | Austrian Power Grid (APG) | transmission | 83 | 52 (52 by name) | public notice (Regulation (EU) 2019/943 Art. 50(4a)); reuse with the source named | MW free > 0 -> available; 0 MW, flexible connection possible -> limited; 0 MW, no flexible connection -> none |
| BG | Elektroenergien Sistemen Operator (ESO) | transmission | 447 | 447 | public web map; reuse with the source named | connection possible -> available; grid expansion needed first -> none |
| CZ | ČEPS | transmission | 36 | 36 | public web map; reuse with the source named | suitable -> available; conditionally suitable -> limited; not suitable -> none |
| DE | 50Hertz | transmission | 75 | 75 | 50Hertz website terms (public information under §14e EnWG); reuse with the source named | MW only: more than 0 MW free -> available, 0 MW -> none; a location without a published MW has no class |
| DE | Amprion | transmission | 10 | 7 (7 by name) | Amprion website (information only, without warranty) | a potential connection point with an earliest commissioning year (2032-2035) -> limited; 'only load connections possible' -> generation none |
| DE | TransnetBW | transmission | 52 | 37 (37 by name) | public web map; reuse with the source named | medium-term -> limited; long-term -> limited; not available -> none |
| DK | Energinet and the Danish DSOs | transmission | 1,261 | 1,261 | public web map; reuse with the source named | MW only: more than 0 MW free -> available, 0 MW -> none |
| EE | Elering | transmission | 163 | 163 | public web map; reuse with the source named | expandable (type A) -> available; not expandable (type B) -> none |
| ES | Begasa | distribution | 23 | 23 | CC BY 4.0 | MW only: more than 0 MW free -> available, 0 MW -> none; generation and consumption joined by substation and voltage |
| ES | E-Redes España | distribution | 191 | 191 | CC BY 4.0 | MW only: more than 0 MW free -> available, 0 MW -> none; generation and consumption joined by substation and voltage |
| ES | Red Eléctrica (transmission nodes) | transmission | 937 | 451 (451 by name) | REE terms of use (reuse with the source named) | MW only: more than 0 MW free -> available, 0 MW -> none (demand: CEP with ride-through, the first column) |
| ES | Viesgo | distribution | 179 | 179 | CC BY 4.0 | MW only: more than 0 MW free -> available, 0 MW -> none; generation and consumption joined by substation and voltage |
| ES | e-distribución (Endesa) | distribution | 1,859 | 1,859 | published under CNMC Circular 1/2024; reuse with the source named | MW only: more than 0 MW free -> available, 0 MW -> none (demand: firm capacity available); joined by substation code and voltage |
| FI | Elenia | distribution | 169 | 169 | Elenia public web map (no licence stated) | MW only: more than 0 MW free -> available, 0 MW -> none |
| FR | RTE and the distribution operators (Capareseau) | transmission | 3,116 | 3,116 | Capareseau: reuse allowed with the source named | MW only: more than 0 MW free -> available, 0 MW -> none, on 'capacité réservée au titre du S3REnR qui reste à affecter' (INFO_NA) |
| GB | NESO (TEC register) | transmission | 1,053 | 294 | NESO Open Data Licence | a site with MW waiting (cumulative capacity - MW connected, summed per site, computed) -> queue |
| GB | National Grid Electricity Distribution (NGED) | distribution | 1,182 | 1,182 | WPD Open Data Licence | NGED's constraint colour: green -> available, amber -> limited, red -> none (generation and demand each) |
| GB | Northern Powergrid | distribution | 670 | 670 | Northern Powergrid Open Data Licence v1.0 | MW only: more than 0 MW free -> available, 0 MW -> none (generation headroom genhr); demand headroom demhr kept as published (MVA) |
| GB | Scottish and Southern Electricity Networks (SSEN) | distribution | 998 | 998 | CC BY 4.0 | SSEN's RAG status: Green -> available, Amber -> limited, Red -> none; demand headroom is MVA, kept as MVA |
| GR | HEDNO | distribution | 454 | 446 | HEDNO public web application (no licence stated) | HEDNO's availability colour: green (over 2 MVA on both criteria) -> available, orange (about 2 MVA on one) -> limited, red (zero) -> none; mva_gen = the smaller of the thermal and the short-circuit margin (both published, the binding one taken) |
| HR | HOPS | transmission | 199 | 153 (153 by name) | HOPS website (public information) | HOPS's categories: A (up to 50 MW) -> limited, B (up to 100 MW) -> available, C (over 100 MW) -> available, / (0 MW or no free bay) -> none |
| HU | MAVIR and the DSOs (station list) | transmission | 168 | 168 | MAVIR website (disclaimer sheet in the file) | spare bays + free bays/cells offered > 0 -> available, 0 -> none; injection capacity kept as published (MVA) |
| HU | MVM Démász | distribution | 43 | 31 (31 by name) | operator website (public information) | MW only: more than 0 MW free -> available, 0 MW -> none, for load only (the table is 'vételezési célú', for withdrawal); no generation figure published |
| HU | MVM Émász | distribution | 32 | 21 (21 by name) | operator website (public information) | MW only: more than 0 MW free -> available, 0 MW -> none, for load only (the table is 'vételezési célú', for withdrawal); no generation figure published |
| IE | ESB Networks | distribution | 657 | 657 | ESB Networks website terms | MW only: more than 0 MW free -> available, 0 MW -> none, on firm generation available (MW); demand available is MVA, kept as published |
| IT | Terna (Econnextion) | transmission | 21 | 21 | dati.terna.it (terms of use not found; figures shown with the source named) | requests to connect renewables per region -> queue (MW requested, summed per region, computed) |
| LT | Litgrid | transmission | 309 | 309 | public web map; reuse with the source named | MW only: more than 0 MW free -> available, 0 MW -> none, on the larger of the free MW for solar and for wind (both published) |
| LU | Creos | transmission | 43 | 43 | public web map; reuse with the source named | MW only: more than 0 MW free -> available, 0 MW -> none, on the largest free MW of the station's voltage levels |
| MT | Enemalta | distribution | 1,332 | 1,332 | public notice (Regulation (EU) 2019/943 Art. 57(3)); reuse with the source named | kWp for renewables and kVA for load as published (shown as MVA/MWp, divided by 1,000); class: more than 0 -> available, 0 -> none |
| NL | Netbeheer Nederland (regional operators) | distribution | 923 | 923 | Esri Nederland terms of use | 0 capacity available, no queue -> available; 1 capacity limited, no queue -> limited; 2 under study, with a queue -> queue; 3 shortage of capacity, with a queue -> none |
| PL | PSE | transmission | 182 | 51 (51 by name) | PSE website (public information under the Energy Law) | requests in the Art. 7(8l) list -> queue; switchgear without a free connection bay -> none |
| PT | E-REDES | distribution | 470 | 378 (378 by name) | CC BY 4.0 | MVA only (reception capacity, HV): more than 0 -> available, 0 -> none |
| SE | Svenska kraftnät | transmission | 21 | 21 | public web map; reuse with the source named | MW only: more than 0 MW free -> available, 0 MW -> none |
| SI | ELES | transmission | 46 | 46 | ELES public web map (no licence stated) | MW only: more than 0 MW free -> available, 0 MW -> none |
| SK | Východoslovenská distribučná (VSD) | distribution | 32 | 32 | operator website (public information) | MW only: more than 0 MW free -> available, 0 MW -> none |
| SK | Západoslovenská distribučná (ZSD) | distribution | 63 | 57 (1 by name) | operator website (public information) | MW only: more than 0 MW free -> available, 0 MW -> none |
| US-PGE | Pacific Gas and Electric (GRIP) | distribution | 776 | 776 | PG&E: 'available for general public consumption' | a substation with queued distributed generation -> queue; PG&E publishes hosting capacity per line section, not per substation |
| US-SCE | Southern California Edison (DRPEP) | distribution | 884 | 884 | SCE DRPEP (information purposes only; no use restriction stated) | MW only: more than 0 MW free -> available, 0 MW -> none |
| US-SDGE | San Diego Gas & Electric (ICA) | distribution | 107 | 107 | SDG&E public ICA map (no licence stated) | a substation with queued generation -> queue; SDG&E publishes hosting capacity per grid cell, not per substation |

Not added (evidence in data/coverage.yaml): TenneT DE and the E.ON DSOs, Elia, AST, Delgaz,
E-Distribuție and TSO Cyprus behind Cloudflare's check (HTTP 403); i-DE (503), UFD (403); OPUS
TITÁSZ (its PDF does not say load or generation); ELES's DSO layer (upper bounds only); ConEd,
National Grid, Xcel, Duke and Dominion (per feeder line or grid cell, not nodes); ENWL, SPEN and
UKPN (keys: `ENWL_API_KEY`, `SPEN_API_KEY`, `UKPN_API_KEY`).

## Room to connect, brief 26 (`scripts/build_connect_h26.py`, `connect/h_<key>.json`)

The operators brief 26 adds, in the same harmonised rows (one `connect/h_<key>.json` each, read
by `build_connect_harmonised.py`). Research and every operator checked:
`docs/research/room-to-connect.md`; probe `scripts/probe_connect_h26.py`, its output in
`docs/research/probe_connect_h26.txt`. Nodes without published coordinates are placed on an
OpenStreetMap substation of the same unique name in the Actions job (`wave7.yml` job R); a file's
`osm_area` names the area searched when the operator's code is not a country (`US-CA` for CAISO),
and `match_name` the name looked up when it differs from the label (TEİAŞ: the transformer centre
without its busbar). `summable: false` marks figures that share the grid (the US Order 2023
heatmaps study each bus alone), so no country sum adds them.

| cc | Operator | Level | Rows | On the map | Licence | Values and class mapping |
|---|---|---|---|---|---|---|
| AT | Energienetze Steiermark | distribution | 53 | 44 (44 by name) | operator website (public information) | free feed-in capacity (FEK) per substation, available MW (booked MW not drawn); MW only: more than 0 MW free -> available, 0 MW -> none |
| CH | Swissgrid | transmission | 151 | 102 (102 by name) | Swissgrid public PDF (no licence stated) | additional generation and load per 220/380 kV substation, 2026 base case, MVA as published (capped at 300 MVA); more than 0 MVA -> available, 0 -> none; 2030-2040 and the flexibility cases not drawn |
| CZ | PREdistribuce | distribution | 25 | middle of each area's bounding box (computed) | public web map (no licence stated) | 'Volná kapacita' per 110 kV supply area: more than 0 -> available, 0 -> none; the layer states no unit, so no figure is drawn |
| FI | Helen Sähköverkko | distribution | 25 | middle of each area's bounding box | public web map (no licence stated) | free MV capacity for consumption (MVA, data 05/2025); more than 0 MVA -> available, 0 -> none |
| GB | NIE Networks (Northern Ireland) | distribution | 265 | as published | capacity map terms & conditions | demand and generation headroom per BSP and primary (MVA; dual primaries one row per transformation); more than 0 MVA -> available, 0 -> none; 'Contact for Info' stays empty |
| HR | HEP ODS | distribution | 488 | 441 (440 as published, 1 by name) | public web map (no licence stated) | free capacity for RES (kW, shown in MW) and pending applications (`mw_queue`) per substation, data date 2026-10-01; MW only |
| SE | Vattenfall Eldistribution (regional network) | distribution | 775 | as published | public web map (no licence stated) | MW per technology and years to a possible connection; mw_gen = wind, mw_load = 'medium' consumption, for the earliest horizon each station lists (in the name); more than 0 MW within 1-2 years -> available, only in 2-3 or 3-5 years -> limited, 0 MW -> none |
| SE | Vattenfall Eldistribution (local networks) | distribution | 282 | middle of each area's bounding box; areas simplified to ~200 m | public web map (no licence stated) | the same, per local supply area |
| TR | TEİAŞ | transmission | 1,132 | 593 (593 by the centre's name) | public announcement (no licence stated) | remaining unlicensed solar and wind capacity allocatable from the distribution level per transformer centre, busbar and EDAŞ/OSB (MWe, 01.10.2026, EPDK decision 14353); MW only |
| US-AVA | Avista | transmission | 214 | as published | public heatmap (no licence stated) | per bus the largest tested injection (20-300 MW steps) with no overloaded element (computed from MW_Available per step and element; a lower bound); MW only; not summable |
| US-CAISO | CAISO | transmission | 833 | 397 (by name in California; the heatmap encodes its coordinates: not decoded) | public heatmap (no licence stated) | `trlim` (transmission capacity, MW) per bus, study `2025_TPD` (`C15_Reassessment`, `Cluster15` not drawn); MW only, a negative value -> none; not summable |
| US-IPC | Idaho Power | transmission | 216 | as published | public heatmap (no licence stated) | maximum injection per substation (MW); MW only; not summable |
| US-LGEKU | LG&E and KU | transmission | 745 | as published | public heatmap (no licence stated) | transfer limit per bus: the newest study year, the lowest over its seasons (computed); MW only; not summable |
| US-PGE-OR | Portland General Electric | transmission | 226 | as published (multipoint, first point) | public heatmap (terms on the item page) | available capacity per point of interconnection (MW); MW only; not summable |

Not added: the four small Finnish DSOs on Rejlers-hosted maps (MVA bands, no side), Elenia's
storage layer and Vattenfall's other technologies (fields the schema has no place for), National
Grid NY and Eversource MA/NH feeder hosting capacity (lines: a `line` kind and PMTiles, next step),
and every operator listed in the research file as interactive, refused, login or behind a browser
check (data requests there). The Brotli-encoded CAISO file needs the `brotli` package (a project
dependency). Refresh: by hand (`wave7.yml` job R, after `build_connect_h23.py`).

## Room to connect: France (`scripts/build_connect_more.py fr`, `connect/fr.json`)

Capareseau (RTE and the distribution operators; re-use allowed with the source named): every
substation's S3REnR values from the site's region files (position, values by code) and the code
labels from its CSV export (3,116 substations). Passed through; numbers parsed where a value is a
number. Shown: "capacity reserved under the S3REnR still to allocate" (MW) in four classes on
"Grid capacity" (new generation), card (count and sum, computed), Check a site (sum within 50 km,
computed). Lake `capareseau/substations`. Refresh by hand (`wave6.yml` group A).

## Room to connect: Italy (`build_connect_more.py it`, `connect/it.json`)

Terna Econnextion via the dati.terna.it download center (JSON): requests to connect renewables
(`FER`) and storage (`Accumuli`) to the transmission grid by region and province, MW and requests
as published. Regions joined to NUTS-2 2024 (GISCO, simplified 0.01°; Trentino-Alto Adige =
ITH1 + ITH2). Computed: totals per region (shading in four classes, feed-in side), per source.
Terms of use not found on dati.terna.it. Lake `econnextion/requests`. Refresh: group A (monthly
at the source).

## Room to connect: Belgium (`build_connect_more.py be`, `connect/be.json`), blocked

Elia's capacity for new decentralised generation: elia.be answers scripts with HTTP 403 and kept
Chromium on Cloudflare's "Just a moment..." page in two Actions runs (2026-10-19), and Elia's and
Fluvius' open-data portals hold no capacity set. `scripts/browser_fetch.py elia_capacity` (monthly
in `browser-fetch.yml`) builds it from a file the owner uploads to
`r2://infraatlas-raw/sources/elia_capacity/manual/`; the card and lake table follow.

## Room to connect: Portugal (`build_connect_more.py pt`, `connect/pt.json`)

E-REDES open data `capacidade-rececao-rnd` (CC BY 4.0): reception capacity per HV/MV substation
(MVA), the RARI and newest-quarter values as published (470 substations, 3T2026). E-REDES gives no
positions: card only (count with HV capacity left, computed; largest). Lake
`eredes_capacity/substations`. Refresh: group A (quarterly at the source).

## Room to connect: Ireland (`build_connect_more.py ie`, `connect/ie.json`)

ESB Networks' Available Capacity Heatmap download (xlsx, July 2026; website terms): every
transformer's installed MVA, demand available (MVA), firm and non-firm generation available (MW),
parent constraint, comment and position as published (46,527 rows). The map, card and Check a site
use the 38 kV and 110 kV stations and MV transformers (657); the lake keeps every row
(`esb_heatmap/transformers`). EirGrid publishes no machine-readable heatmap. Refresh: group A.

## Room to connect: Poland (`build_connect_more.py pl`, `connect/pl.json`)

PSE: the list under Art. 7(8l) of the Energy Law (886 requests, conditions and agreements on the
transmission grid as of 2026-08-31; MW, type, stage and dates as published) and the list of PSE
switchgears with no free connection bay (69, 2026-02-04). No positions: card only (counts and MW
per stage, computed). Lake `pse_capacity/*`. Refresh: group A (PSE updates monthly).

## Substations worldwide (`scripts/build_grid_more.py substations`, R2 `grid/world-substations.pmtiles`)

From our own lake (`overture_power/sites`, release 2026-09-23.1; OpenStreetMap via Overture, ODbL):
870,774 substations as points (centre of a mapped outline, computed), kV as tagged, name, operator;
tippecanoe zoom 4-9 (25 MB). Check a site reads the zoom-9 tiles outside Europe: nearest
substation and the count within the tiles read (distance to their edge). Refresh with the Overture
extract (group B).

## Germany: grid operator per municipality (`build_grid_more.py operators`, `de_grid_operators.json`)

MaStR in the lake (snapshot 2026-10-17, dl-de/by-2-0): each unit's location -> its grid
connection points -> the grid operator's MaStR number -> the operator's name. Computed per
municipality (AGS, 11,179): the operator with most units connected, its units, the number of
operators. Check a site: "Grid operator of the municipality". Lake `mastr_grid/operators`. Refresh
after each MaStR snapshot (group B).

## US utility service territories (`build_grid_more.py utilities`, `us/utilities.json`)

EIA-861 service territories via PUDL (`core_eia861__yearly_service_territory`, in place, CC BY 4.0):
the utilities reporting service in each county, 2025 (3,133 counties, 2,904 utilities), as
reported. Check a site lists those serving the site's county (county outlines from the outages
layer); the state card counts utilities per state (computed). No lake copy. Refresh: group B yearly.

## Sea cables and pipelines (`build_grid_more.py emodnet`, `sea_cables.json`)

EMODnet Human Activities (CC BY 4.0, WFS, no key): the national power-cable layers
(`pcablesbshcontis`, `pcablesnve`, `pcablesrijks`, `pcablesshom`; 1,186 features) on "Undersea power
cables", and `pipelines` (3,951) with gas, oil and condensate on the pipelines layers (mixed
hydrocarbons on both; water, chemicals and sewage left off). Lines simplified 0.002°; attributes
as published. API (no lake copy). Refresh: group B.

## Protected areas (`scripts/build_constraints.py protected`, R2 `grid/protected.pmtiles`, `protected.json`)

Natura 2000 end 2024 (EEA; 27,173 sites) and PAD-US 4.1 Fee (USGS, public domain) from the
publishers' ArcGIS services as GeoJSON with their generalisation (maxAllowableOffset 0.0005°,
~50 m): the 1.36 GB GeoPackage and 1.01 GB GeoParquet are over the download limit. Asked by
OBJECTID range, four ranges at a time, a failing range asked again in halves: paging by
resultOffset sorted the whole layer for every page and PAD-US (296,456 areas) answered HTTP 524
from offset 2,500 (wave 6 run, 2026-10-19), ~105 s per 50 areas when it answered; ID ranges answer
in 1-6 s (2026-10-21). Passed through: code, name, type, area, PAD-US designation, manager, GAP
status. Computed: counts and areas per country/state; Check a site: areas within 10 km and the
share of that circle covered (points 0.5 km apart). Lake `protected/*`. Refresh: group P yearly.
A source that still fails is skipped and named under `failed` in `protected.json`. PAD-US 4.1 Fee
(296,456 areas, 57 states and territories, 2026-10-21) holds every GAP status, marine monuments at
their full extent and overlapping records (Papahānaumokuākea under HI and again under `UNKF`, the
Pacific Remote Islands twice): its acres summed nationally (9.4 million km²) exceed the US land
area, so the card shows the count of areas and no national area sum.

## River flood hazard (`build_constraints.py flood`, R2 `grid/flood-{eu,world}.pmtiles`, lookups)

JRC river flood hazard maps, 100-year return period (CC BY 4.0): Europe at 100 m (171 MB zip), the
world at 30 arc-seconds (49 MB). Water depth in JRC's five classes (under 0.5, 0.5-1, 1-2, 2-4,
4 m or more) as PNG tiles (Europe zoom 0-9, world 0-7) and lookup grids of the deepest class per
cell (computed; Europe 0.01°, world 0.05°; uint8 read by HTTP range in Check a site). Class rasters
as COG in `lake/flood/`. Refresh: group C when JRC updates.

## Major roads and railways (`build_constraints.py roads`, R2 `grid/roads-rail.pmtiles`)

Overture transportation segments (OpenStreetMap, ODbL), newest release: roads of class motorway,
trunk and primary and standard-gauge railways in Europe and the US (bounding boxes), simplified
0.0002°; tiles zoom 4-9 (layers `roads`, `rail`). Check a site: straight-line distance to the
nearest of each within the tiles read. Lake `overture_transport/segments`. Refresh: group K.

## Hydrogen projects (`scripts/build_coming.py hydrogen`, `hydrogen.json`)

European Hydrogen Observatory, "Hydrogen production and consumption projects" (Dec 2025 xlsx;
European Commission re-use policy): 238 projects in operation or under construction with name,
city, country, start year, production capacity (MW), process, end use, consumption (t/year),
position and stage as published. Layer "Hydrogen projects" (Industry & data), card (counts and MW
per stage, computed). Lake `hydrogen/projects`. Refresh: group D (the Observatory updates yearly).

## Renewable auctions (`build_coming.py auctions`, `auctions.json`)

AURES II auction database (Mendeley Data, doi 10.17632/2h9jpzy3wx.1, CC BY 4.0): 820 auction rounds
in 20 countries, 2011-2021, with date, technologies, status, awarded capacity (kW; MW computed) and
awarded prices in ct/kWh as published. Card "Renewable auctions" in the country's Prices tab
(newest rounds; awarded MW summed, computed). aures2project.eu answered 520. Lake `aures/auctions`.
Static (the project ended).

## Technology costs (`build_coming.py atb`, `costs.json`)

NREL Annual Technology Baseline 2025 v1.0.0 (OEDI, CC BY 4.0, 321 MB CSV): LCOE, CAPEX, fixed O&M
and capacity factor of each technology's default detail, Moderate scenario, R&D case (the edition
publishes no Market case without tax credits), 30-year cost recovery, 2025/2030/2035/2050, as
published. Card "What new capacity costs" (World Capacity tab, US Retail tab). Lake
`atb/electricity` (every row). IRENA's cost data: blocked (below). Refresh: group D yearly.

## Planned gas projects (`build_coming.py gas`, `gas_projects.json`)

ENTSOG TYNDP 2026 Annex A (xlsx): 347 projects with code, name, country, promoter, maturity,
commissioning years and CAPEX (where not confidential) as published; pipeline km per project summed
over its sections (computed). No positions: the layer "Planned gas projects" draws one ring per
country (count, computed) at its label point; card by category and maturity. Lake
`entsog_tyndp/projects`. Refresh: group D per TYNDP.

## Greenhouse-gas inventories (`build_coming.py ghg`, `profiles/ghg_inventory.json`)

National inventories reported under the UNFCCC and the EU (EEA data) as Eurostat publishes them
(`env_air_gge`, API, CC BY 4.0): Mt CO2e by CRF sector (totals with and without LULUCF, energy and
its parts, industrial processes, agriculture, LULUCF, waste), the newest year (2024, 32 countries
and the EU). The EEA datahub page answered 404. Section in the country report. API only.

## US electric disturbances (`scripts/build_us_reliability.py oe417`), blocked

DOE OE-417 annual summaries on oe.netl.doe.gov: from GitHub Actions the host answered
"Network is unreachable" (probe, httpx) and "Could not resolve host" (build, curl -4). The script,
the card ("Electric disturbances" in the US outages card) and the test are in place; it runs when
the host answers.

## FERC 714 planning-area demand (`build_us_reliability.py ferc714`, `us/ferc714.json`)

FERC Form 714 hourly demand per planning area via PUDL (`out_ferc714__hourly_planning_area_demand`,
in place, CC BY 4.0): the newest year with 80+ planning areas (2025, 88 with 300+ days), daily mean
of the hourly demand as reported (computed; PUDL's imputed values not used). Region from the
planning area's balancing authority (EIA's BA codes); 39 without one show under the whole country.
US region card "Demand per planning area". No lake copy. Refresh: group E yearly.

## France regional mix (`scripts/build_regional_live.py fr`, `fr_regions.json`)

RTE éCO2mix régional temps réel (ODRÉ `eco2mix-regional-tr`, Licence Ouverte, no key): per region
the newest 15-minute values (consumption, generation by source, battery, physical exchanges, MW as
published) and the last 24 hours of consumption; each region's NUTS-1 id for the agent (12
regions; Corsica is not in the real-time set). Card "Regions" in France's Now tab. Refreshed with
every snapshot (`eu-snapshot.yml`). API only.

## Spain regional mix (`build_regional_live.py es`, `es_regions.json`)

Red Eléctrica REData `generacion/estructura-generacion` by autonomous community (`geo_limit=ccaa`,
no key): generation per technology, monthly, the last 13 months, MWh as published (daily answers
were 500/502; Incapsula refuses fast requests, so one every 2 s). Card in Spain's Now tab (the last
full month, summed per community, computed). Daily in `eu-days.yml`. API only.

## New Zealand live (`build_regional_live.py nz`, `nz.json`)

Transpower's System Operator live data (generation sourced from em6): generation and capacity by
fuel (MW) and 5-minute demand for NZ and each island, as published. "Live grids" marker, card in
the World panel and its region panel. The Electricity Authority's EMI datasets (CC BY 4.0, monthly
CSVs on emidatasets.blob.core.windows.net) are in the agent catalogue. Every snapshot. API only.

## South Africa live (`build_regional_live.py za`, `za.json`)

Eskom's data portal pages link its hourly demand and station build-up CSVs under
`wp-content/uploads/2026/07/`, which answer HTTP 404 since October 2026; the same file names answer
under the current month's folder (`uploads/2026/10/`, checked 2026-10-21). The script asks the
page's link first, then the same name in this month's and last month's folder. The files list hours
out of order and the demand file runs a week of forecasts past its measured hours: rows are sorted
by hour, rows without any value left out, the last 336 kept. Passthrough: those rows and the
load-shedding status (loadshedding.eskom.co.za; the answer minus 1 is the stage). The card shows
the newest hour with a measured (non-forecast) value, MW rounded to whole MW; Eskom publishes
about two days late (newest measured hour 2026-10-18 23:00 on 2026-10-21). "Live grids" marker and
card. Every snapshot.

## Area outlines (`scripts/build_outlines.py`, lake `outlines/*`)

Outlines at every level for the agent's `resolve_area` and `in_area()` (brief 27 B1); no map file.
Overture Maps divisions (`divisions`, release 2026-10-21.0, ODbL with geoBoundaries and Esri parts under
CC BY; 1,082,068 areas, 2.26 GB, every subtype from country to neighbourhood); geoBoundaries ADM2
via Overture (`adm2`, 49,349); US Census cartographic boundaries 2024 1:500,000 (`us_places` 32,612,
`us_cousub` 36,354, `us_tracts` 85,184; public domain); ONS Open Geography ITL 1-3, LAD, MSOA, LSOA,
Scotland's data zones and intermediate zones, NISRA super data zones (`uk_ons`, OGL v3); INSEE/IGN
contours IRIS (`fr_iris`, Licence Ouverte 2.0); CBS wijk- en buurtkaart 2024 (`nl_cbs`: 342
gemeenten, 3,393 wijken, 14,574 buurten; CC BY 4.0); Ireland's small areas 2022 (OSi/CSO, CC BY
4.0), Sweden's DeSO (SCB, CC0) and Belgium's statistical sectors 2024 (Statbel, open licence) in
`small_areas` (44,874); GHSL urban centres UCDB R2024A (`urban_centres`, CC BY 4.0, population as
published); the GEOSTAT 2021 1 km grid (`geostat_grid`, 1,901,599 cells, Eurostat reuse policy). `names` (3,397,857 rows) is the
name index of every set, no geometry. Geometry in WGS 84; display copies are simplified, areas are
computed on the full outline (`ST_Area_Spheroid`). **Left out:** Eurostat GISCO LAU (its terms say
"will not be used for commercial purposes"); a country without a published small-area level shows
its coarser level, named.

## Energy per small area (`scripts/build_small_area_energy.py`, lake `small_area_energy/*`)

One schema for every country (`consumption`, `heating`, `poverty`, `renewables`; columns iso3,
level, code, name, year, carrier or category, value, unit, measure, source). Values are passthrough;
totals are kept as totals and averages as averages, never multiplied out, and a region's total is
never split by area. France: Agence ORE electricity and gas per IRIS and commune (Licence Ouverte
2.0; 3,214,647 IRIS rows, 2,003,509 commune rows) and the electric heating share published with the
IRIS rows. Great Britain: DESNZ subnational consumption per LSOA, MSOA and local authority
(OGL v3; 1,836,212 rows), DESNZ sub-regional fuel poverty (2024 data, 33,756 LSOA, modelled by
DESNZ), ONS Census 2021 TS046 central heating per LSOA via Nomis (35,672 LSOA x 13 categories),
DESNZ renewable electricity by local authority. Netherlands: CBS average electricity and gas per
dwelling and heating shares per buurt (CC BY 4.0). Denmark: Energi Data Service household
electricity per municipality (CC BY 4.0). Portugal: E-REDES consumption per municipality (CC BY
4.0). Sweden: SCB TAB3654 final energy per kommun (CC0). Ireland: CSO MEC03 metered electricity per
county (CC BY 4.0). Spain: ICAEN electricity per Catalan municipality (Catalonia only; CC BY 4.0).
US: DOE LEAD 2022 energy burden and expenditure per tract (computed: sum over cohorts / income or
households; public domain); ACS B25040 heating fuel per tract only with `CENSUS_API_KEY` (the Census
API refuses keyless requests since 2026). Every member state: Eurostat ilc_mdes01 (arrears on
utility bills, country level, CC BY 4.0). Research per country: docs/research/small-area-energy.md.
Refresh: `wave8.yml` group C.

## Rasters for area statistics (`scripts/build_rasters.py`, lake `rasters/*`)

COGs `area_stats` sums or classifies inside any area (cell-centre rule; agent/rasters.yaml). GHSL
GHS-POP and GHS-BUILT-S epoch 2025 (R2023A, CC BY 4.0): 3 arc-second tiles over the EU-27, the UK
and the US (86 tiles, 0.77 GB for built-up) and the 30 arc-second world layer (126 MB). ESA
WorldCover 2021 v200 (CC BY 4.0) and slope from Copernicus DEM GLO-30 (Copernicus licence, free
and open including commercial use) as class shares per 30 arc-second cell (`slope_1km_shares.tif`,
3,490 pieces mosaicked, 650 MB; `worldcover_1km_shares.tif`); the 10 m and 30 m tiles are read in
place for small areas. Hotmaps heat density 100 m (`hotmaps_heat_density_100m.tif`, CC BY 4.0, MWh
per hectare a year). Global Solar Atlas, Global Wind Atlas and JRC flood depth as before.
Probe: backend/probes/probe_area_stats.py (Berlin, 3,629,179.4 people in 130,249 cells, equal to an
independent count). Refresh: `wave8.yml` groups R, S, M.

## Industrial facilities (`scripts/build_assets_w8.py eea`, `w8/industrial.json`, lake `industrial/*`)

EEA Industrial Reporting database v15 (E-PRTR and IED, 2007-2023, CC BY 4.0): releases to air and
water per facility, large combustion plants' fuel input and emissions, IED installations, as
published. The map layer "Industrial facilities" shows each facility's newest reported year of
releases to air (kg, as reported). Coverage: the EU-27 and the other reporting countries.

## Dams (`build_assets_w8.py dams`, `w8/dams.json`, lake `dams/*`)

Global Dam Watch v1.0 (figshare, CC BY 4.0): 41,145 barriers and 35,295 reservoirs worldwide,
columns as published (height, length, capacity, main use, power). Layer "Dams": barriers with a
reservoir or a height, hover card with the published fields.

## CO₂ storage (`build_assets_w8.py co2stop`, `w8/co2storage.json`, lake `co2stop/*`)

CO2StoP (JRC, assessment of about 2013; reuse authorised with acknowledgement): storage units, traps
and the database's own country totals. The database's user list (`user_details`) and test tables are
left out. Layer "CO₂ storage": unit positions from the KML (centroids computed for the map), the
2013 vintage named on the card.

## Excess heat and heat demand (`build_assets_w8.py hotmaps`, `w8/excess_heat.json`, lake `hotmaps/*`)

Hotmaps (CC BY 4.0): the industrial database (sites with excess heat by temperature level, GWh a
year, as published) and the heat density raster (area_stats `heat_demand`). EU-28, 2015 vintage.

## Fires (`build_assets_w8.py fires`, `w8/fires.json`)

NIFC WFIGS current interagency fire perimeters (public domain; perimeters simplified to 0.001° for
the map, acres as published) and NASA FIRMS VIIRS detections of the last 24 hours when
`FIRMS_MAP_KEY` is set (skipped and named in the file otherwise). EFFIS burnt areas are released only
through JRC's data request form (blocked; request text in data/coverage.yaml).

## Ownership, TRI, Pollution Inventory (`build_assets_w8.py ownership|tri|ukpi`, lake only)

GEM Global Energy Ownership Tracker (CC BY 4.0) from the private bucket, one table per sheet. EPA
Toxics Release Inventory, newest year (2024, 77,295 rows, public domain). Environment Agency
Pollution Inventory 2024 (England, 31,384 releases from 2,870 permits; EA conditional licence,
which allows commercial use with the attribution "Contains Environment Agency information ©
Environment Agency and/or database right"); points moved from British National Grid.

## Zoning and land-use plans (`scripts/build_zoning.py`, lake `zoning/*`)

Zones of statutory land-use plans and planning designations, for the agent (no map layer yet).
Table `zones`, one partition per source; every row keeps the source's own zone code and label
(`zone_code`, `zone_label`), its plan (`plan_id`, `plan_name`, `plan_status`, `adopted` as the
source writes it), the document link (`doc_url`) and all source attributes verbatim
(`attributes`, JSON). `class` is a harmonised use class from a lookup of each source's own code
list (`CLASSES` in the script, listed below); codes the lookup does not name stay `other`.
Geometry as the publisher's service returns it in EPSG:4326; invalid rings repaired with
`ST_MakeValid`; rows without geometry kept.

| source | publisher, service | rows (2026-11-08) | class from | licence |
|---|---|---:|---|---|
| `fr_gpu` | Géoportail de l'Urbanisme (IGN), WFS `wfs_du:zone_urba` | 1,345,010 (all fetched; 9,345 invalid geometries repaired with `ST_MakeValid`, 2 kept as published) | CNIG `typezone`: U urban, AU to be urbanised, A agricultural, N natural | Licence Ouverte 2.0 |
| `ie_myplan` | MyPlan, Department of Housing, ArcGIS `GZT_Current_Plan`, `GZT_Expired_Plan` | 124,473 | Generalised Zoning Types (R, C, M, G, N, P, S, O codes) | CC BY 4.0 |
| `dk_plandata` | Plandata.dk, WFS: adopted kommuneplanrammer, lokalplaner, solar and wind lokalplaner | 50,608 frames + 38,080 + 285 + 608 local plans (service counts) | `anvgen` (11 housing ... 91 rural) | Plandata terms |
| `fi_helsinki` | City of Helsinki, Kaavahakemisto plans in force | 4,393 | none (plan outlines) | CC BY 4.0 |
| `us_ca` | California Statewide Zoning (OLUCI), ArcGIS North and South | 568,741 (service counts) | publisher's `ucd_description` | none stated (owner question 9) |
| `gb_england` | planning.data.gov.uk bulk CSV (MHCLG): local plans (the register: adoption date and PDF link, no geometry) and local plan boundaries, green belt, housing allocations, development policy areas, conservation areas, article 4 direction areas, brownfield land, tree preservation zones, AONB, national parks, World Heritage sites and buffer zones, registered parks and gardens, scheduled monuments, listed building outlines, heritage coast | 321,942 (run 43563742943; 4,106 rows without geometry, kept: the plan register and brownfield sites published without a point); 25 plan PDFs sampled into `zoning.documents` (812 pages of text) | the dataset name in `class_code`; housing allocations `residential` (61), every other row `designation` | OGL 3.0 |
| `be_wallonia` | Service public de Wallonie, plan de secteur in force, ArcGIS `AMENAGEMENT_TERRITOIRE/PDS` layer 22 (zones d'affectation) | 43,797 (all read, equal to the service count; run 42531956633) | `AFFECT` codes with the service's own labels (H habitat, A economic activity, D concerted communal development, R agricultural, forest, green and natural, P public services, E water, X extraction; L leisure, V unassigned and ZEC stay `other`) | CC BY 4.0 (metadata record 37502a64-868e-4e3d-bf66-31ff65a24a5a; indicative, no legal value) |
| `es_barcelona` | Mapa Urbanístic de Catalunya (Generalitat, Departament de Territori, January 2023), served for the province of Barcelona (311 municipalities) by the Diputació de Barcelona, ArcGIS `CARTOBASE/MUC` | 227,129: 221,357 qualification + 5,772 classification polygons (all read, equal to the service counts; run 42531956633) | qualification codes and labels from the service's legend (A, D, M, N, R, S); classification by label (urban, to be urbanised; non-developable land stays `other`) | none stated on the service (owner question 9) |
| `lu_pag` | Luxembourg, Ministère des Affaires intérieures, INSPIRE OGC API Features `LU.SpatialPlan.PAG` (communal general development plans) | 456,770 (equal to GDAL's count; run 42573230555; the service declares EPSG:3035 but returns WGS84 latitude, longitude, swapped back) | none (PAG `categorie` codes kept in `class_code`) | CC0 (data.public.lu) |
| `de_berlin` | Senatsverwaltung für Stadtentwicklung Berlin, WFS `bplan`: Bebauungspläne in force (`b_bp_fs`) and in procedure (`a_bp_iv`) | 4,048 plan areas: 2,852 in force + 1,196 in procedure (equal to GDAL's counts; run 42573230555) | none (plan outlines) | dl-de/zero-2-0 |
| `at_ooe` | Land Oberösterreich (DORIS), Flächenwidmungspläne, OGD shapefile `FLWI_WIDMUNGEN_F` | 231,589 (run 42572592823) | none (`KENNZAHL` codes kept) | CC BY 4.0 |
| `at_tirol` | Land Tirol, ArcGIS `FLW_Flaechenwidmung` | 79,566 (equal to the service count; run 42572592823) | none (`OBJEKT` codes kept in `class_code`, `WIDMUNG` as the label) | none stated (owner question 9) |
| `at_wien` | Stadt Wien, WFS `ogdwien:GENFLWIDMUNGOGD` (Flächenwidmungs- und Bebauungsplan) | 26,437 (run 42572592823) | `WIDMUNGSKLASSE`: W residential, GB mixed, GBBG employment, IG industrial, E/S/L green, VB traffic, F community | CC BY 3.0 AT |
| `at_bgld` | Land Burgenland, INSPIRE PLU WFS on hale»connect, `plu:ZoningElement` | 79,705 (equal to GDAL's count, read in pages of 1,000; 17 without geometry, kept; run 42637630388) | HILUCS land-use code | access constraint "otherRestrictions", licence not named (owner question 9) |
| `ee_plan` | Maa- ja Ruumiamet, planning register WFS `planeeringud`: comprehensive-plan land-use zones (`yld_plan_maakas`) and detailed-plan areas (`detail_plan_ala`) | 61,241: 56,862 + 4,379 (equal to GDAL's counts; run 42603609392); the plan links open the register's web pages, no PDFs | none (`tahis` codes kept) | service: no fees, no access constraints |
| `cz_praha` | IPR Praha, Územní plán hl. m. Prahy, functional use areas, ArcGIS `PUP_CUR_PVP_FVU_P` | 15,442 (equal to the service count; run 42603609392) | none (`kodfp1_a` codes kept) | CC BY |
| `lv_riga` | Rīgas valstspilsētas pašvaldība, functional zoning GeoPackage on data.gov.lv | 6,132 (equal to GDAL's count; run 42603609392) | none (zone codes kept) | CC BY 4.0 |
| `es_siu` | Ministerio de Vivienda y Agenda Urbana, Sistema de Información Urbana (all of Spain), ArcGIS `SIU/CLASES_DE_SUELO` layer 0 (land classes) and `SIU/Planeamiento_Vigente` layer 0 (municipal plan in force) | 30,008: 21,791 land-class areas + 8,217 municipal plan outlines (equal to the service counts; pages of 500, halved when the server answers HTML; run 42638499452) | land class of the Ley de Suelo: urbano urban, urbanizable to_urbanise, no urbanizable natural, sistemas generales infrastructure; plan outlines `other` | CC BY 4.0 |
| `eu_wfs` | the INSPIRE Planned Land Use and XPlanung WFS services found on data.europa.eu (`data/zoning_discovery/wfs_services.csv`: 2,196 services, by the catalogue's country: DE 2,188, MT 3, ES 2, AT 1, FI 1, HR 1), each read from its publisher's server through GDAL (`scripts/build_zoning_hub.py --region wfs`); only layers named ZoningElement, SupplementaryRegulation, SpatialPlan, XPlanung BP/FP/RP/SO plans, BaugebietsTeilFlaeche, BebauungsFlaeche or Widmung are read | 271,980 zones (48 shards: run 42713639180, shards 10 and 24 rerun in 42740880850 after a GDAL crash, exit 139); each layer's rows checked against GDAL's count; one row per layer in `zoning.hub_layers` | HILUCS land-use code where the layer carries one; otherwise `other` (code = the specific land-use code or the layer name) | per service, in `hub_layers.licence` |
| `nl_plu` | Netherlands, Kadaster/PDOK, INSPIRE Planned Land Use Atom download `land_use.gml` (11.6 GB GML of the Omgevingswet plans, read in 256 MB parts) | 5,705 (run 42857046954; written in files of 128 rows, as the geometries are large: 5.5 GB of NDJSON for 5,705 zones) | HILUCS codes mapped to the harmonised classes (other 2,630, natural 1,173, water 770, infrastructure 491, community 314, residential 164, agricultural 90, commercial 48, industrial 19, extraction 6) | Public Domain Mark 1.0 (PDOK) |
| `pt_crus` | Portugal (mainland), DGT, national Carta do Regime de Uso do Solo WFS (`SDISNITWFSCRUS`, every municipal PDM in one harmonised layer), read by 20 km bounding-box tiles (WFS 1.1, `maxFeatures=20000`; a tile that returns the cap is split in four), each zone kept once by its ID | 324,894 (run 42938533000; the zoning catalogue went from 38,471,390 to 38,796,284 rows with only this partition added, catalogue run 43373301789; the server reports no hit count, so completeness rests on the tiles covering the mainland) | `Categoria` (habitacional, central, atividades económicas, industrial, verde, equipamentos, agrícola, florestal, natural, recursos geológicos and energéticos, infraestruturas) mapped to the harmonised classes (`PT_CRUS_CLASS`); Classe / Categoria kept in `zone_code` | CC BY 4.0 (DGT) |
| `de_nrw` | Germany, North Rhine-Westphalia: Bauleitpläne NRW (INSPIRE planned land use, the plans 316 municipalities report to the state), opengeodata.nrw.de GeoPackage `bplan_EPSG25832_GeoPackage.zip`, layer PlaeneNachBauGB | 70,960 plan outlines, equal to GDAL's count (run 43559981459); 25 plan PDFs sampled into `zoning.documents` | none: plan outlines; plan type (luplantypenamevalue: Bebauungsplan, Flächennutzungsplan, Satzung) in `zone_code`, plan kind code (luplanartbplan) in `class_code`; status 4000 is "in force" (the state OGC API gives it as legalForce), other status codes kept as "NRW stand <code>" as NRW publishes no list for them | no public-access limitations (INSPIRE metadata); no licence named |
| `de_mv` | Germany, Mecklenburg-Vorpommern: Bauleitpläne in MV WFS (`geodaten-mv.de/dienste/bauleitplan_wfs`, Ministerium für Inneres, Bau und Digitalisierung): development, land-use and special plans and their parts (Bereiche) | 17,975 (B-Pläne 11,098, B-Plan parts 4,630, F-Pläne 1,753, F-Plan parts 302, special plans 159, their parts 33), each equal to GDAL's count (run 43562949367) | none: plan outlines; legal status as the service words it (`rechtsstand_text`) in `plan_status` | dl-de/by-2-0 (service capabilities) |
| `de_bb` | Germany, Brandenburg: legally effective development plans (PLIS, Landesamt für Bauen und Verkehr; WFS `bebauungsplaene_rechtswirksam_wfs` read as GeoJSON) | 7,909 (areas 7,891, lines 16, points 2; run 43562949367) | the plan's main use (`bp_t_haupt`, BauNVO Bauflächen): Wohnbauflächen residential 3,662, Gewerbliche Bauflächen employment 965, Gemischte Bauflächen mixed 656, Gemeinbedarfsflächen community 207, Freiraum open_space 15, other 2,404 (Sonderbauflächen and unstated) | no fees, no access constraints (service capabilities) |
| `local_hub` | ArcGIS Online services titled in each country's own planning words (`scripts/probe_zoning_local.py`: MPZP, plan ogólny, územní plán, asemakaava, yleiskaava, PGT, piano regolatore, ΓΠΣ, χρήσεις γης, PUG, ОУП, bendrasis planas, namenska raba, detaljplan, prostorni plan, LDP proposals, ...), kept only when the term is a whole word of the title, the title has none of the not-zoning words (test, draft, forest, flood, survey, programme, ...) and the item lies in Europe; list in `data/zoning_discovery/local_services.csv` (718 services; German and English plan words added 2026-11-14); read like `us_hub` (`build_zoning_hub.py --region local`) | 1,348,603 zones (run 43564226802, 48 shards; a full run replaces the partition), by the country holding each layer's first zone: SI 464,017, SE 184,973, FI 154,872, IT 153,571, PL 125,434, BG 59,004, DE 55,630, BA 46,349, LT 38,310, CZ 28,638, RO 6,356, GR 5,553, GB 5,000, HR 4,855, CH 1,715, NO 789, SK 410, AT 304, none 12,823; every layer looked at, read or skipped with the reason, in `zoning.hub_layers` | the label's words in English and the local languages (`WORDS` in `build_zoning_hub.py`: mieszkaniow, asuin, abitat, stamben, κατοικ, ...); otherwise `other` | per service, in `hub_layers.licence`; mostly none stated (owner question 9) |
| `us_hub` (and `eu_hub`, `gb_hub`) | the ArcGIS services the Hub sweep found (`data/zoning_discovery/hub_services.csv`), each read from its publisher's server (`scripts/build_zoning_hub.py`) | US: 32,997,727 zones from 6,521 services, plus Alaska and Hawaii 123,720 zones from 89 services (run 42534280337; rows outside the GISCO outlines keep no country) (48 shards: run 42509867449, shards 4, 5, 12, 14, 15 rerun in 42526415788 and 42530251710, 2026-11-08); EU list (`eu_hub`): 415,879 zones from 350 services (run 42533301971), by the country holding each layer's first zone: IE 200,959, US 139,008, ZA 60,923, CA 5,725, GB 801, NL 700, UA 43, CH 10, none 7,710 (the Hub search returned services from outside Europe; each row keeps the country it lies in; Irish layers may repeat MyPlan zones, so sums across sources need the `source` filter); one row per layer looked at in `zoning.hub_layers` (15,092: read, skipped with the reason, or failed with the error) | the label's words (`WORDS` in the script: "residential", "commercial", ...); a label without one, or a layer with only a code field, stays `other` | per service, in `hub_layers.licence`; mostly none stated (owner question 9) |

Hub services: titles that are not maps (feedback forms, surveys, hearings) are dropped; in each
service only polygon layers named for zoning, land use, overlays or plans are read (parcels,
boundaries and roads are not), in full by object id. `zone_code` and `zone_label` are the values
of the fields whose names say so; `class_code` names those fields and the matched word.
`country` is the GISCO outline (the app's `countries.json`, `world.json`) holding the layer's
first zone, NULL when none does (the Hub's "us" tiles also hold Canadian services). A publisher
may serve one layer under several names; every copy is kept, each with its own `plan_id`
(service URL and layer). `hub_layers` lists every layer looked at: read (rows, the fields
used, seconds), skipped (geometry, no zoning field, layer name) or failed (the error).

Plan documents (`scripts/zoning_documents.py`): `documents` (one row per PDF: url, plan, bytes,
SHA-256, pages, private R2 key under `infraatlas-raw/zoning-docs/`) and `document_pages` (page
text as the PDF holds it; pages without a text layer stay empty). Only a sample of 25 PDFs per
source until owner question 8 is answered. Sources found and still to build, the discovery
method and the blocked ones: `docs/research/zoning.md`.

## Notes

- ENTSO-E allows 400 requests a minute; the scripts ask four at a time. A full snapshot
  (~270 requests) took about a minute on 2026-10-05; single answers range from 0.3 s
  to 50 s.
- Energy-Charts answers 429 to bursts. `scripts/fetch_eu_reference.py` still asks it
  one request at a time for installed capacity.

## GB local authority districts (`scripts/wave9.py gb-lad`, `gb_lad.json`)

ONS Local Authority Districts (December 2021) UK BUC, from the ONS ArcGIS service
(`Local_Authority_Districts_December_2021_UK_BUC_2022`), OGL v3: 374 districts with their
codes (`LAD21CD`) and names, coordinates rounded to 4 decimals (0.46 MB). The shapes of the
wave-9 colourings with `scope: gb_lad` (DfT VEH0131, keyed by the April 2021 codes). The
colouring keeps district rows only (E06-E09, W06, S12, N09): county and region totals and the
sheet's footnote rows are left out; 11 published codes of districts merged since April 2021
have no shape and stay in the file.

<!-- wave9:begin (generated by scripts/wave9.py render) -->
## Wave 9 sources (`WAVE=9 scripts/wave9.py`, lake `wave9/<id>`)

Every table is passthrough: the publisher's rows and columns as published (column names in
lower snake case), one table per source; positions are moved to WGS 84 from the source's CRS
(computed), points from published coordinates. On the map: a point source of at most 30,000
records gets a map file (`w9/<id>.json`, all records); every other positioned source is cut into
vector tiles in Actions (tippecanoe, every record, no feature or size limit; larger sets from
zoom 4 or 6) published as `w9/<id>.pmtiles` in the public bucket. Area series become colourings
(`w9c/<id>.json`): one named series per table (the filter is in the file), Eurostat's country
rows, USGS's US counties or GB districts, the newest period published for at least 90 % of the most areas, colour stops at the quartiles
(computed). The full list of the
sources probed, with the ones blocked or left out, is docs/research/wave9-sources.md.

| Source | Category | Places | Level | Licence | Rows | Table |
|---|---|---|---|---|---|---|
| [Fluvius consumption per statistical sector and NACE sector (Flanders)](https://opendata.fluvius.be/api/explore/v2.1/catalog/datasets/1_06b-verbruiksgegevens-statistische-sector-met-nace-sector/exports/csv?delimiter=%2C) | Part A: finishing wave 8 | BE | small_area | check | 540,342 | `wave9.be_fluvius_consumption` |
| [Zensus 2022 heating type per 100 m cell](https://www.destatis.de/static/DE/zensus/gitterdaten/Zensus2022_Heizungsart.zip) | Part A: finishing wave 8 | DE | grid_100m | dl-de/by-2-0 | 2,628,942 | `wave9.de_zensus_heating` |
| [CSO Census 2022 small-area statistics (central heating)](https://www.cso.ie/en/media/csoie/census/census2022/SAPS_2022_Small_Area_UR_171024.csv) | Part A: finishing wave 8 | IE | small_area | CC BY 4.0 | 18,920 | `wave9.ie_cso_saps_heating` |
| [ISTAT census sections 2021](https://www.istat.it/storage/cartografia/basi_territoriali/2021/R01_21.zip) | Part A: finishing wave 8 | IT | small_area | CC BY 4.0 | 756,376 | `wave9.it_istat_sezioni` |
| [INE census sections 2024](https://www.ine.es/prodyser/cartografia/seccionado_2024.zip) | Part A: finishing wave 8 | ES | small_area | CC BY 4.0 | 36,477 | `wave9.es_ine_secciones` |
| [Statistics Finland Paavo postal areas 2024](https://geo.stat.fi/geoserver/postialue/wfs?service=WFS&version=2.0.0&request=GetFeature&typeName=postialue:pno_tilasto_2024&outputFormat=application/json&srsName=EPSG:4326) | Part A: finishing wave 8 | FI | small_area | CC BY 4.0 | 3,026 | `wave9.fi_paavo` |
| [ČSÚ basic settlement units (ZSJ)](https://geodata.csu.gov.cz/as/data/distribuce/Hosted/Open_data_RSO/FeatureServer/20/gpkg.zip) | Part A: finishing wave 8 | CZ | small_area | ČSÚ open data terms (data.gov.cz) | 23,605 | `wave9.cz_zsj` |
| [Statistics Estonia statistical grid](https://inspire.geoportaal.ee/geoserver/SU_ruutkaart/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=SU_ruutkaart:SU.StatisticalGridCell&outputFormat=application/json&srsName=EPSG:4326&propertyName=code,geom) | Part A: finishing wave 8 | EE | small_area | no conditions apply (INSPIRE metadata: "tingimusi ei rakendata"; no access restrictions) | 45,636 | `wave9.ee_grid` |
| [Environment Agency Flood Map for Planning, flood zones 2 and 3](https://environment.data.gov.uk/api/file/download?fileDataSetId=455d2eb3-3065-4d20-871b-c4d5dee23f67&fileName=Flood_Map_for_Planning_Flood_Zones.gpkg.zip) | Part A: finishing wave 8 | GB | polygon | OGL v3 | 415,408 | `wave9.gb_ea_flood_zones` |
| [EIA petroleum refineries](https://www.eia.gov/maps/map_data/Petroleum_Refineries_US_EIA.zip) | Part A: finishing wave 8 | US | point | public domain | 130 | `wave9.us_eia_refineries` |
| [EIA natural gas processing plants](https://www.eia.gov/maps/map_data/NaturalGas_ProcessingPlants_US_EIA.zip) | Part A: finishing wave 8 | US | point | public domain | 478 | `wave9.us_eia_gas_processing` |
| [EIA interstate and intrastate gas pipelines](https://www.eia.gov/maps/map_data/NaturalGas_InterIntrastate_Pipelines_US_EIA.zip) | Part A: finishing wave 8 | US | line | public domain | 32,961 | `wave9.us_eia_gas_pipelines` |
| [EIA crude oil pipelines](https://www.eia.gov/maps/map_data/CrudeOil_Pipelines_US_EIA.zip) | Part A: finishing wave 8 | US | line | public domain | 236 | `wave9.us_eia_crude_pipelines` |
| [EIA LNG import and export terminals](https://www.eia.gov/maps/map_data/Lng_ImportExportTerminals_US_EIA.zip) | Part A: finishing wave 8 | US | point | public domain | 8 | `wave9.us_eia_lng` |
| [EIA petroleum product terminals](https://www.eia.gov/maps/map_data/PetroleumProduct_Terminals_US_EIA.zip) | Part A: finishing wave 8 | US | point | public domain | 1,474 | `wave9.us_eia_product_terminals` |
| [EIA underground gas storage](https://www.eia.gov/maps/map_data/NaturalGas_UndergroundStorage_US_EIA.zip) | Part A: finishing wave 8 | US | point | public domain | 412 | `wave9.us_eia_gas_storage` |
| [EIA hydrocarbon gas liquids pipelines](https://www.eia.gov/maps/map_data/HGL_Pipelines_US_EIA.zip) | Part A: finishing wave 8 | US | line | public domain | 133 | `wave9.us_eia_hgl_pipelines` |
| [EIA petroleum product pipelines](https://www.eia.gov/maps/map_data/PetroleumProduct_Pipelines_US_EIA.zip) | Part A: finishing wave 8 | US | line | public domain | 329 | `wave9.us_eia_product_pipelines` |
| [EIA crude-by-rail terminals](https://www.eia.gov/maps/map_data/CrudeOil_RailTerminals_US_EIA.zip) | Part A: finishing wave 8 | US | point | public domain | 99 | `wave9.us_eia_crude_rail` |
| [EIA biodiesel plants](https://www.eia.gov/maps/map_data/Biodiesel_Plants_US_EIA.zip) | 7. Supply chain, materials and industry | US | point | public domain | 75 | `wave9.us_eia_biodiesel` |
| [EIA ethanol plants](https://www.eia.gov/maps/map_data/Ethanol_Plants_US_EIA.zip) | 7. Supply chain, materials and industry | US | point | public domain | 197 | `wave9.us_eia_ethanol` |
| [NETL NATCARB CO2 storage resources](https://edx.netl.doe.gov/storage/f/edx/2020/06/2020-06-29T16:09:54.953Z/881f1fe1-fdb5-4e9e-8bc4-db151a3baa60/saline10k_1502.zip) | Part A: finishing wave 8 | US | polygon | public domain (US federal government work | 186,675 | `wave9.us_natcarb` |
| [BLM solar energy zones](https://services1.arcgis.com/KbxwQRRfWyEYLgp4/arcgis/rest/services/Energy_Designations/FeatureServer/10) | 1. Land, permitting and planning | US | polygon | public domain (BLM | 153 | `wave9.us_blm_solar_dla` |
| [Natural England provisional Agricultural Land Classification](https://environment.data.gov.uk/api/file/download?fileDataSetId=f33896b6-9847-4f03-b5d9-3c55497a003c&fileName=Provisional_Agricultural_Land_Classification_ALC.gpkg.zip) | 1. Land, permitting and planning | GB | polygon | OGL v3 | 1,826 | `wave9.gb_ne_alc` |
| [Géorisques polluted sites and soils](https://www.georisques.gouv.fr/webappReport/ws/infosols/export/shapefile?national=true) | 1. Land, permitting and planning | FR | polygon | Licence Ouverte 2.0 | 12,431 | `wave9.fr_georisques_ssp` |
| [Brownfield land registers (planning.data.gov.uk)](https://files.planning.data.gov.uk/dataset/brownfield-land.csv) | 1. Land, permitting and planning | GB | point | OGL v3 | 40,229 | `wave9.gb_brownfield_register` |
| [EPA RE-Powering screened sites](https://www.epa.gov/system/files/documents/2023-05/re-powering-screening-dataset-2022%20Updated.xlsx) | 1. Land, permitting and planning | US | point | public domain (EPA geospatial data | 190,976 | `wave9.us_epa_repowering` |
| [EPA Facility Registry Service cleanups](https://geopub.epa.gov/arcgis/rest/services/EMEF/efpoints/MapServer/5) | 1. Land, permitting and planning | US | point | public domain (EPA geospatial data | 45,924 | `wave9.us_epa_frs_cleanups` |
| [Eurostat agricultural land prices and rents (apri_lprc)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/apri_lprc/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 1. Land, permitting and planning | EU | region | CC BY 4.0 | 12,354 | `wave9.eu_land_prices` |
| [OurAirports airports](https://davidmegginson.github.io/ourairports-data/airports.csv) | 1. Land, permitting and planning | World | point | public domain | 86,337 | `wave9.world_ourairports` |
| [Historic England National Heritage List](https://services-eu1.arcgis.com/ZOdPfBS3aqqDYPUQ/arcgis/rest/services/National_Heritage_List_for_England_NHLE_v02_VIEW/FeatureServer/0) | 1. Land, permitting and planning | GB | point | OGL v3 | 379,686 | `wave9.gb_he_listed` |
| [National Register of Historic Places](https://mapservices.nps.gov/arcgis/rest/services/cultural_resources/nrhp_locations/MapServer/0) | 1. Land, permitting and planning | US | point | public domain | 74,636 | `wave9.us_nrhp` |
| [NEXRAD weather radar sites](https://www.ncei.noaa.gov/access/homr/file/nexrad-stations.txt) | 1. Land, permitting and planning | US | point | public domain | 210 | `wave9.us_nexrad` |
| [Planning Inspectorate national infrastructure projects](https://national-infrastructure-consenting.planninginspectorate.gov.uk/api/applications-download) | 1. Land, permitting and planning | GB | point | OGL v3 | 295 | `wave9.gb_pins_dco` |
| [NESO Electricity Ten Year Statement](https://api.neso.energy/dataset/997f4820-1ad4-499b-b1fe-4b8d3d7fbc72/resource/e914fcec-1dc9-4f1f-97e7-59c0d9521bea/download/etys-boundary-gis-data-mar25.zip) | 2. Grid planning, connection and network charges | GB | line | NESO Open Data Licence | 34 | `wave9.gb_neso_etys` |
| [NESO TNUoS tariffs](https://api.neso.energy/api/3/action/package_search?q=tnuos%20tariffs) | 2. Grid planning, connection and network charges | GB | region | NESO Open Data Licence | 572 | `wave9.gb_neso_tnuos` |
| [OpenEI Utility Rate Database](https://openei.org/apps/USURDB/download/usurdb.csv.gz) | 2. Grid planning, connection and network charges | US | point | CC0 | 58,920 | `wave9.us_openei_urdb` |
| [CSO data-centre electricity consumption (MEC02)](https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/MEC02/JSON-stat/2.0/en) | 2. Grid planning, connection and network charges | IE | country | CC BY 4.0 | 132 | `wave9.ie_cso_datacentres` |
| [NESO constraint cost breakdown](https://api.neso.energy/api/3/action/package_search?q=constraint%20breakdown) | 2. Grid planning, connection and network charges | GB | country | NESO Open Data Licence | 210 | `wave9.gb_neso_constraint_costs` |
| [NGED embedded capacity register](https://connecteddata.nationalgrid.co.uk/api/3/action/package_search?q=name:embedded-capacity-register) | 2. Grid planning, connection and network charges | GB | point | check | 7,211 | `wave9.gb_nged_opendata` |
| [SSEN embedded capacity register](https://ckan-prod.sse.datopian.com/api/3/action/package_show?id=embedded_capacity_register) | 2. Grid planning, connection and network charges | GB | point | CC BY 4.0 | 1,317 | `wave9.gb_ssen_opendata` |
| [Northern Powergrid connection queue](https://northernpowergrid.opendatasoft.com/api/explore/v2.1/catalog/datasets/connection-queue-information/exports/csv?delimiter=%2C) | 2. Grid planning, connection and network charges | GB | point | check | 445 | `wave9.gb_npg_opendata` |
| [Svenska kraftnät reserve markets (Mimer)](https://data.svk.se/datastore/dump/6093d167-dece-45c8-8ac7-d307e6ac45e9?format=csv) | 3. Markets and revenues | SE | country | CC BY 4.0 | 439,314 | `wave9.se_svk_reserves` |
| [Energinet FCR-D down reserve auctions (DK2)](https://api.energidataservice.dk/dataset/FcrNdDK2?limit=0&start=2025-01-01) | 3. Markets and revenues | DK | country | CC BY 4.0 | 728,595 | `wave9.dk_energinet_reserves` |
| [regelleistung.net balancing tenders](https://www.regelleistung.net/apps/datacenter/tenders/) | 3. Markets and revenues | DE, AT, BE, NL, FR | country | not stated (no reuse licence on regelleistung.net; imprint checked 2026-10-31); built on the owner's instruction (2026-11-06) to build sources whose licence is not clear | 279,266 | `wave9.de_regelleistung` |
| [ENTSO-E contracted balancing reserves, aFRR (A81, B95), last 30 days](https://web-api.tp.entsoe.eu/api) | 3. Markets and revenues | EU | zone | ENTSO-E terms (reuse with attribution) | 77,480 | `wave9.eu_entsoe_balancing` |
| [Elexon system buy and sell prices (one day per call)](https://data.elexon.co.uk/bmrs/api/v1/balancing/settlement/system-prices/2026-10-01?format=json) | 3. Markets and revenues | GB | country | Elexon BMRS licence (open, attribution) | 48 | `wave9.gb_elexon_balancing` |
| [ISO ancillary-service prices](https://oasis.caiso.com/oasisapi/SingleZip?queryname=PRC_AS&market_run_id=DAM&startdatetime=20261001T07:00-0000&enddatetime=20261101T07:00-0000&version=1&resultformat=6) | 3. Markets and revenues | US | zone | CAISO public materials, use with credit to the California ISO | 19,344 | `wave9.us_iso_as_prices` |
| [EMR Capacity Market register](https://api.neso.energy/api/3/action/package_show?id=capacity-market-register) | 3. Markets and revenues | GB | point | NESO Open Data Licence | 29,864 | `wave9.gb_emr_cm_register` |
| [PJM RPM capacity auction results](https://www.pjm.com/-/media/DotCom/markets-ops/rpm/rpm-auction-info/rpm-auctions-resource-clearing-price-summary.xlsx) | 3. Markets and revenues | US | zone | not stated (the legal page renders no text without JavaScript; the old terms URLs are gone); built on the owner's instruction (2026-11-06) to build sources whose licence is not clear | 2,083 | `wave9.us_pjm_rpm` |
| [ESHM20 European seismic hazard model](https://efehrappsrvr.ethz.ch/share/map?id=81&lon1=-32&lat1=27&lon2=45&lat2=72&imt=PGA&hmapexceedprob=0.002103&hmapexceedyears=1&soiltype=rock_vs30_800ms-1&aggregationtype=arithmetic&aggregationlevel=0.5) | 4. Physical climate and hazard risk | Europe | point | CC BY 4.0 | 100,636 | `wave9.eu_eshm20` |
| [USGS National Seismic Hazard Model 2023](https://www.sciencebase.gov/catalog/item/64ff886dd34ed30c2057b4d9) | 4. Physical climate and hazard risk | US | polygon | public domain (USGS) | 9,794 | `wave9.us_usgs_nshm` |
| [US Drought Monitor (current)](https://droughtmonitor.unl.edu/data/shapefiles_m/USDM_current_M.zip) | 4. Physical climate and hazard risk | US | polygon | public (USDM, credit requested) | 5 | `wave9.us_drought_monitor` |
| [JRC LISCoAsT coastal flood hazard](https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/LISCOAST/10012/LATEST/globalESLprojections.zip) | 4. Physical climate and hazard risk | Europe | point | CC BY 4.0 | 20,865 | `wave9.eu_jrc_coastal_flood` |
| [USGS landslide inventory](https://www.sciencebase.gov/catalog/item/671eef1fd34ed0f827ea9f12) | 4. Physical climate and hazard risk | US | point | CC0 | 680,497 | `wave9.us_usgs_landslides` |
| [NOAA Storm Events (newest year)](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/) | 4. Physical climate and hazard risk | US | point | public domain | 72,360 | `wave9.us_noaa_storm_events` |
| [USGS geoelectric hazard](https://www.sciencebase.gov/catalog/item/68781e6dd4be025a4973e62c) | 4. Physical climate and hazard risk | US | point | CC0 | 1,616 | `wave9.us_usgs_geoelectric` |
| [Agence ORE vehicles per commune and energy](https://opendata.agenceore.fr/data-fair/api/v1/datasets/voitures-par-commune-par-energie/raw) | 5. Demand and electrification | FR | municipality | Licence Ouverte 2.0 | 773,782 | `wave9.fr_ore_ev_commune` |
| [RDW registered vehicles](https://opendata.rdw.nl/resource/8ys7-d773.json?$select=brandstof_omschrijving,count(*)&$group=brandstof_omschrijving&$limit=100) | 5. Demand and electrification | NL | country | CC0 | 9 | `wave9.nl_rdw_vehicles` |
| [KBA vehicles per registration district](https://www.kba.de/SharedDocs/Downloads/DE/Statistik/Fahrzeuge/FZ1/fz1_2026.xlsx?__blob=publicationFile&v=2) | 5. Demand and electrification | DE | county | dl-de/by-2-0 | 448 | `wave9.de_kba_districts` |
| [DfT VEH0142 plug-in vehicles](statistical-data-sets/vehicle-licensing-statistics-data-tables) | 5. Demand and electrification | GB | small_area | OGL v3 | 2,520 | `wave9.gb_dft_veh0142` |
| [AFDC EV registrations per state](https://afdc.energy.gov/files/u/data/data_source/10962/10962-ev-registration-counts-by-state_9-06-24.xlsx) | 5. Demand and electrification | US | region | U.S. DOE publication, no licence stated (counts derived by NREL from Experian data) | 51 | `wave9.us_afdc_registrations` |
| [ODRÉ national register of production installations](https://opendata.agenceore.fr/data-fair/api/v1/datasets/3f6et1q09oarxn7afaj0reop/raw) | 5. Demand and electrification | FR | municipality | Licence Ouverte 2.0 | 141,589 | `wave9.fr_ore_solar_commune` |
| [CBS solar power per region (85005NED)](https://datasets.cbs.nl/odata/v1/CBS/85005NED/Observations) | 5. Demand and electrification | NL | municipality | CC BY 4.0 | 78,944 | `wave9.nl_cbs_solar` |
| [DESNZ solar deployment per local authority](statistics/regional-renewable-statistics) | 5. Demand and electrification | GB | county | OGL v3 | 4,606 | `wave9.gb_desnz_subregional_fit` |
| [ADEME energy performance diagnostics (DPE)](https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/values_agg?field=code_departement_ban;etiquette_dpe&agg_size=120;8&size=0) | 5. Demand and electrification | FR | county | Licence Ouverte 2.0 | 715 | `wave9.fr_ademe_dpe` |
| [SEAI Building Energy Ratings](https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/EBQ03/JSON-stat/2.0/en) | 5. Demand and electrification | IE | county | CC BY 4.0 | 5,698,560 | `wave9.ie_seai_ber` |
| [MHCLG EPC live table D1 (domestic certificates per local authority)](statistical-data-sets/live-tables-on-energy-performance-of-buildings-certificates) | 5. Demand and electrification | GB | county | OGL v3 | 90 | `wave9.gb_epc_stats` |
| [NYC Local Law 84 building energy benchmarking](https://data.cityofnewyork.us/resource/5zyy-y8am.json) | 5. Demand and electrification | US | point | public | 103,259 | `wave9.us_nyc_ll84` |
| [Eurostat heating and cooling degree days per NUTS 3 (nrg_chddr2_a)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_chddr2_a/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 5. Demand and electrification | EU | county | CC BY 4.0 | 39,600 | `wave9.eu_degree_days` |
| [NOAA CPC degree days per state](https://ftp.cpc.ncep.noaa.gov/htdocs/degree_days/weighted/daily_data/2025/StatesCONUS.Heating.txt) | 5. Demand and electrification | US | region | public domain | 48 | `wave9.us_cpc_degree_days` |
| [CSO metered electricity consumption (MEC03)](https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/MEC03/JSON-stat/2.0/en) | 5. Demand and electrification | IE | country | CC BY 4.0 | 1,650 | `wave9.ie_cso_dc_consumption` |
| [EMODnet offshore wind farms](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:windfarmspoly&outputFormat=application/json) | 6. Offshore and maritime | Europe | polygon | CC BY 4.0 | 600 | `wave9.eu_emodnet_wind_farms` |
| [BOEM offshore wind lease outlines](https://boem-metaport-boem.hub.arcgis.com/api/download/v1/items/709831444a234968966667d84bcc0357/geojson?layers=8) | 6. Offshore and maritime | US | polygon | public domain | 52 | `wave9.us_boem_wind_leases` |
| [USGS usSEABED](https://pubs.usgs.gov/ds/2005/118/data/atl_ext.zip) | 6. Offshore and maritime | US | point | public domain (USGS) | 117,031 | `wave9.us_usseabed` |
| [NOAA marine protected areas inventory](https://services2.arcgis.com/C8EMgrsFcRFL6LrL/arcgis/rest/services/NOAA_MPA_Inventory_2023/FeatureServer/0) | 6. Offshore and maritime | US | polygon | public domain (US government work) | 981 | `wave9.us_noaa_mpa` |
| [USGS Mineral Resources Data System](https://mrdata.usgs.gov/mrds/mrds-csv.zip) | 7. Supply chain, materials and industry | World | point | public domain | 304,632 | `wave9.us_usgs_mrds` |
| [EGDI mineral deposits](https://maps.europe-geology.eu/wfs/?service=WFS&version=2.0.0&request=GetFeature&typeNames=ms:egdi_mineraloccurr_critical_raw_materials_2023&outputFormat=geojson&FILTER=%3CFilter%20xmlns%3D%22http%3A//www.opengis.net/fes/2.0%22%3E%3CPropertyIsNotEqualTo%3E%3CValueReference%3Ecountry%3C/ValueReference%3E%3CLiteral%3EPoland%3C/Literal%3E%3C/PropertyIsNotEqualTo%3E%3C/Filter%3E) | 7. Supply chain, materials and industry | Europe | point | CC BY 4.0 (Polish records CC BY-NC-ND 4.0, filtered out) | 28,223 | `wave9.eu_egdi_minerals` |
| [EPA LMOP landfill gas energy projects](https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/LMOP_Projects/FeatureServer/0) | 7. Supply chain, materials and industry | US | point | CC0 (data.gov) | 542 | `wave9.us_epa_lmop` |
| [EPA AgSTAR livestock digesters](https://www.epa.gov/sites/default/files/2020-10/agstar-livestock-ad-database.xlsx) | 7. Supply chain, materials and industry | US | county | public domain | 473 | `wave9.us_epa_agstar` |
| [Salt-cavern hydrogen storage potential (Zenodo)](https://zenodo.org/api/records/18153129/files/h2_salt_cavern_storage.parquet/content) | 7. Supply chain, materials and industry | Europe | polygon | CC BY 4.0 | 119 | `wave9.eu_salt_caverns` |
| [USAspending DOE awards](https://files.usaspending.gov/award_data_archive/FY2025_089_Assistance_Full_20261006.zip) | 8. Finance, public money and incentives | US | point | public domain (U.S. federal spending data) | 11,923 | `wave9.us_usaspending_doe` |
| [NETL IRA energy community layers](https://arcgis.netl.doe.gov/server/rest/services/Hosted/2024_MSAs_NonMSAs_that_are_Energy_Communities/FeatureServer/0) | 8. Finance, public money and incentives | US | county | CC BY (NETL) | 901 | `wave9.us_ira_energy_communities` |
| [HUD Opportunity Zones (census tracts)](https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/Opportunity_Zones/FeatureServer/13) | 8. Finance, public money and incentives | US | small_area | public domain | 8,765 | `wave9.us_opportunity_zones` |
| [Eurostat household income per NUTS 2 (nama_10r_2hhinc)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nama_10r_2hhinc/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 9. Social and community | EU | region | CC BY 4.0 | 111,460 | `wave9.eu_household_income` |
| [ONS income estimates per MSOA](https://www.ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/smallareaincomeestimatesformiddlelayersuperoutputareasenglandandwales/financialyearending2023/datasetfinal.xlsx) | 9. Social and community | GB | small_area | OGL v3 | 7,264 | `wave9.gb_ons_income_msoa` |
| [NREL Sharing the Sun community solar projects](https://data.nlr.gov/system/files/244/1793053331-Sharing%20the%20Sun%20Community%20Solar%20Project%20Data%20%28Sep%202026%29.xlsx) | 9. Social and community | US | point | NLR data licence (free use and copying with the notice and credit to DOE/NLR/Alliance) | 4,810 | `wave9.us_nrel_sharing_sun` |
| [Commission broadband coverage study](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/isoc_cbs/?format=SDMX-CSV&compressed=false) | 10. Telecom and digital | EU | country | CC BY 4.0 | 1,404 | `wave9.eu_broadband_coverage` |
| [EEA water exploitation index](https://sdi.eea.europa.eu/datashare/s/sptXqwkQr5g7Bp5/download?path=/eea_v_3035_250_k_wei-subunit-level_p_2023_v01_r00&files=WEI_2000_2023_SDI_SubunitScale.xlsx) | 11. Water and cooling | Europe | region | CC BY 4.0 | 21,006 | `wave9.eu_eea_wei` |
| [USGS estimated water use per county (2015)](https://www.sciencebase.gov/catalog/item/5af3311be4b0da30c1b245d8) | 11. Water and cooling | US | county | public domain | 3,223 | `wave9.us_usgs_water_use` |
| [USGS NWIS stream gauges](https://api.waterdata.usgs.gov/ogcapi/v1/collections/monitoring-locations/items?f=csv&limit=50000&site_type_code=ST&agency_code=USGS&state_code=01) | 11. Water and cooling | US | point | public domain | 147,741 | `wave9.us_usgs_nwis_sites` |
| [IHFC Global Heat Flow Database 2024](https://datapub.gfz.de/download/10.5880.FIDGEO.2024.014-VEueRf/GHFBD-R2024_v.2026-03.zip) | 12. Heat networks and geothermal | World | point | CC BY 4.0 | 91,182 | `wave9.world_ihfc_heat_flow` |
| [Danish Energy Agency district heating areas](https://geoserver.plandata.dk/geoserver/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=pdk:theme_pdk_forsyningomraade_vedtaget_v&outputFormat=application/json&srsName=EPSG:4326) | 12. Heat networks and geothermal | DK | polygon | CC BY 4.0 | 6,263 | `wave9.dk_district_heating` |
| [TEN-T network (TENtec)](https://webgate.ec.europa.eu/getis/rest/services/TENTec/tentec_public_services_ext/MapServer/8) | 13. Mobility | Europe | line | CC BY 4.0 (European Commission) | 4,767 | `wave9.eu_tent_network` |
| [National Highways Strategic Road Network](https://services-eu1.arcgis.com/mZXeBXkkZpekxjXT/arcgis/rest/services/Network_Model_Public_view2/FeatureServer/1) | 13. Mobility | GB | line | OGL v3 | 43,040 | `wave9.gb_srn` |
| [FHWA Alternative Fuel Corridors](https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/AltFuels_rounds1_8/FeatureServer/0) | 13. Mobility | US | line | public domain (U.S. DOT) | 2,275 | `wave9.us_fhwa_afc` |
| [EEA air quality statistics per station](https://discomap.eea.europa.eu/App/AQViewer/download?fqn=Airquality_Dissem.b2g.AirQualityStatistics&f=csv) | 15. Air quality near plants | Europe | point | EEA reuse (commercial use allowed, with acknowledgement) | 16,343 | `wave9.eu_eea_aq_stats` |
| [DEFRA AURN monitoring sites](https://uk-air.defra.gov.uk/sos-ukair/api/v1/stations?expanded=false) | 15. Air quality near plants | GB | point | OGL v3 | 2,448 | `wave9.gb_defra_aurn` |
| [EPA AQS annual concentrations per monitor (2025)](https://aqs.epa.gov/aqsweb/airdata/annual_conc_by_monitor_2025.zip) | 15. Air quality near plants | US | point | public domain | 65,709 | `wave9.us_epa_aqs_annual` |
| [Enedis interruption time per department](https://opendata.enedis.fr/data-fair/api/v1/datasets/w06kbpkd-qkqnu6zq5lpxer3/lines?size=1000&format=csv) | 16. Reliability below the country | FR | county | Licence Ouverte 2.0 | 94 | `wave9.fr_enedis_interruptions` |
| [EIA-861 reliability per utility](https://www.eia.gov/electricity/data/eia861/zip/f8612025.zip) | 16. Reliability below the country | US | point | public domain | 977 | `wave9.us_eia861_reliability` |
| [Eurostat vehicles by fuel per NUTS 2 (tran_r_elvehst)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/tran_r_elvehst/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 5. Demand and electrification | EU | region | CC BY 4.0 | 15,106 | `wave9.eu_ev_stock_nuts2` |
| [Eurostat new passenger cars by fuel (road_eqs_carpda)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_carpda/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 5. Demand and electrification | EU | country | CC BY 4.0 | 5,969 | `wave9.eu_new_cars_fuel` |
| [Eurostat heat pump characteristics (nrg_inf_hptc)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_inf_hptc/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 5. Demand and electrification | EU | country | CC BY 4.0 | 24,857 | `wave9.eu_heat_pumps` |
| [Eurostat household broadband access per NUTS 2 (isoc_r_broad_h)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/isoc_r_broad_h/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 10. Telecom and digital | EU | region | CC BY 4.0 | 4,566 | `wave9.eu_broadband_nuts2` |
| [Eurostat electrified railway lines (rail_if_electri)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_if_electri/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 13. Mobility | EU | country | CC BY 4.0 | 2,651 | `wave9.eu_rail_electrified` |
| [Eurostat water abstraction (env_wat_abs)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_wat_abs/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 11. Water and cooling | EU | country | CC BY 4.0 | 16,316 | `wave9.eu_water_abstraction` |
| [Eurostat water use (env_wat_use)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_wat_use/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 11. Water and cooling | EU | country | CC BY 4.0 | 6,853 | `wave9.eu_water_use` |
| [Eurostat population connected to wastewater treatment (env_ww_con)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ww_con/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 11. Water and cooling | EU | country | CC BY 4.0 | 5,883 | `wave9.eu_wastewater_connected` |
| [Eurostat nuclear capacity and reactors (nrg_inf_nuc)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_inf_nuc/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 14. Nuclear | EU | country | CC BY 4.0 | 3,363 | `wave9.eu_nuclear_capacity` |
| [Eurostat air passengers per NUTS 2 (tran_r_avpa_nm)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/tran_r_avpa_nm/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 13. Mobility | EU | region | CC BY 4.0 | 10,203 | `wave9.eu_air_passengers` |
| [Eurostat population unable to keep home adequately warm (sdg_07_60)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_07_60/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 9. Social and community | EU | country | CC BY 4.0 | 1,260 | `wave9.eu_energy_productivity` |
| [OurAirports runways](https://davidmegginson.github.io/ourairports-data/runways.csv) | 13. Mobility | World | point | public domain | 48,405 | `wave9.world_ourairports_runways` |
| [OurAirports navigation aids](https://davidmegginson.github.io/ourairports-data/navaids.csv) | 1. Land, permitting and planning | World | point | public domain | 11,008 | `wave9.world_ourairports_navaids` |
| [EPA LMOP landfills](https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/New_Landfills/FeatureServer/0) | 7. Supply chain, materials and industry | US | point | CC0 (data.gov) | 2,323 | `wave9.us_epa_lmop_landfills` |
| [BOEM active renewable energy leases](https://boem-metaport-boem.hub.arcgis.com/api/download/v1/items/e5a371353b4744418e57da448dac9471/geojson?layers=0) | 6. Offshore and maritime | US | polygon | public domain | 4,892 | `wave9.us_boem_active_leases` |
| [MHCLG table DEC1 (display energy certificates per local authority)](statistical-data-sets/live-tables-on-energy-performance-of-buildings-certificates) | 5. Demand and electrification | GB | county | OGL v3 | 90 | `wave9.gb_dec_certificates` |
| [DfT plug-in cars per local authority (VEH0131)](statistical-data-sets/vehicle-licensing-statistics-data-tables) | 5. Demand and electrification | GB | county | OGL v3 | 484 | `wave9.gb_ulev_la` |
| [SMU node heat flow data (Geothermal Data Repository)](https://gdr.openei.org/files/1704/Download%20Data%20Files.zip) | 12. Heat networks and geothermal | US | point | CC BY 4.0 | 106,468 | `wave9.us_smu_heat_flow` |
| [EMODnet offshore installations](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:platforms&outputFormat=application/json) | 6. Offshore and maritime | Europe | point | CC BY 4.0 (EMODnet Human Activities) | 1,617 | `wave9.eu_emodnet_platforms` |
| [EMODnet offshore pipelines](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:pipelines&outputFormat=application/json) | Part A: finishing wave 8 | Europe | line | CC BY 4.0 (EMODnet Human Activities) | 3,951 | `wave9.eu_emodnet_pipelines` |
| [EMODnet wave and tidal energy projects](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:oenergy&outputFormat=application/json) | 6. Offshore and maritime | Europe | point | CC BY 4.0 (EMODnet Human Activities) | 361 | `wave9.eu_emodnet_ocean_energy` |
| [EMODnet maritime spatial plan zones](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=1.0.0&request=GetFeature&typeName=emodnet:mspzoningpoly&outputFormat=SHAPE-ZIP&format_options=CHARSET:UTF-8) | 6. Offshore and maritime | Europe | polygon | CC BY 4.0 (EMODnet Human Activities) | 4,257 | `wave9.eu_emodnet_msp_zoning` |
| [EMODnet ports](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:portlocations&outputFormat=application/json) | 6. Offshore and maritime | Europe | point | CC BY 4.0 (EMODnet Human Activities) | 946 | `wave9.eu_emodnet_ports` |
| [EMODnet goods handled per port](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:portgoods&outputFormat=application/json) | 6. Offshore and maritime | Europe | point | CC BY 4.0 (EMODnet Human Activities) | 429,668 | `wave9.eu_emodnet_port_goods` |
| [EMODnet urban wastewater treatment plants (UWWTD)](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:treatmentplants&outputFormat=application/json) | 11. Water and cooling | Europe | point | CC BY 4.0 (EMODnet Human Activities) | 57,243 | `wave9.eu_emodnet_wwtp` |
| [EMODnet nuclear power plants](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:nuclear&outputFormat=application/json) | 14. Nuclear | Europe | point | CC BY 4.0 (EMODnet Human Activities) | 121 | `wave9.eu_emodnet_nuclear` |
| [EMODnet desalination plants](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:desalination&outputFormat=application/json) | 11. Water and cooling | Europe | point | CC BY 4.0 (EMODnet Human Activities) | 3,911 | `wave9.eu_emodnet_desalination` |
| [EMODnet hydrocarbon licences](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:hydrocarbons&outputFormat=application/json) | Part A: finishing wave 8 | Europe | polygon | CC BY 4.0 (EMODnet Human Activities) | 28,506 | `wave9.eu_emodnet_hydrocarbon_licences` |
| [EMODnet marine protected areas](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:marineprotectedareas&outputFormat=application/json) | 6. Offshore and maritime | Europe | polygon | CC BY 4.0 (EMODnet Human Activities) | 826 | `wave9.eu_emodnet_mpa` |
| [EMODnet military areas at sea](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:militaryareaspoly&outputFormat=application/json) | 6. Offshore and maritime | Europe | polygon | CC BY 4.0 (EMODnet Human Activities) | 746 | `wave9.eu_emodnet_military` |
| [EMODnet marine aggregate areas](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:aggregateareas&outputFormat=application/json) | 6. Offshore and maritime | Europe | polygon | CC BY 4.0 (EMODnet Human Activities) | 1,202 | `wave9.eu_emodnet_aggregates` |
| [EMODnet seabed substrate 1:1M](https://drive.emodnet-geology.eu/geoserver/wfs?service=WFS&version=1.0.0&request=GetFeature&typeName=gtk:seabed_substrate_1m&outputFormat=SHAPE-ZIP&srsName=EPSG:4326&format_options=CHARSET:UTF-8) | 6. Offshore and maritime | Europe | polygon | Commission reuse (EMODnet Geology, CC BY 4.0) | 67,254 | `wave9.eu_emodnet_substrate` |
| [Cohesion policy projects 2014-2020 (Kohesio export)](https://cohesiondata.ec.europa.eu/api/views/557j-pmg8/rows.csv?accessType=DOWNLOAD) | 8. Finance, public money and incentives | EU | point | CC0 (cohesiondata.ec.europa.eu) | 1,967,976 | `wave9.eu_kohesio_2014_2020` |
| [Northern Powergrid heat map: substation headroom](https://northernpowergrid.opendatasoft.com/api/explore/v2.1/catalog/datasets/heatmapdatatable/exports/csv?delimiter=%2C) | 2. Grid planning, connection and network charges | GB | point | check | 670 | `wave9.gb_npg_heatmap_substations` |
| [DESNZ Heat Networks Planning Database (Q2 2026)](https://assets.publishing.service.gov.uk/media/6a6cbd2e0c36759b5ccaa304/HNPD_2026_Q2.xlsx) | 12. Heat networks and geothermal | GB | point | OGL v3 | 1,505 | `wave9.gb_hnpd` |
| [Eurostat electricity and derived heat production by fuel (nrg_bal_peh)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_bal_peh/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 12. Heat networks and geothermal | EU | country | CC BY 4.0 | 894,510 | `wave9.eu_heat_production` |
| [Eurostat non-household electricity price components incl. network costs (nrg_pc_205_c)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_pc_205_c/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 2. Grid planning, connection and network charges | EU | country | CC BY 4.0 | 81,164 | `wave9.eu_network_costs` |
| [Eurostat non-household electricity prices (nrg_pc_206)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_pc_206/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 3. Markets and revenues | EU | country | CC BY 4.0 | 2,307 | `wave9.eu_nonhousehold_prices` |
| [Eurostat renewable electricity capacity by technology (nrg_inf_epcrw)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_inf_epcrw/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 5. Demand and electrification | EU | country | CC BY 4.0 | 18,961 | `wave9.eu_renewable_capacity` |
| [Eurostat household internet access (isoc_ci_in_h)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/isoc_ci_in_h/?format=SDMX-CSV&compressed=false&startPeriod=2015) | 10. Telecom and digital | EU | country | CC BY 4.0 | 5,585 | `wave9.eu_internet_households` |
| [EIA-861 2024 reliability per utility (SAIDI, SAIFI)](https://www.eia.gov/electricity/data/eia861/zip/f8612024.zip) | 16. Reliability below the country | US | point | public domain | 972 | `wave9.us_eia861_reliability_xlsx` |
| [NRC operating reactors list](https://www.nrc.gov/reading-rm/doc-collections/datasets/reactors-operating.xls) | 14. Nuclear | US | point | CC0 (data.gov) | 93 | `wave9.us_nrc_operating_reactors` |
| [CBS electricity delivered to data centres 2017-2024 (Netherlands)](https://www.cbs.nl/-/media/_excel/2025/51/datacenters_elektriciteitsleveringen_2017_2024.xlsx) | 5. Demand and electrification | NL | country | CC BY 4.0 | 16 | `wave9.nl_cbs_datacentres` |
| [Clean Hydrogen Observatory electrolyser manufacturing capacity](https://observatory.clean-hydrogen.europa.eu/sites/default/files/2026-07/Electrolyser%20manufacturing%20capacity%20May2026.xlsx) | 7. Supply chain, materials and industry | Europe | total | ©Clean Hydrogen JU, reproduction is authorised, provided the source is acknowledged | 11 | `wave9.eu_cleanh2_electrolyser_mfg` |
| [EMODnet telecommunication cables - DE BSH-CONTIS](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:bshcontiscables&outputFormat=application/json) | 10. Telecom and digital | DE | line | EMODnet Human Activities: re-use for any purpose including commercial, free of charge, sources acknowledged | 28 | `wave9.de_emodnet_telecom_bsh` |
| [EMODnet telecommunication cables - ES CICA](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:cicacables&outputFormat=application/json) | 10. Telecom and digital | ES | line | EMODnet Human Activities: re-use for any purpose including commercial, free of charge, sources acknowledged | 29 | `wave9.es_emodnet_telecom_cica` |
| [EMODnet telecommunication cables - FR SHOM](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:shomcables&outputFormat=application/json) | 10. Telecom and digital | FR | line | EMODnet Human Activities: re-use for any purpose including commercial, free of charge, sources acknowledged | 603 | `wave9.fr_emodnet_telecom_shom` |
| [EMODnet telecommunication cables - FR SIGCables](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:sigcables&outputFormat=application/json) | 10. Telecom and digital | FR | line | EMODnet Human Activities: re-use for any purpose including commercial, free of charge, sources acknowledged | 60 | `wave9.fr_emodnet_telecom_sigcables` |
| [EMODnet telecommunication cables - MT IOI-MOC](https://ows.emodnet-humanactivities.eu/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=emodnet:maltacables&outputFormat=application/json) | 10. Telecom and digital | MT | line | EMODnet Human Activities: re-use for any purpose including commercial, free of charge, sources acknowledged | 6 | `wave9.mt_emodnet_telecom` |
| [OpenStreetMap communication lines (Overture base/infrastructure)](s3://overturemaps-us-west-2/release/2026-09-23.1/theme=base/type=infrastructure/*) | 10. Telecom and digital | Europe | line | ODbL (OpenStreetMap contributors, via Overture) | 6,991 | `wave9.eur_overture_comm_lines` |
| [BfEE Plattform für Abwärme (reported excess heat per site](https://elan1.bafa.bund.de/zvi-ui/pfa/abwaermepotentiale) | 7. Supply chain, materials and industry | DE | point | CC BY 4.0 | 24,355 | `wave9.de_bfee_abwaerme` |
| [Energinet countertrade procured in intraday (DK1)](https://api.energidataservice.dk/dataset/CountertradeIntraday_v2?limit=0&start=2025-10-15) | 2. Grid planning, connection and network charges | DK | country | CC BY 4.0 | 26,976 | `wave9.dk_energinet_countertrade` |
| [EirGrid renewable dispatch-down (constraints and curtailment) summary](https://www.eirgrid.ie/sites/default/files/publications/DD-Summary-Report-V23.xlsx) | 2. Grid planning, connection and network charges | IE | country | EirGrid Group Open Data Licence (commercial use allowed, credit 'Supported by EirGrid Group Data') | 16,905 | `wave9.ie_eirgrid_dispatch_down` |
| [SEMO balancing and imbalance market cost view (half-hourly)](https://reports.sem-o.com/api/v1/documents/static-reports?DPuG_ID=BM-095&page_size=100&sort_by=Date&order_by=DESC) | 3. Markets and revenues | IE | zone | EirGrid Group Open Data Licence (covers SEMO; commercial use allowed with credit) | 651 | `wave9.ie_semo_imbalance` |
| [Elia balancing energy prices and reserve capacity bids](https://opendata.elia.be/api/explore/v2.1/catalog/datasets/ods166/exports/csv) | 3. Markets and revenues | BE | country | Elia Open Data Licence (named in every dataset's metas; the licence page did not answer, 2026-11-05 and 2026-11-06, so its terms are not quoted); built on the owner's instruction (2026-11-06) | 1,004,448 | `wave9.be_elia_balancing` |
| [RTE balancing mechanism activated volumes per year (ODRÉ)](https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/volumes-actives-ma/exports/csv) | 3. Markets and revenues | FR | country | Licence Ouverte 2.0 | 12 | `wave9.fr_odre_balancing_volumes` |
| [IPTO (ADMIE) balancing market settlement files](https://www.admie.gr/getOperationMarketFilewRange?dateStart=2026-10-01&dateEnd=2026-10-01) | 3. Markets and revenues | GR | country | not stated (IPTO's Terms and Services cover liability and accuracy only); built on the owner's instruction (2026-11-06) to build sources whose licence is not clear | 202,936 | `wave9.gr_admie_balancing` |
| [PSE balancing prices and reserve capacity prices (raporty.pse.pl API)](https://api.raporty.pse.pl/api/cmbp-tp?$filter=business_date%20ge%20'2024-06-14') | 3. Markets and revenues | PL | country | not stated (neither raporty.pse.pl nor the API states reuse terms); built on the owner's instruction (2026-11-06) to build sources whose licence is not stated | 105,053 | `wave9.pl_pse_balancing` |
| [ČEPS data (web service CepsData.asmx)](https://www.ceps.cz/_layouts/CepsData.asmx) | 3. Markets and revenues | CZ | country | not stated (no reuse terms found on ceps.cz); built on the owner's instruction (2026-11-06) to build sources whose licence is not clear | 194,355 | `wave9.cz_ceps_balancing` |
| [EIA-861M estimated small-scale solar PV capacity and generation per state](https://www.eia.gov/electricity/data/eia861m/xls/small_scale_solar_2026.xlsx) | 5. Demand and electrification | US | region | public domain | 411 | `wave9.us_eia861m_small_solar` |
| [SURS electricity consumption (kWh) per municipality and consumer type, yearly (1817609S)](https://pxweb.stat.si/SiStatData/api/v1/sl/Data/1817609S.px) | Part A: finishing wave 8 | SI | municipality | CC BY 4.0 | 3,852 | `wave9.si_surs_electricity_municipality` |
| [SURS dwellings by heating method per settlement (0871205S) and per municipality (0861120S)](https://pxweb.stat.si/SiStatData/api/v1/sl/Data/0871205S.px) | Part A: finishing wave 8 | SI | small_area | CC BY 4.0 | 192,648 | `wave9.si_surs_heating_settlement` |
| [Statistics Finland buildings by heating fuel per municipality (StatFin raku 15er)](https://pxdata.stat.fi/PxWeb/api/v1/fi/StatFin/raku/15er.px) | Part A: finishing wave 8 | FI | municipality | CC BY 4.0 | 1,067,904 | `wave9.fi_statfin_heating_fuel_municipality` |
| [ČSÚ Census 2021 occupied dwellings by main energy source for heating](https://csu.gov.cz/docs/107508/cf59a324-f403-7444-58c3-7b26bdbf01ec/sldb2021_byty_energie.csv?version=1.0) | Part A: finishing wave 8 | CZ | municipality | CC BY 4.0 | 87,413 | `wave9.cz_csu_sldb_heating_energy` |
| [ČSÚ Census 2021 occupied dwellings by heating method](https://csu.gov.cz/docs/107508/d0e84fb3-8e98-0d05-0254-db4465ff8f65/sldb2021_byty_vytapeni.csv?version=1.0) | Part A: finishing wave 8 | CZ | municipality | CC BY 4.0 | 47,069 | `wave9.cz_csu_sldb_heating_mode` |
| [INE Portugal Census 2021 dwellings by heating type used most often](https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd=0011526&lang=PT) | Part A: finishing wave 8 | PT | small_area | CC BY 4.0 | 24,052 | `wave9.pt_ine_heating_freguesia` |
| [Statistics Estonia census 2011 dwellings by main heating method per municipality (RL0223)](https://andmed.stat.ee/api/v1/et/stat/rahvaloendus/rel2011/eluruumid/RL0223.PX) | Part A: finishing wave 8 | EE | municipality | CC BY-SA 4.0 | 18,256 | `wave9.ee_stat_heating_2011` |
| [CSP census dwellings with and without central heating per municipality and Riga neighbourhood (MAS080)](https://data.stat.gov.lv/api/v1/lv/OSP_PUB/POP/MA/MAS/MAS080) | Part A: finishing wave 8 | LV | small_area | CC0 1.0 | 329,160 | `wave9.lv_csp_central_heating` |
| [DESNZ Boiler Upgrade Scheme redemptions per local authority (heat pumps)](statistics/boiler-upgrade-scheme-statistics-september-2026) | 5. Demand and electrification | GB | county | OGL v3 | 371 | `wave9.gb_bus_heat_pumps_la` |
| [EIA RECS 2020 main space-heating equipment per state (central heat pump share)](https://www.eia.gov/consumption/residential/data/2020/state/xls/State%20Space%20Heating.xlsx) | 5. Demand and electrification | US | region | public domain | 1 | `wave9.us_eia_recs_heat_pumps_state` |
| [Transelectrica available capacity per grid zone and allocation year (capacity auctions)](https://www.transelectrica.ro/web/tel/procesul-de-alocare-a-capacitatii-retelei-electrice) | 2. Grid planning, connection and network charges | RO | zone | not stated (site footer "Copyright © Transelectrica 2013 - 2026"); a public notice required by ANRE Order 53/2024 art. 6 (1)-(2); built on the owner's instruction (2026-11-06) to build sources whose licence is not clear | 100 | `wave9.ro_transelectrica_zone_capacity` |
| [EMS list of all connection requests (generation and storage) on the transmission system](https://ems.rs/wp-content/uploads/2026/11/20261104-proizvodjaci-Spisak-prikljucenja2.pdf) | 2. Grid planning, connection and network charges | RS | plant | not stated (ems.rs has no terms or copyright page); a list published under the Law on the Use of Renewable Energy Sources (Službeni glasnik RS 40/2021, 35/2023, 94/2024); built on the owner's instruction (2026-11-06) | 88 | `wave9.rs_ems_connection_queue` |
| [ŠÚ SR consumption of fuels, electricity and heat per district (okres), yearly (DATAcube en3001rr)](https://statdata.statistics.sk/public/api/dc/opendata/cube/dataset/en3001rr/download?lang=SK&type=CSV) | Part A: finishing wave 8 | SK | district | CC BY 4.0 | 13,800 | `wave9.sk_susr_energy_consumption_okres` |
| [ELSTAT Census 2021 households by main energy source for heating, cooking and hot water, per regional unit (SAM05 table Α13)](https://www.statistics.gr/el/statistics?p_p_id=documents_WAR_publicationsportlet_INSTANCE_VBZOni0vs5VJ&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view&p_p_cacheability=cacheLevelPage&p_p_col_id=column-2&p_p_col_count=4&p_p_col_pos=2&_documents_WAR_publicationsportlet_INSTANCE_VBZOni0vs5VJ_javax.faces.resource=document&_documents_WAR_publicationsportlet_INSTANCE_VBZOni0vs5VJ_ln=downloadResources&_documents_WAR_publicationsportlet_INSTANCE_VBZOni0vs5VJ_documentID=532490&_documents_WAR_publicationsportlet_INSTANCE_VBZOni0vs5VJ_locale=el) | Part A: finishing wave 8 | GR | county | ELSTAT reuse policy (free reuse, commercial included, with source) | 3,906 | `wave9.gr_elstat_heating_energy_regional_unit` |
| [ELSTAT Census 2021 conventional dwellings by occupancy and heating availability and type, per settlement (SAM05 table Γ09)](https://www.statistics.gr/el/statistics?p_p_id=documents_WAR_publicationsportlet_INSTANCE_VBZOni0vs5VJ&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view&p_p_cacheability=cacheLevelPage&p_p_col_id=column-2&p_p_col_count=4&p_p_col_pos=2&_documents_WAR_publicationsportlet_INSTANCE_VBZOni0vs5VJ_javax.faces.resource=document&_documents_WAR_publicationsportlet_INSTANCE_VBZOni0vs5VJ_ln=downloadResources&_documents_WAR_publicationsportlet_INSTANCE_VBZOni0vs5VJ_documentID=532485&_documents_WAR_publicationsportlet_INSTANCE_VBZOni0vs5VJ_locale=el) | Part A: finishing wave 8 | GR | small_area | ELSTAT reuse policy (free reuse, commercial included, with source) | 444,864 | `wave9.gr_elstat_heating_settlement` |
<!-- wave9:end -->

<!-- wave10:begin (generated by scripts/wave9.py render) -->
## Wave 10 sources (`WAVE=10 scripts/wave9.py`, lake `wave10/<id>`)

Every table is passthrough: the publisher's rows and columns as published (column names in
lower snake case), one table per source; positions are moved to WGS 84 from the source's CRS
(computed), points from published coordinates. On the map: a point source of at most 30,000
records gets a map file (`w10/<id>.json`, all records); every other positioned source is cut into
vector tiles in Actions (tippecanoe, every record, no feature or size limit; larger sets from
zoom 4 or 6) published as `w10/<id>.pmtiles` in the public bucket. Area series become colourings
(`w10c/<id>.json`): one named series per table (the filter is in the file), Eurostat's country
rows, USGS's US counties or GB districts, the newest period published for at least 90 % of the most areas, colour stops at the quartiles
(computed). The full list of the
sources probed, with the ones blocked or left out, is docs/research/wave9-sources.md.

| Source | Category | Places | Level | Licence | Rows | Table |
|---|---|---|---|---|---|---|
| [DESNZ sub-national electricity consumption per local authority](statistics/regional-and-local-authority-electricity-consumption-statistics) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 7,770 | `wave10.gb_desnz_elec_la` |
| [DESNZ sub-national gas consumption per local authority](statistics/regional-and-local-authority-gas-consumption-statistics) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 7,754 | `wave10.gb_desnz_gas_la` |
| [DESNZ domestic gas consumption distribution per local authority](statistics/regional-and-local-authority-gas-consumption-statistics) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 35 | `wave10.gb_desnz_gas_distribution` |
| [DESNZ domestic electricity consumption distribution per local authority](statistics/regional-and-local-authority-electricity-consumption-statistics) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 25 | `wave10.gb_desnz_elec_distribution` |
| [DESNZ sub-national total final energy consumption per local authority](statistics/total-final-energy-consumption-at-regional-and-local-authority-level-2005-to-2023) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 7,315 | `wave10.gb_desnz_tfec_la` |
| [DESNZ renewable electricity installed capacity per local authority](statistics/regional-renewable-statistics) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 4,606 | `wave10.gb_desnz_ren_capacity_la` |
| [DESNZ renewable electricity generation per local authority](statistics/regional-renewable-statistics) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 4,582 | `wave10.gb_desnz_ren_generation_la` |
| [DESNZ renewable electricity installations per local authority](statistics/regional-renewable-statistics) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 4,606 | `wave10.gb_desnz_ren_sites_la` |
| [DESNZ local authority territorial greenhouse gas emissions (table 1.1)](statistics/uk-local-authority-and-regional-greenhouse-gas-emissions-statistics-2005-to-2023) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 7,657 | `wave10.gb_desnz_ghg_la` |
| [DESNZ local authority CO2 emissions within the scope of local authorities (table 2.1)](statistics/uk-local-authority-and-regional-greenhouse-gas-emissions-statistics-2005-to-2023) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 7,657 | `wave10.gb_desnz_co2_la` |
| [DESNZ local authority greenhouse gas emissions dataset (long format)](statistics/uk-local-authority-and-regional-greenhouse-gas-emissions-statistics-2005-to-2023) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 559,215 | `wave10.gb_desnz_ghg_dataset` |
| [DfT public EV charging devices per local authority (EVCD 1a)](statistics/electric-vehicle-public-charging-infrastructure-statistics-october-2025) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 433 | `wave10.gb_dft_evcd_devices` |
| [DfT public EV charging devices per 100](statistics/electric-vehicle-public-charging-infrastructure-statistics-october-2025) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 433 | `wave10.gb_dft_evcd_per_100k` |
| [DfT public rapid EV charging devices per local authority (EVCD 1b)](statistics/electric-vehicle-public-charging-infrastructure-statistics-october-2025) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 433 | `wave10.gb_dft_evcd_rapid` |
| [ONS Census 2021 TS046 central heating per local authority (Nomis)](https://www.nomisweb.co.uk/api/v01/dataset/NM_2064_1.data.csv?geography=TYPE424&select=date_name,geography_code,geography_name,c2021_heating_13_name,measures_name,obs_value) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 8,268 | `wave10.gb_census_heating` |
| [ONS Census 2021 TS044 accommodation type per local authority (Nomis)](https://www.nomisweb.co.uk/api/v01/dataset/NM_2062_1.data.csv?geography=TYPE424&select=date_name,geography_code,geography_name,c2021_acctype_9_name,measures_name,obs_value) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 5,724 | `wave10.gb_census_accommodation` |
| [ONS Census 2021 TS045 car or van availability per local authority (Nomis)](https://www.nomisweb.co.uk/api/v01/dataset/NM_2063_1.data.csv?geography=TYPE424&select=date_name,geography_code,geography_name,c2021_cars_5_name,measures_name,obs_value) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 3,180 | `wave10.gb_census_cars` |
| [ONS Census 2021 TS054 tenure per local authority (Nomis)](https://www.nomisweb.co.uk/api/v01/dataset/NM_2072_1.data.csv?geography=TYPE424&select=date_name,geography_code,geography_name,c2021_tenure_9_name,measures_name,obs_value) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 9,540 | `wave10.gb_census_tenure` |
| [ONS Census 2021 TS050 number of bedrooms per local authority (Nomis)](https://www.nomisweb.co.uk/api/v01/dataset/NM_2068_1.data.csv?geography=TYPE424&select=date_name,geography_code,geography_name,c2021_bedrooms_5_name,measures_name,obs_value) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 3,180 | `wave10.gb_census_bedrooms` |
| [ONS Census 2021 TS061 method used to travel to work per local authority (Nomis)](https://www.nomisweb.co.uk/api/v01/dataset/NM_2078_1.data.csv?geography=TYPE424&select=date_name,geography_code,geography_name,c2021_ttwmeth_12_name,measures_name,obs_value) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 7,632 | `wave10.gb_census_travel_method` |
| [ONS Census 2021 TS058 distance travelled to work per local authority (Nomis)](https://www.nomisweb.co.uk/api/v01/dataset/NM_2075_1.data.csv?geography=TYPE424&select=date_name,geography_code,geography_name,c2021_ttwdist_11_name,measures_name,obs_value) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 6,996 | `wave10.gb_census_travel_distance` |
| [ONS Census 2021 TS006 population density per local authority (Nomis)](https://www.nomisweb.co.uk/api/v01/dataset/NM_2026_1.data.csv?geography=TYPE154&select=date_name,geography_code,geography_name,measures_name,obs_value) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 331 | `wave10.gb_census_density` |
| [ONS Census 2021 TS041 number of households per local authority (Nomis)](https://www.nomisweb.co.uk/api/v01/dataset/NM_2059_1.data.csv?geography=TYPE424&select=date_name,geography_code,geography_name,measures_name,obs_value) | 8. GB local authority energy and emissions | GB | county | OGL v3 | 1 | `wave10.gb_census_households` |
| [Eurostat Persons employed in circular economy sectors (cei_cie011)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_cie011/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 808 | `wave10.eu_cei_cie011` |
| [Eurostat Private investment and gross added value related to circular economy sectors (cei_cie012)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_cie012/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 1,616 | `wave10.eu_cei_cie012` |
| [Eurostat Consumption footprint (cei_gsr010)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_gsr010/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 21,420 | `wave10.eu_cei_gsr010` |
| [Eurostat Greenhouse gases emissions from production activities (cei_gsr011)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_gsr011/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 492 | `wave10.eu_cei_gsr011` |
| [Eurostat EU self-sufficiency for raw materials (cei_gsr020)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_gsr020/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 315 | `wave10.eu_cei_gsr020` |
| [Eurostat Material import dependency (cei_gsr030)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_gsr030/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 564 | `wave10.eu_cei_gsr030` |
| [Eurostat Material footprint (cei_pc020)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_pc020/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 492 | `wave10.eu_cei_pc020` |
| [Eurostat Resource productivity (cei_pc030)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_pc030/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 1,622 | `wave10.eu_cei_pc030` |
| [Eurostat Generation of municipal waste per capita (cei_pc031)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_pc031/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 550 | `wave10.eu_cei_pc031` |
| [Eurostat Generation of waste excluding major mineral wastes per GDP unit (cei_pc032)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_pc032/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 285 | `wave10.eu_cei_pc032` |
| [Eurostat Waste generation per capita (cei_pc034)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_pc034/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 298 | `wave10.eu_cei_pc034` |
| [Eurostat Food waste (cei_pc035)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_pc035/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 145 | `wave10.eu_cei_pc035` |
| [Eurostat Generation of packaging waste per capita (cei_pc040)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_pc040/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 451 | `wave10.eu_cei_pc040` |
| [Eurostat Generation of plastic packaging waste per capita (cei_pc050)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_pc050/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 451 | `wave10.eu_cei_pc050` |
| [Eurostat Contribution of recycled materials to raw materials demand - end-of-life recycling input rates (EOL-RIR) (cei_srm010)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_srm010/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 116 | `wave10.eu_cei_srm010` |
| [Eurostat Trade in recyclable raw materials (cei_srm020)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_srm020/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 36,368 | `wave10.eu_cei_srm020` |
| [Eurostat Circular material use rate (cei_srm030)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_srm030/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 420 | `wave10.eu_cei_srm030` |
| [Eurostat Recyclable secondary raw materials - prices (cei_srm040)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_srm040/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 3,168 | `wave10.eu_cei_srm040` |
| [Eurostat Recycling rate of all waste excluding major mineral waste (cei_wm010)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_wm010/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 154 | `wave10.eu_cei_wm010` |
| [Eurostat Recycling rate of municipal waste (cei_wm011)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_wm011/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 510 | `wave10.eu_cei_wm011` |
| [Eurostat Recycling rate of packaging waste by type of packaging (cei_wm020)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_wm020/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 2,706 | `wave10.eu_cei_wm020` |
| [Eurostat Recycling rate of waste of electrical and electronic equipment (WEEE) separately collected (cei_wm060)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/cei_wm060/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 451 | `wave10.eu_cei_wm060` |
| [Eurostat Air emissions intensities by NACE Rev. 2 activity (env_ac_aeint_r2)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_aeint_r2/?format=TSV&compressed=true) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 5,354,167 | `wave10.eu_env_ac_aeint_r2` |
| [Eurostat Air emissions accounts totals bridging to emission inventory totals (env_ac_aibrid_r2)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_aibrid_r2/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 595,116 | `wave10.eu_env_ac_aibrid_r2` |
| [Eurostat Air emissions accounts related to road transport - totals bridging to emission inventory totals (env_ac_aibrid_rd)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_aibrid_rd/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 86,264 | `wave10.eu_env_ac_aibrid_rd` |
| [Eurostat Air emissions accounts for greenhouse gases by NACE Rev. 2 activity - quarterly data (env_ac_aigg_q)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_aigg_q/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 16,502 | `wave10.eu_env_ac_aigg_q` |
| [Eurostat Air emissions accounts by NACE Rev. 2 activity (env_ac_ainah_r2)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_ainah_r2/?format=TSV&compressed=true) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 6,272,440 | `wave10.eu_env_ac_ainah_r2` |
| [Eurostat Air emissions accounts related to road transport by NACE Rev. 2 activity (env_ac_ainah_rd)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_ainah_rd/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 713,160 | `wave10.eu_env_ac_ainah_rd` |
| [Eurostat Investments in climate change mitigation by NACE Rev. 2 activity (env_ac_ccminv)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_ccminv/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 13,846 | `wave10.eu_env_ac_ccminv` |
| [Eurostat Intermediate consumption of environmental protection services by institutional sector and NACE Rev. 2 activity (env_ac_cepsgc1)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_cepsgc1/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 61,622 | `wave10.eu_env_ac_cepsgc1` |
| [Eurostat Final consumption expenditure on environmental protection services by institutional sector (env_ac_cepsgh1)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_cepsgh1/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 10,424 | `wave10.eu_env_ac_cepsgh1` |
| [Eurostat Methane emission footprints (CH4 in CO2 equivalent, FIGARO application) (env_ac_ch4fp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_ch4fp/?format=TSV&compressed=true) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 19,233,000 | `wave10.eu_env_ac_ch4fp` |
| [Eurostat Carbon dioxide emission footprints (FIGARO application) (env_ac_co2fp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_co2fp/?format=TSV&compressed=true) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 19,233,000 | `wave10.eu_env_ac_co2fp` |
| [Eurostat Circular material use rate (env_ac_cur)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_cur/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 420 | `wave10.eu_env_ac_cur` |
| [Eurostat Circular material use rate by material type (env_ac_curm)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_curm/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 75 | `wave10.eu_env_ac_curm` |
| [Eurostat Employment in the environmental goods and services sector (2000-2023) (env_ac_egss1)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_egss1/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 877,833 | `wave10.eu_env_ac_egss1` |
| [Eurostat Production, value added and exports in the environmental goods and services sector (2000-2023) (env_ac_egss2)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_egss2/?format=TSV&compressed=true) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 5,789,110 | `wave10.eu_env_ac_egss2` |
| [Eurostat Production, value added and employment by industry groups in the environmental goods and services sector (2000-2023) (env_ac_egss3)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_egss3/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 299 | `wave10.eu_env_ac_egss3` |
| [Eurostat Environmental protection investments of corporations as ancillary producers by environmental protection activity and NACE Rev. 2 activity (env_ac_epiap1)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_epiap1/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 133,870 | `wave10.eu_env_ac_epiap1` |
| [Eurostat Environmental protection investments of general government by environmental protection activity (env_ac_epigg1)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_epigg1/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 6,398 | `wave10.eu_env_ac_epigg1` |
| [Eurostat Environmental protection investments of corporations as specialist and secondary producers by environmental protection activity (env_ac_epissp1)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_epissp1/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 5,980 | `wave10.eu_env_ac_epissp1` |
| [Eurostat Environmental protection investments of total economy (env_ac_epite1)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_epite1/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 558 | `wave10.eu_env_ac_epite1` |
| [Eurostat National expenditure on environmental protection by institutional sector (env_ac_epneis1)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_epneis1/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 2,922 | `wave10.eu_env_ac_epneis1` |
| [Eurostat Environmental protection transfers by environmental protection activity and institutional sector (env_ac_eptrf1)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_eptrf1/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 36,432 | `wave10.eu_env_ac_eptrf1` |
| [Eurostat Greenhouse gas emission footprints (in CO2 equivalent, FIGARO application) (env_ac_ghgfp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_ghgfp/?format=TSV&compressed=true) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 19,233,000 | `wave10.eu_env_ac_ghgfp` |
| [Eurostat Hydrofluorocarbon emission footprints (HFC in CO2 equivalent, FIGARO application) (env_ac_hfcfp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_hfcfp/?format=TSV&compressed=true) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 19,233,000 | `wave10.eu_env_ac_hfcfp` |
| [Eurostat Air emission footprints (domestic technology assumption) (env_ac_io10)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_io10/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 1,181,880 | `wave10.eu_env_ac_io10` |
| [Eurostat Land use footprints (env_ac_landfp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_landfp/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 165 | `wave10.eu_env_ac_landfp` |
| [Eurostat Material flow accounts (env_ac_mfa)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_mfa/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 509,201 | `wave10.eu_env_ac_mfa` |
| [Eurostat Material flow accounts - balancing items (env_ac_mfabi)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_mfabi/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 13,389 | `wave10.eu_env_ac_mfabi` |
| [Eurostat Material flow accounts - domestic processed output (env_ac_mfadpo)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_mfadpo/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 35,446 | `wave10.eu_env_ac_mfadpo` |
| [Eurostat Material flow accounts - main indicators (env_ac_mfain)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_mfain/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 13,790 | `wave10.eu_env_ac_mfain` |
| [Eurostat Material import dependency (env_ac_mid)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_mid/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 2,820 | `wave10.eu_env_ac_mid` |
| [Eurostat Nitrous oxide emission footprints (N2O in CO2 equivalent, FIGARO application) (env_ac_n2ofp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_n2ofp/?format=TSV&compressed=true) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 19,233,000 | `wave10.eu_env_ac_n2ofp` |
| [Eurostat Nitrogen trifluoride and sulphur hexafluoride emission footprints (NF3-SF6 in CO2 equivalent, FIGARO application) (env_ac_nf3sf6fp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_nf3sf6fp/?format=TSV&compressed=true) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 19,233,000 | `wave10.eu_env_ac_nf3sf6fp` |
| [Eurostat Key indicators of physical energy flow accounts by NACE Rev. 2 activity (env_ac_pefa04)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_pefa04/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 301,792 | `wave10.eu_env_ac_pefa04` |
| [Eurostat Physical energy flow accounts totals bridging to energy balances totals (env_ac_pefa05)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_pefa05/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 4,564 | `wave10.eu_env_ac_pefa05` |
| [Eurostat Energy footprints (domestic technology assumption) (env_ac_pefafp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_pefafp/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 80,400 | `wave10.eu_env_ac_pefafp` |
| [Eurostat Energy supply and use by NACE Rev. 2 activity (env_ac_pefasu)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_pefasu/?format=TSV&compressed=true) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 8,152,111 | `wave10.eu_env_ac_pefasu` |
| [Eurostat Production of environmental protection services of general government by economic characteristics (env_ac_pepsgg1)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_pepsgg1/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 39,490 | `wave10.eu_env_ac_pepsgg1` |
| [Eurostat Production of environmental protection services of corporations as ancillary producers by economic characteristics and NACE Rev. 2 activity (env_ac_pepsns1)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_pepsns1/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 257,882 | `wave10.eu_env_ac_pepsns1` |
| [Eurostat Production of environmental protection services of corporations as specialist and secondary producers by economic characteristics (env_ac_pepssp1)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_pepssp1/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 32,268 | `wave10.eu_env_ac_pepssp1` |
| [Eurostat Perfluorocarbon emission footprints (PFC in CO2 equivalent, FIGARO application) (env_ac_pfcfp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_pfcfp/?format=TSV&compressed=true) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 19,233,000 | `wave10.eu_env_ac_pfcfp` |
| [Eurostat Material footprints - main indicators (env_ac_rme)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_rme/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 24,606 | `wave10.eu_env_ac_rme` |
| [Eurostat Material footprints - details by final use of products (env_ac_rmefd)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_rmefd/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 946,196 | `wave10.eu_env_ac_rmefd` |
| [Eurostat Resource productivity (env_ac_rp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_rp/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 2,186 | `wave10.eu_env_ac_rp` |
| [Eurostat Material flows for circular economy - Sankey diagram data (env_ac_sd)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_sd/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 50,940 | `wave10.eu_env_ac_sd` |
| [Eurostat Environmental tax revenues (env_ac_tax)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_tax/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 2. Energy prices, taxes and markets | EU | country | CC BY 4.0 (Eurostat) | 9,456 | `wave10.eu_env_ac_tax` |
| [Eurostat Energy taxes by paying sector (env_ac_taxener)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_taxener/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 2. Energy prices, taxes and markets | EU | country | CC BY 4.0 (Eurostat) | 3,535 | `wave10.eu_env_ac_taxener` |
| [Eurostat Environmental taxes by economic activity (NACE Rev. 2) (env_ac_taxind2)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_ac_taxind2/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 2. Energy prices, taxes and markets | EU | country | CC BY 4.0 (Eurostat) | 431,730 | `wave10.eu_env_ac_taxind2` |
| [Eurostat Air pollutants by source sector (env_air_emis)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_air_emis/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 412,002 | `wave10.eu_env_air_emis` |
| [Eurostat Air pollutants by source sector aggregated for indicator sets (env_air_emis_ind)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_air_emis_ind/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 7,860 | `wave10.eu_env_air_emis_ind` |
| [Eurostat Nitrogen dioxide concentrations in European capital cities - monthly averages, experimental statistics (env_air_no2)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_air_no2/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 3,240 | `wave10.eu_env_air_no2` |
| [Eurostat Final consumption expenditure on environmental protection services by institutional sector and environmental purpose (env_epea_cfin)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_epea_cfin/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 7,418 | `wave10.eu_env_epea_cfin` |
| [Eurostat Intermediate consumption of environmental protection services by institutional sector, NACE Rev. 2 activity and environmental purpose (env_epea_cint)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_epea_cint/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 51,592 | `wave10.eu_env_epea_cint` |
| [Eurostat Environmental protection investments of corporations as ancillary producers by NACE Rev. 2 activity and environmental purpose (env_epea_invap)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_epea_invap/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 94,022 | `wave10.eu_env_epea_invap` |
| [Eurostat Environmental protection investments of general government and NPISH by environmental purpose (env_epea_invgg)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_epea_invgg/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 3,624 | `wave10.eu_env_epea_invgg` |
| [Eurostat Environmental protection investments of corporations as specialist and secondary producers by environmental purpose (env_epea_invsp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_epea_invsp/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 3,828 | `wave10.eu_env_epea_invsp` |
| [Eurostat Environmental protection investments of total economy (env_epea_invte)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_epea_invte/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 477 | `wave10.eu_env_epea_invte` |
| [Eurostat National expenditure on environmental protection by institutional sector and environmental purpose (env_epea_neep)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_epea_neep/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 21,171 | `wave10.eu_env_epea_neep` |
| [Eurostat Production of environmental protection services by corporations as ancillary producers, by economic characteristics, NACE Rev. 2 activity and environmental purpose (env_epea_pap)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_epea_pap/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 195,092 | `wave10.eu_env_epea_pap` |
| [Eurostat Production of environmental protection services by general government and NPISH, by economic characteristics and environmental purpose (env_epea_pgg)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_epea_pgg/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 26,444 | `wave10.eu_env_epea_pgg` |
| [Eurostat Production of environmental protection services by corporations as specialist and secondary producers, by economic characteristics and environmental purpose (env_epea_psp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_epea_psp/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 22,488 | `wave10.eu_env_epea_psp` |
| [Eurostat Environmental protection transfers by institutional sector and environmental purpose (env_epea_trf)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_epea_trf/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 20,044 | `wave10.eu_env_epea_trf` |
| [Eurostat Environmental subsidies and similar transfers from general government, by environmental activity, sector of recipient and ESA category of transfer (env_esst_cepgg)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_esst_cepgg/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 142,792 | `wave10.eu_env_esst_cepgg` |
| [Eurostat Environmental subsidies and similar transfers from general government to corporations, by environmental activity, ESA category of transfer and NACE Rev. 2 activity of recipient (env_esst_cepggcp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_esst_cepggcp/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 202,358 | `wave10.eu_env_esst_cepggcp` |
| [Eurostat Environmental subsidies and similar transfers from the rest of the world to the domestic economy, by environmental activity and ESA category of transfer (env_esst_ceprw)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_esst_ceprw/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 22,270 | `wave10.eu_env_esst_ceprw` |
| [Eurostat Environmental subsidies and similar transfers from general government, by environmental activity, sector of recipient and ESA category of transfer (2011-2022) (env_esst_gg)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_esst_gg/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 206,037 | `wave10.eu_env_esst_gg` |
| [Eurostat Environmental subsidies and similar transfers from general government to corporations, by environmental activity, ESA category of transfer and NACE Rev. 2 activity of recipient (2011-2022) (env_esst_ggcp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_esst_ggcp/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 209,400 | `wave10.eu_env_esst_ggcp` |
| [Eurostat Environmental subsidies and similar transfers from the Rest of the World to the domestic economy, by environmental activity and ESA category of transfer (2011-2022) (env_esst_rw)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_esst_rw/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 3. Emissions and environmental accounts | EU | country | CC BY 4.0 (Eurostat) | 33,570 | `wave10.eu_env_esst_rw` |
| [Eurostat Water use balance (env_wat_bal)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_wat_bal/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 4,791 | `wave10.eu_env_wat_bal` |
| [Eurostat Water use by supply category and economical sector (env_wat_cat)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_wat_cat/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 6,051 | `wave10.eu_env_wat_cat` |
| [Eurostat Water use in the manufacturing industry by activity and supply category (env_wat_ind)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_wat_ind/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 4,701 | `wave10.eu_env_wat_ind` |
| [Eurostat Population connected to public water supply (env_wat_pop)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_wat_pop/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 372 | `wave10.eu_env_wat_pop` |
| [Eurostat Renewable freshwater resources (env_wat_res)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_wat_res/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 7,192 | `wave10.eu_env_wat_res` |
| [Eurostat Water abstraction by river basin district (RBD) (env_watabs_rb)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_watabs_rb/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 23,732 | `wave10.eu_env_watabs_rb` |
| [Eurostat Freshwater resources by river basin district (RBD) (env_watres_rb)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_watres_rb/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 17,705 | `wave10.eu_env_watres_rb` |
| [Eurostat Water use by river basin district (RBD) (env_watuse_rb)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/env_watuse_rb/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 5. Water, materials and circular economy | EU | country | CC BY 4.0 (Eurostat) | 7,030 | `wave10.eu_env_watuse_rb` |
| [Eurostat Self-propelled vessels, tugs and pushers and their power by year of construction (iww_eq_age)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/iww_eq_age/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,236 | `wave10.eu_iww_eq_age` |
| [Eurostat Load capacity of self-propelled vessels by year of construction (iww_eq_age_loa)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/iww_eq_age_loa/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 559 | `wave10.eu_iww_eq_age_loa` |
| [Eurostat Self-propelled vessels, dumb and pushed vessels by load capacity (iww_eq_loadcap)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/iww_eq_loadcap/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,626 | `wave10.eu_iww_eq_loadcap` |
| [Eurostat Power of self-propelled vessels by load capacity (iww_eq_power_lo)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/iww_eq_power_lo/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 482 | `wave10.eu_iww_eq_power_lo` |
| [Eurostat Calorific values for energy balances (nrg_bal_cv)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_bal_cv/?format=TSV&compressed=true) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 166,309 | `wave10.eu_nrg_bal_cv` |
| [Eurostat Simplified energy balances (nrg_bal_s)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_bal_s/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 1,966,518 | `wave10.eu_nrg_bal_s` |
| [Eurostat Biomass supply (nrg_cb_bm)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_bm/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 12,332 | `wave10.eu_nrg_cb_bm` |
| [Eurostat Crude oil supply - monthly data (nrg_cb_cosm)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_cosm/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 30,549 | `wave10.eu_nrg_cb_cosm` |
| [Eurostat Electricity supply, transformation and consumption - annual data (nrg_cb_e)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_e/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 36,635 | `wave10.eu_nrg_cb_e` |
| [Eurostat Electricity available to internal market - monthly data (nrg_cb_eim)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_eim/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 17,165 | `wave10.eu_nrg_cb_eim` |
| [Eurostat Electricity supply, transformation and consumption - monthly data (nrg_cb_em)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_em/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 41,927 | `wave10.eu_nrg_cb_em` |
| [Eurostat Gas supply, transformation and consumption - annual data (nrg_cb_gas)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_gas/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 296,960 | `wave10.eu_nrg_cb_gas` |
| [Eurostat Gas supply, transformation and consumption - monthly data (nrg_cb_gasm)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_gasm/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 125,203 | `wave10.eu_nrg_cb_gasm` |
| [Eurostat Derived heat supply, transformation and consumption (nrg_cb_h)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_h/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 31,148 | `wave10.eu_nrg_cb_h` |
| [Eurostat Hydrogen, ammonia and e-fuels supply, transformation and consumption (nrg_cb_h2)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_h2/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 11,208 | `wave10.eu_nrg_cb_h2` |
| [Eurostat Oil and petroleum products supply, transformation and consumption - annual data (nrg_cb_oil)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_oil/?format=TSV&compressed=true) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 8,907,863 | `wave10.eu_nrg_cb_oil` |
| [Eurostat Oil and petroleum products supply, transformation and consumption - monthly data (nrg_cb_oilm)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_oilm/?format=TSV&compressed=true) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 2,904,030 | `wave10.eu_nrg_cb_oilm` |
| [Eurostat Net electricity generation by type of fuel - monthly data (nrg_cb_pem)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_pem/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 206,979 | `wave10.eu_nrg_cb_pem` |
| [Eurostat Renewables and wastes supply, transformation and consumption (nrg_cb_rw)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_rw/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 674,532 | `wave10.eu_nrg_cb_rw` |
| [Eurostat Solid fossil fuels supply, transformation and consumption - annual data (nrg_cb_sff)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_sff/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 696,518 | `wave10.eu_nrg_cb_sff` |
| [Eurostat Solid fossil fuels supply, transformation and consumption - monthly data (nrg_cb_sffm)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_cb_sffm/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 299,713 | `wave10.eu_nrg_cb_sffm` |
| [Eurostat Cooling and heating degree days by country - annual data (nrg_chdd_a)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_chdd_a/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 992 | `wave10.eu_nrg_chdd_a` |
| [Eurostat Cooling and heating degree days by country - monthly data (nrg_chdd_m)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_chdd_m/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 11,904 | `wave10.eu_nrg_chdd_m` |
| [Eurostat Cooling and heating degree days by NUTS 3 region - monthly data (nrg_chddr2_m)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_chddr2_m/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 691,200 | `wave10.eu_nrg_chddr2_m` |
| [Eurostat Combined heat and power capacity, production, fuel use and primary energy savings (nrg_chp_cpfe)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_chp_cpfe/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 73,831 | `wave10.eu_nrg_chp_cpfe` |
| [Eurostat Combined heat and power fuel use (nrg_chp_f)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_chp_f/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 5,350 | `wave10.eu_nrg_chp_f` |
| [Eurostat Combined heat and power units (nrg_chp_n)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_chp_n/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 5,201 | `wave10.eu_nrg_chp_n` |
| [Eurostat Final energy consumption by sector - calorific values (nrg_d_cv)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_d_cv/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 6,144 | `wave10.eu_nrg_d_cv` |
| [Eurostat Households energy consumption - quantities (nrg_d_hhq)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_d_hhq/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 67,178 | `wave10.eu_nrg_d_hhq` |
| [Eurostat Industry energy consumption by NACE Rev. 2 activity - quantities (nrg_d_indq_n)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_d_indq_n/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 1,001,830 | `wave10.eu_nrg_d_indq_n` |
| [Eurostat Services energy consumption by NACE Rev. 2 activity - quantities (nrg_d_serq_n)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_d_serq_n/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 133,670 | `wave10.eu_nrg_d_serq_n` |
| [Eurostat Transport energy consumption by mode of transport - quantities (nrg_d_traq)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_d_traq/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 102,962 | `wave10.eu_nrg_d_traq` |
| [Eurostat District heating and cooling networks' customers (nrg_dhdc_c)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_dhdc_c/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 841 | `wave10.eu_nrg_dhdc_c` |
| [Eurostat District heating and cooling networks' capacity, productions and losses (nrg_dhdc_cpl)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_dhdc_cpl/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 6,572 | `wave10.eu_nrg_dhdc_cpl` |
| [Eurostat District heating and cooling networks' energy supply (nrg_dhdc_e)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_dhdc_e/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 3,367 | `wave10.eu_nrg_dhdc_e` |
| [Eurostat District heating and cooling networks and their length (nrg_dhdc_n)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_dhdc_n/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 1,759 | `wave10.eu_nrg_dhdc_n` |
| [Eurostat Heat pumps' ambient heat captured by technology and climate (nrg_ind_ahbtc)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_ahbtc/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 44,688 | `wave10.eu_nrg_ind_ahbtc` |
| [Eurostat Overall renewable energy share - detailed components (nrg_ind_cotd)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_cotd/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 10,172 | `wave10.eu_nrg_ind_cotd` |
| [Eurostat Diversity index of energy supply (nrg_ind_di)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_di/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 405 | `wave10.eu_nrg_ind_di` |
| [Eurostat Diversity index of final energy consumption by sector (nrg_ind_difec)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_difec/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 10,657 | `wave10.eu_nrg_ind_difec` |
| [Eurostat Biomethane exports through the grid (nrg_ind_ebmg)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_ebmg/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 25,080 | `wave10.eu_nrg_ind_ebmg` |
| [Eurostat Primary and final energy consumption (nrg_ind_eff)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_eff/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 10,842 | `wave10.eu_nrg_ind_eff` |
| [Eurostat Energy intensity (nrg_ind_ei)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_ei/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 2,195 | `wave10.eu_nrg_ind_ei` |
| [Eurostat Energy productivity (nrg_ind_ep)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_ep/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 1,105 | `wave10.eu_nrg_ind_ep` |
| [Eurostat Electricity production and self-consumption (nrg_ind_epsc)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_epsc/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 20,760 | `wave10.eu_nrg_ind_epsc` |
| [Eurostat Available energy, energy supply and final energy consumption per capita (nrg_ind_esc)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_esc/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 32,692 | `wave10.eu_nrg_ind_esc` |
| [Eurostat Energy self-reliance (nrg_ind_esr)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_esr/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 405 | `wave10.eu_nrg_ind_esr` |
| [Eurostat Share of fuels in final energy consumption (nrg_ind_fecf)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_fecf/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 20,298 | `wave10.eu_nrg_ind_fecf` |
| [Eurostat Households energy consumption - quantities per square meter (nrg_ind_fechm2)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_fechm2/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 87 | `wave10.eu_nrg_ind_fechm2` |
| [Eurostat Share of fossil fuels in gross available energy (nrg_ind_ffgae)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_ffgae/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 597 | `wave10.eu_nrg_ind_ffgae` |
| [Eurostat Heat pumps - ambient heat (nrg_ind_hpind)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_hpind/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 2,920 | `wave10.eu_nrg_ind_hpind` |
| [Eurostat Heat pumps' technical characteristics by technology and climate (nrg_ind_hptctc)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_hptctc/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 127,568 | `wave10.eu_nrg_ind_hptctc` |
| [Eurostat Biomethane imports through the grid (nrg_ind_ibmg)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_ibmg/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 25,080 | `wave10.eu_nrg_ind_ibmg` |
| [Eurostat Energy imports dependency (nrg_ind_id)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_id/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 7,761 | `wave10.eu_nrg_ind_id` |
| [Eurostat Import dependency on third countries by fuel type (nrg_ind_id3cf)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_id3cf/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 3,304 | `wave10.eu_nrg_ind_id3cf` |
| [Eurostat Oil and petroleum products import dependency by country of origin (nrg_ind_idooil)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_idooil/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 4,466 | `wave10.eu_nrg_ind_idooil` |
| [Eurostat Energy import origin concentration index by fuel (nrg_ind_ioc)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_ioc/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 6,497 | `wave10.eu_nrg_ind_ioc` |
| [Eurostat Electricity and derived heat gross and net production (nrg_ind_peh)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_peh/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 266,012 | `wave10.eu_nrg_ind_peh` |
| [Eurostat Electricity and heat production (nrg_ind_pehap)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_pehap/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 155,618 | `wave10.eu_nrg_ind_pehap` |
| [Eurostat Electricity and derived heat gross production from combustible fuels (nrg_ind_pehcf)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_pehcf/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 928,323 | `wave10.eu_nrg_ind_pehcf` |
| [Eurostat Electricity and derived heat gross production from non-combustible fuels (nrg_ind_pehnf)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_pehnf/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 156,820 | `wave10.eu_nrg_ind_pehnf` |
| [Eurostat Hydrogen, ammonia and e-fuels production (nrg_ind_psth2)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_psth2/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 2,599 | `wave10.eu_nrg_ind_psth2` |
| [Eurostat Renewable cooling ambient energy (nrg_ind_rcaebt)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_rcaebt/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 3,192 | `wave10.eu_nrg_ind_rcaebt` |
| [Eurostat Renewable cooling technical characteristics (nrg_ind_rctcbt)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_rctcbt/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 4,611 | `wave10.eu_nrg_ind_rctcbt` |
| [Eurostat Rate of electrification (nrg_ind_re)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_re/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 19,264 | `wave10.eu_nrg_ind_re` |
| [Eurostat Renewable energy share (nrg_ind_ren)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_ren/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 2,343 | `wave10.eu_nrg_ind_ren` |
| [Eurostat Renewable energy sources in overall share (nrg_ind_resovsh)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_resovsh/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 10,032 | `wave10.eu_nrg_ind_resovsh` |
| [Eurostat Renewable energy cooperation mechanisms - statistical transfers, joint projects and joint support schemes (nrg_ind_stjpjss)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_stjpjss/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 12,013 | `wave10.eu_nrg_ind_stjpjss` |
| [Eurostat Renewable energy share in electricity - detailed components (nrg_ind_ured)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_ured/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 15,012 | `wave10.eu_nrg_ind_ured` |
| [Eurostat Renewable energy share in heating and cooling - detailed components (nrg_ind_urhcd)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_urhcd/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 18,852 | `wave10.eu_nrg_ind_urhcd` |
| [Eurostat Renewable energy share in transport - detailed components (nrg_ind_urtd)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ind_urtd/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 33,452 | `wave10.eu_nrg_ind_urtd` |
| [Eurostat Batteries power capacities and energy storage (nrg_inf_bt)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_inf_bt/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 6,926 | `wave10.eu_nrg_inf_bt` |
| [Eurostat Electricity production capacities (nrg_inf_epc)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_inf_epc/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 93,704 | `wave10.eu_nrg_inf_epc` |
| [Eurostat Electricity production capacities for combustible fuels (nrg_inf_epct)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_inf_epct/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 6,230 | `wave10.eu_nrg_inf_epct` |
| [Eurostat Hydrogen, ammonia and e-fuels production capacity (nrg_inf_h2stpc)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_inf_h2stpc/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 2,462 | `wave10.eu_nrg_inf_h2stpc` |
| [Eurostat Liquid biofuels production capacities (nrg_inf_lbpc)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_inf_lbpc/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 2,499 | `wave10.eu_nrg_inf_lbpc` |
| [Eurostat Solar thermal collectors' surface (nrg_inf_stcs)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_inf_stcs/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 625 | `wave10.eu_nrg_inf_stcs` |
| [Eurostat Gas prices components for household consumers (nrg_pc_202_c)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_pc_202_c/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 2. Energy prices, taxes and markets | EU | country | CC BY 4.0 (Eurostat) | 56,971 | `wave10.eu_nrg_pc_202_c` |
| [Eurostat Household consumption volumes of gas by consumption bands (nrg_pc_202_v)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_pc_202_v/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 2. Energy prices, taxes and markets | EU | country | CC BY 4.0 (Eurostat) | 850 | `wave10.eu_nrg_pc_202_v` |
| [Eurostat Gas prices components for non-household consumers (nrg_pc_203_c)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_pc_203_c/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 2. Energy prices, taxes and markets | EU | country | CC BY 4.0 (Eurostat) | 95,229 | `wave10.eu_nrg_pc_203_c` |
| [Eurostat Non-household consumption volumes of gas by consumption bands (nrg_pc_203_v)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_pc_203_v/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 2. Energy prices, taxes and markets | EU | country | CC BY 4.0 (Eurostat) | 1,617 | `wave10.eu_nrg_pc_203_v` |
| [Eurostat Household consumption volumes of electricity by consumption bands (nrg_pc_204_v)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_pc_204_v/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 2. Energy prices, taxes and markets | EU | country | CC BY 4.0 (Eurostat) | 1,785 | `wave10.eu_nrg_pc_204_v` |
| [Eurostat Non-household consumption volumes of electricity by consumption bands (nrg_pc_205_v)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_pc_205_v/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 2. Energy prices, taxes and markets | EU | country | CC BY 4.0 (Eurostat) | 2,315 | `wave10.eu_nrg_pc_205_v` |
| [Eurostat Natural gas stock levels - annual data (nrg_stk_gas)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_stk_gas/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 6,738 | `wave10.eu_nrg_stk_gas` |
| [Eurostat Gas products stock levels - monthly data (nrg_stk_gasm)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_stk_gasm/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 38,584 | `wave10.eu_nrg_stk_gasm` |
| [Eurostat Hydrogen, ammonia and e-fuels stock levels (nrg_stk_h2)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_stk_h2/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 632 | `wave10.eu_nrg_stk_h2` |
| [Eurostat Oil stocks held abroad - monthly data (nrg_stk_oam)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_stk_oam/?format=TSV&compressed=true) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 50,915,404 | `wave10.eu_nrg_stk_oam` |
| [Eurostat Emergency oil stocks in days equivalent - monthly data (nrg_stk_oem)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_stk_oem/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 28,688 | `wave10.eu_nrg_stk_oem` |
| [Eurostat Oil products stock levels - annual data (nrg_stk_oil)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_stk_oil/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 49,646 | `wave10.eu_nrg_stk_oil` |
| [Eurostat Oil products stock levels - monthly data (nrg_stk_oilm)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_stk_oilm/?format=TSV&compressed=true) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 7,886,384 | `wave10.eu_nrg_stk_oilm` |
| [Eurostat Oil stocks held for other countries - monthly data (nrg_stk_oom)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_stk_oom/?format=TSV&compressed=true) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 21,952,802 | `wave10.eu_nrg_stk_oom` |
| [Eurostat Biofuels exports (nrg_te_bio)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_te_bio/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 621,122 | `wave10.eu_nrg_te_bio` |
| [Eurostat Electricity and derived heat exports (nrg_te_eh)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_te_eh/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 205,930 | `wave10.eu_nrg_te_eh` |
| [Eurostat Natural gas exports - annual data (nrg_te_gas)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_te_gas/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 409,048 | `wave10.eu_nrg_te_gas` |
| [Eurostat Natural gas exports - monthly data (nrg_te_gasm)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_te_gasm/?format=TSV&compressed=true) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 2,440,767 | `wave10.eu_nrg_te_gasm` |
| [Eurostat Hydrogen, ammonia and e-fuels exports (nrg_te_h2)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_te_h2/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 19,694 | `wave10.eu_nrg_te_h2` |
| [Eurostat Oil and petroleum products exports - annual data (nrg_te_oil)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_te_oil/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 3,905,304 | `wave10.eu_nrg_te_oil` |
| [Eurostat Oil and petroleum products exports - monthly data (nrg_te_oilm)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_te_oilm/?format=TSV&compressed=true) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 23,365,824 | `wave10.eu_nrg_te_oilm` |
| [Eurostat Solid fossil fuels exports (nrg_te_sff)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_te_sff/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 1,447,808 | `wave10.eu_nrg_te_sff` |
| [Eurostat Biofuels imports (nrg_ti_bio)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ti_bio/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 621,262 | `wave10.eu_nrg_ti_bio` |
| [Eurostat Crude oil imports by field of production - monthly data (nrg_ti_coifpm)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ti_coifpm/?format=TSV&compressed=true) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 7,284,668 | `wave10.eu_nrg_ti_coifpm` |
| [Eurostat Electricity and derived heat imports (nrg_ti_eh)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ti_eh/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 205,947 | `wave10.eu_nrg_ti_eh` |
| [Eurostat Natural gas imports - annual data (nrg_ti_gas)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ti_gas/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 409,049 | `wave10.eu_nrg_ti_gas` |
| [Eurostat Natural gas imports - monthly data (nrg_ti_gasm)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ti_gasm/?format=TSV&compressed=true) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 2,628,311 | `wave10.eu_nrg_ti_gasm` |
| [Eurostat Hydrogen, ammonia and e-fuels imports (nrg_ti_h2)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ti_h2/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 19,694 | `wave10.eu_nrg_ti_h2` |
| [Eurostat Oil and petroleum products imports - annual data (nrg_ti_oil)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ti_oil/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 3,902,880 | `wave10.eu_nrg_ti_oil` |
| [Eurostat Oil and petroleum products imports - monthly data (nrg_ti_oilm)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ti_oilm/?format=TSV&compressed=true) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 24,235,212 | `wave10.eu_nrg_ti_oilm` |
| [Eurostat Solid fossil fuels imports (nrg_ti_sff)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_ti_sff/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 1. Energy supply, balances and trade | EU | country | CC BY 4.0 (Eurostat) | 1,447,806 | `wave10.eu_nrg_ti_sff` |
| [Eurostat Locomotives and railcars by source of energy (rail_eq_locon)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_eq_locon/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,381 | `wave10.eu_rail_eq_locon` |
| [Eurostat Tractive power of locomotives and railcars by source of energy (rail_eq_locop)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_eq_locop/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 1,671 | `wave10.eu_rail_eq_locop` |
| [Eurostat Seat/berth capacity of passenger railway vehicles (rail_eq_pa_csb)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_eq_pa_csb/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 836 | `wave10.eu_rail_eq_pa_csb` |
| [Eurostat Seat capacity of passenger railway vehicles by type of vehicles (rail_eq_pa_cty)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_eq_pa_cty/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 829 | `wave10.eu_rail_eq_pa_cty` |
| [Eurostat Passenger railway vehicles, by type of vehicle (rail_eq_pa_nty)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_eq_pa_nty/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 1,683 | `wave10.eu_rail_eq_pa_nty` |
| [Eurostat Trainsets and capacity by type of speed (rail_eq_trset)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_eq_trset/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 1,497 | `wave10.eu_rail_eq_trset` |
| [Eurostat Railway transport vans (rail_eq_vans)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_eq_vans/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 241 | `wave10.eu_rail_eq_vans` |
| [Eurostat Wagons and their load capacity by type of wagons (rail_eq_wagon)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_eq_wagon/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 3,588 | `wave10.eu_rail_eq_wagon` |
| [Eurostat Length of electrified and non-electrified railway lines by track gauge (rail_if_line_ga)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_if_line_ga/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 6,897 | `wave10.eu_rail_if_line_ga` |
| [Eurostat Length of electric and non-electric railway lines by nature of transport (rail_if_line_na)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_if_line_na/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 5,959 | `wave10.eu_rail_if_line_na` |
| [Eurostat Length of railway lines by maximum permitted speed (rail_if_line_sp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_if_line_sp/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,305 | `wave10.eu_rail_if_line_sp` |
| [Eurostat Length of railway lines by number of tracks and electrification of lines (rail_if_line_tr)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_if_line_tr/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 5,022 | `wave10.eu_rail_if_line_tr` |
| [Eurostat Level crossings by type (rail_if_lvlcros)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_if_lvlcros/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 1,260 | `wave10.eu_rail_if_lvlcros` |
| [Eurostat Length of railway tracks by electrification of tracks (rail_if_tracks)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_if_tracks/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 1,421 | `wave10.eu_rail_if_tracks` |
| [Eurostat Length of railway lines equipped with the railway traffic management system (ERTMS) (rail_if_traff)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_if_traff/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 794 | `wave10.eu_rail_if_traff` |
| [Eurostat New motor coaches, buses and trolley buses by type of motor energy (road_eqr_busmot)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_busmot/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 4,897 | `wave10.eu_road_eqr_busmot` |
| [Eurostat Seat capacity of new motor coaches, buses and trolley buses (road_eqr_bussea)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_bussea/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 285 | `wave10.eu_road_eqr_bussea` |
| [Eurostat New motor coaches, buses and trolley buses , by type of vehicles (road_eqr_busveh)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_busveh/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 1,306 | `wave10.eu_road_eqr_busveh` |
| [Eurostat New passenger cars by type of motor energy and engine size (road_eqr_carmot)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_carmot/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 4,194 | `wave10.eu_road_eqr_carmot` |
| [Eurostat New passenger cars by type of motor energy (road_eqr_carpda)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_carpda/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 6,741 | `wave10.eu_road_eqr_carpda` |
| [Eurostat New lorries, by type of motor energy (road_eqr_lormot)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_lormot/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 9,944 | `wave10.eu_road_eqr_lormot` |
| [Eurostat New lorries and their load capacity by permissible maximum gross weight (road_eqr_lorrit)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_lorrit/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 3,557 | `wave10.eu_road_eqr_lorrit` |
| [Eurostat New mopeds and motorcycles by type of motor energy (road_eqr_mopeds)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_mopeds/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,199 | `wave10.eu_road_eqr_mopeds` |
| [Eurostat New motorcycles by engine size (road_eqr_motors)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_motors/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 1,305 | `wave10.eu_road_eqr_motors` |
| [Eurostat New semi-trailers and their load capacity, by permissible maximum gross weight (road_eqr_semit)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_semit/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,170 | `wave10.eu_road_eqr_semit` |
| [Eurostat New special purpose road vehicles (road_eqr_spurp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_spurp/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 442 | `wave10.eu_road_eqr_spurp` |
| [Eurostat New road tractors by type of motor energy (road_eqr_tracmot)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_tracmot/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 4,458 | `wave10.eu_road_eqr_tracmot` |
| [Eurostat New trailers and their load capacity, by permissible maximum gross weight (road_eqr_trail)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_trail/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,572 | `wave10.eu_road_eqr_trail` |
| [Eurostat New trams (road_eqr_trams)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_trams/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 163 | `wave10.eu_road_eqr_trams` |
| [Eurostat New passenger cars by unloaded weight (road_eqr_unlweig)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_unlweig/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,011 | `wave10.eu_road_eqr_unlweig` |
| [Eurostat New zero-emission vehicles by type of vehicle and type of motor energy (road_eqr_zev)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqr_zev/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 11,403 | `wave10.eu_road_eqr_zev` |
| [Eurostat Motor coaches, buses and trolley buses by age (road_eqs_busage)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_busage/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 3,174 | `wave10.eu_road_eqs_busage` |
| [Eurostat Motor coaches, buses and trolley buses, by type of motor energy (road_eqs_busmot)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_busmot/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 5,268 | `wave10.eu_road_eqs_busmot` |
| [Eurostat Seats /berths in motor coaches, buses and trolley buses (road_eqs_bussea)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_bussea/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 322 | `wave10.eu_road_eqs_bussea` |
| [Eurostat Motor coaches, buses and trolley buses, by type of vehicle (road_eqs_busveh)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_busveh/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 1,421 | `wave10.eu_road_eqs_busveh` |
| [Eurostat Passenger cars by age (road_eqs_carage)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_carage/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,729 | `wave10.eu_road_eqs_carage` |
| [Eurostat Passenger cars by Euro emission standard (road_eqs_caremiss)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_caremiss/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 89 | `wave10.eu_road_eqs_caremiss` |
| [Eurostat Passenger cars - per thousand inhabitants (road_eqs_carhab)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_carhab/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 654 | `wave10.eu_road_eqs_carhab` |
| [Eurostat Passenger cars, by type of motor energy and size of engine (road_eqs_carmot)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_carmot/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 4,431 | `wave10.eu_road_eqs_carmot` |
| [Eurostat Lorries, by type of motor energy (road_eqs_lormot)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_lormot/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 10,410 | `wave10.eu_road_eqs_lormot` |
| [Eurostat Lorries and road tractors by age and type of vehicle (road_eqs_lorroa)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_lorroa/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 6,990 | `wave10.eu_road_eqs_lorroa` |
| [Eurostat Lorries and their load capacity by permissible maximum gross weight (road_eqs_lorton)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_lorton/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 3,761 | `wave10.eu_road_eqs_lorton` |
| [Eurostat Mopeds and motorcycles by type of motor energy (road_eqs_mopeds)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_mopeds/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,353 | `wave10.eu_road_eqs_mopeds` |
| [Eurostat Motorcycles by engine size (road_eqs_motorc)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_motorc/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 1,435 | `wave10.eu_road_eqs_motorc` |
| [Eurostat Road tractors by type of motor energy (road_eqs_roaene)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_roaene/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 4,555 | `wave10.eu_road_eqs_roaene` |
| [Eurostat Semi-trailers and their load capacity, by permissible maximum gross weight (road_eqs_semit)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_semit/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,262 | `wave10.eu_road_eqs_semit` |
| [Eurostat Special purpose road vehicles (road_eqs_spurp)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_spurp/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 486 | `wave10.eu_road_eqs_spurp` |
| [Eurostat Trailers and their load capacity, by permissible maximum gross weight (road_eqs_trail)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_trail/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,604 | `wave10.eu_road_eqs_trail` |
| [Eurostat Trams (road_eqs_trams)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_trams/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 308 | `wave10.eu_road_eqs_trams` |
| [Eurostat Passenger cars by unloaded weight (road_eqs_unlweig)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_unlweig/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,026 | `wave10.eu_road_eqs_unlweig` |
| [Eurostat Stock of zero-emission vehicles at 31st December by type of vehicle and type of motor energy (road_eqs_zev)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/road_eqs_zev/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 11,334 | `wave10.eu_road_eqs_zev` |
| [Eurostat Population having neither a bath, nor a shower, nor indoor flushing toilet in their household by poverty status (sdg_06_10)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_06_10/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 1,308 | `wave10.eu_sdg_06_10` |
| [Eurostat Population connected to at least secondary wastewater treatment (sdg_06_20)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_06_20/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 435 | `wave10.eu_sdg_06_20` |
| [Eurostat Biochemical oxygen demand in rivers (sdg_06_30)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_06_30/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 308 | `wave10.eu_sdg_06_30` |
| [Eurostat Nitrate in groundwater (sdg_06_40)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_06_40/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 350 | `wave10.eu_sdg_06_40` |
| [Eurostat Phosphate in rivers (sdg_06_50)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_06_50/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 336 | `wave10.eu_sdg_06_50` |
| [Eurostat Water exploitation index, plus (WEI+) (sdg_06_60)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_06_60/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 1,034 | `wave10.eu_sdg_06_60` |
| [Eurostat Pesticides in rivers (sdg_06_70)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_06_70/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 285 | `wave10.eu_sdg_06_70` |
| [Eurostat Primary energy consumption (sdg_07_10)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_07_10/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 1,687 | `wave10.eu_sdg_07_10` |
| [Eurostat Final energy consumption (sdg_07_11)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_07_11/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 1,687 | `wave10.eu_sdg_07_11` |
| [Eurostat Final energy consumption in households per capita (sdg_07_20)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_07_20/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 591 | `wave10.eu_sdg_07_20` |
| [Eurostat Energy productivity (sdg_07_30)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_07_30/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 1,105 | `wave10.eu_sdg_07_30` |
| [Eurostat Share of renewable energy in gross final energy consumption by sector (sdg_07_40)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_07_40/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 2,283 | `wave10.eu_sdg_07_40` |
| [Eurostat Energy import dependency by products (sdg_07_50)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_07_50/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 2,388 | `wave10.eu_sdg_07_50` |
| [Eurostat Gross domestic expenditure on R&D by sector (sdg_09_10)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_09_10/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 2,988 | `wave10.eu_sdg_09_10` |
| [Eurostat R&D personnel by sector (sdg_09_30)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_09_30/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 2,585 | `wave10.eu_sdg_09_30` |
| [Eurostat Patent applications to the European Patent Office by applicants' / inventors' country of residence (sdg_09_40)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_09_40/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 2,346 | `wave10.eu_sdg_09_40` |
| [Eurostat Share of buses and trains in inland passenger transport (sdg_09_50)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_09_50/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 1,605 | `wave10.eu_sdg_09_50` |
| [Eurostat Share of rail and inland waterways in inland freight transport (sdg_09_60)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_09_60/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 1,380 | `wave10.eu_sdg_09_60` |
| [Eurostat Air emissions intensity of manufacturing (sdg_09_70)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_09_70/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 929 | `wave10.eu_sdg_09_70` |
| [Eurostat Severe housing deprivation rate by poverty status (sdg_11_11)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_11_11/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 1,377 | `wave10.eu_sdg_11_11` |
| [Eurostat Population living in households considering that they suffer from noise, by poverty status (sdg_11_20)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_11_20/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 1,371 | `wave10.eu_sdg_11_20` |
| [Eurostat Road traffic deaths, by type of roads (sdg_11_40)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_11_40/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 4,796 | `wave10.eu_sdg_11_40` |
| [Eurostat Premature deaths due to exposure to fine particulate matter (PM2.5) (sdg_11_52)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_11_52/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 1,064 | `wave10.eu_sdg_11_52` |
| [Eurostat Recycling rate of municipal waste (sdg_11_60)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_11_60/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 510 | `wave10.eu_sdg_11_60` |
| [Eurostat Consumption of chemicals by hazardousness - EU aggregate (sdg_12_10)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_12_10/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 60 | `wave10.eu_sdg_12_10` |
| [Eurostat Material footprint (sdg_12_21)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_12_21/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 984 | `wave10.eu_sdg_12_21` |
| [Eurostat Consumption footprint - single weighted score (sdg_12_31)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_12_31/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 420 | `wave10.eu_sdg_12_31` |
| [Eurostat Circular material use rate (sdg_12_41)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_12_41/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 420 | `wave10.eu_sdg_12_41` |
| [Eurostat Generation of waste by hazardousness (sdg_12_51)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_12_51/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 894 | `wave10.eu_sdg_12_51` |
| [Eurostat Gross value added in environmental goods and services sector (sdg_12_61)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_12_61/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 349 | `wave10.eu_sdg_12_61` |
| [Eurostat Domestic net greenhouse gas emissions (sdg_13_10)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_13_10/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 2,790 | `wave10.eu_sdg_13_10` |
| [Eurostat EU net greenhouse gas emissions (according to EU climate policies and targets) (sdg_13_11)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_13_11/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 45 | `wave10.eu_sdg_13_11` |
| [Eurostat Net greenhouse gas emissions of the Land use, Land use change and Forestry (LULUCF) sector (sdg_13_21)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_13_21/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 1,440 | `wave10.eu_sdg_13_21` |
| [Eurostat Average CO2 emissions per km from new passenger cars (sdg_13_31)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_13_31/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 458 | `wave10.eu_sdg_13_31` |
| [Eurostat Economic losses from weather- and climate-related extremes (sdg_13_40)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_13_40/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 2,340 | `wave10.eu_sdg_13_40` |
| [Eurostat Contribution to the international 100bn USD commitment on climate related expending (sdg_13_50)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_13_50/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 330 | `wave10.eu_sdg_13_50` |
| [Eurostat Green bond issuance by type of issuer (sdg_13_70)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_13_70/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 33 | `wave10.eu_sdg_13_70` |
| [Eurostat Green bond issuance by corporates and governments (sdg_13_70a)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/sdg_13_70a/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 308 | `wave10.eu_sdg_13_70a` |
| [Eurostat Fresh water abstraction by source per capita - m³ per capita (ten00003)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00003/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 963 | `wave10.eu_ten00003` |
| [Eurostat Water abstracted by sector of use (ten00006)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00006/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 1,870 | `wave10.eu_ten00006` |
| [Eurostat Sewage sludge production and disposal from urban wastewater (in dry substance (d.s)) (ten00030)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00030/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 2,122 | `wave10.eu_ten00030` |
| [Eurostat Recovery rates for packaging waste (ten00062)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00062/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 2,419 | `wave10.eu_ten00062` |
| [Eurostat Generation of waste by economic activity (ten00106)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00106/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 3,257 | `wave10.eu_ten00106` |
| [Eurostat Generation of waste by waste category (ten00108)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00108/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 596 | `wave10.eu_ten00108` |
| [Eurostat Waste generated by households by year and waste category (ten00110)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00110/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 579 | `wave10.eu_ten00110` |
| [Eurostat Gross available energy by product (ten00121)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00121/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 5,784 | `wave10.eu_ten00121` |
| [Eurostat Total energy supply by product (ten00122)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00122/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 5,784 | `wave10.eu_ten00122` |
| [Eurostat Final energy consumption by product (ten00123)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00123/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 5,772 | `wave10.eu_ten00123` |
| [Eurostat Final energy consumption by sector (ten00124)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00124/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 2,410 | `wave10.eu_ten00124` |
| [Eurostat Final energy consumption in households by type of fuel (ten00125)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00125/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 5,302 | `wave10.eu_ten00125` |
| [Eurostat Final energy consumption in transport by type of fuel (ten00126)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00126/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 6,748 | `wave10.eu_ten00126` |
| [Eurostat Final energy consumption in road transport by type of fuel (ten00127)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00127/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 5,784 | `wave10.eu_ten00127` |
| [Eurostat Final energy consumption in industry by type of fuel (ten00129)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00129/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 5,772 | `wave10.eu_ten00129` |
| [Eurostat National expenditure on environmental protection (ten00135)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00135/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 3,222 | `wave10.eu_ten00135` |
| [Eurostat Environmental protection investments of total economy (ten00136)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00136/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 314 | `wave10.eu_ten00136` |
| [Eurostat Domestic material consumption per capita (ten00137)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00137/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 424 | `wave10.eu_ten00137` |
| [Eurostat Landfill rate of waste excluding major mineral wastes (ten00138)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00138/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 154 | `wave10.eu_ten00138` |
| [Eurostat Energy taxes (ten00139)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00139/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 425 | `wave10.eu_ten00139` |
| [Eurostat Environmental tax revenues as share of total taxes (ten00141)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/ten00141/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 6. Sustainable development indicators | EU | country | CC BY 4.0 (Eurostat) | 755 | `wave10.eu_ten00141` |
| [Eurostat Modal split of inland freight transport (tran_hv_frmod)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/tran_hv_frmod/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 1,840 | `wave10.eu_tran_hv_frmod` |
| [Eurostat Volume of freight transport relative to GDP (tran_hv_frtra)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/tran_hv_frtra/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 445 | `wave10.eu_tran_hv_frtra` |
| [Eurostat Modal split of air, sea and inland freight transport (tran_hv_ms_frmod)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/tran_hv_ms_frmod/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,205 | `wave10.eu_tran_hv_ms_frmod` |
| [Eurostat Modal split of air, sea, inland and oil pipeline freight transport (tran_hv_ms_frmod6)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/tran_hv_ms_frmod6/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,580 | `wave10.eu_tran_hv_ms_frmod6` |
| [Eurostat Modal split of air, sea and inland passenger transport (tran_hv_ms_psmod)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/tran_hv_ms_psmod/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,250 | `wave10.eu_tran_hv_ms_psmod` |
| [Eurostat Modal split of inland passenger transport (tran_hv_psmod)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/tran_hv_psmod/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 2,180 | `wave10.eu_tran_hv_psmod` |
| [Eurostat Volume of passenger transport relative to GDP (tran_hv_pstra)](https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/tran_hv_pstra/?format=SDMX-CSV&compressed=false&startPeriod=2010) | 4. Transport, vehicles and fuels | EU | country | CC BY 4.0 (Eurostat) | 535 | `wave10.eu_tran_hv_pstra` |
| [World Bank WDI Agricultural land (sq. km) (AG.LND.AGRI.K2)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.AGRI.K2?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_agri_k2` |
| [World Bank WDI Agricultural land (% of land area) (AG.LND.AGRI.ZS)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.AGRI.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_agri_zs` |
| [World Bank WDI Arable land (% of land area) (AG.LND.ARBL.ZS)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.ARBL.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_arbl_zs` |
| [World Bank WDI Rural land area where elevation is below 5 meters (sq. km) (AG.LND.EL5M.RU.K2)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.EL5M.RU.K2?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_el5m_ru_k2` |
| [World Bank WDI Rural land area where elevation is below 5 meters (% of total land area) (AG.LND.EL5M.RU.ZS)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.EL5M.RU.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_el5m_ru_zs` |
| [World Bank WDI Urban land area where elevation is below 5 meters (sq. km) (AG.LND.EL5M.UR.K2)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.EL5M.UR.K2?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_el5m_ur_k2` |
| [World Bank WDI Urban land area where elevation is below 5 meters (% of total land area) (AG.LND.EL5M.UR.ZS)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.EL5M.UR.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_el5m_ur_zs` |
| [World Bank WDI Land area where elevation is below 5 meters (% of total land area) (AG.LND.EL5M.ZS)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.EL5M.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_el5m_zs` |
| [World Bank WDI Forest area (sq. km) (AG.LND.FRST.K2)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.FRST.K2?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_frst_k2` |
| [World Bank WDI Forest area (% of land area) (AG.LND.FRST.ZS)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.FRST.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_frst_zs` |
| [World Bank WDI Agricultural irrigated land (% of total agricultural land) (AG.LND.IRIG.AG.ZS)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.IRIG.AG.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_irig_ag_zs` |
| [World Bank WDI Average precipitation in depth (mm per year) (AG.LND.PRCP.MM)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.PRCP.MM?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_prcp_mm` |
| [World Bank WDI Land area (sq. km) (AG.LND.TOTL.K2)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.TOTL.K2?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_totl_k2` |
| [World Bank WDI Rural land area (sq. km) (AG.LND.TOTL.RU.K2)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.TOTL.RU.K2?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_totl_ru_k2` |
| [World Bank WDI Urban land area (sq. km) (AG.LND.TOTL.UR.K2)](https://api.worldbank.org/v2/country/all/indicator/AG.LND.TOTL.UR.K2?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_lnd_totl_ur_k2` |
| [World Bank WDI Surface area (sq. km) (AG.SRF.TOTL.K2)](https://api.worldbank.org/v2/country/all/indicator/AG.SRF.TOTL.K2?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_srf_totl_k2` |
| [World Bank WDI Cereal yield (kg per hectare) (AG.YLD.CREL.KG)](https://api.worldbank.org/v2/country/all/indicator/AG.YLD.CREL.KG?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ag_yld_crel_kg` |
| [World Bank WDI ICT service exports (BoP, current US$) (BX.GSR.CCIS.CD)](https://api.worldbank.org/v2/country/all/indicator/BX.GSR.CCIS.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_bx_gsr_ccis_cd` |
| [World Bank WDI ICT service exports (% of service exports, BoP) (BX.GSR.CCIS.ZS)](https://api.worldbank.org/v2/country/all/indicator/BX.GSR.CCIS.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_bx_gsr_ccis_zs` |
| [World Bank WDI Foreign direct investment, net inflows (% of GDP) (BX.KLT.DINV.WD.GD.ZS)](https://api.worldbank.org/v2/country/all/indicator/BX.KLT.DINV.WD.GD.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_bx_klt_dinv_wd_gd_zs` |
| [World Bank WDI Access to clean fuels and technologies for cooking, rural (% of rural population) (EG.CFT.ACCS.RU.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.CFT.ACCS.RU.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_cft_accs_ru_zs` |
| [World Bank WDI Access to clean fuels and technologies for cooking, urban (% of urban population) (EG.CFT.ACCS.UR.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.CFT.ACCS.UR.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_cft_accs_ur_zs` |
| [World Bank WDI Access to clean fuels and technologies for cooking (% of population) (EG.CFT.ACCS.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.CFT.ACCS.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_cft_accs_zs` |
| [World Bank WDI Energy intensity level of primary energy (MJ/$2021 PPP GDP) (EG.EGY.PRIM.PP.KD)](https://api.worldbank.org/v2/country/all/indicator/EG.EGY.PRIM.PP.KD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_egy_prim_pp_kd` |
| [World Bank WDI Access to electricity, rural (% of rural population) (EG.ELC.ACCS.RU.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.ELC.ACCS.RU.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_elc_accs_ru_zs` |
| [World Bank WDI Access to electricity, urban (% of urban population) (EG.ELC.ACCS.UR.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.ELC.ACCS.UR.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_elc_accs_ur_zs` |
| [World Bank WDI Access to electricity (% of population) (EG.ELC.ACCS.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.ELC.ACCS.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_elc_accs_zs` |
| [World Bank WDI Electricity production from coal sources (% of total) (EG.ELC.COAL.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.ELC.COAL.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_elc_coal_zs` |
| [World Bank WDI Electricity production from oil, gas and coal sources (% of total) (EG.ELC.FOSL.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.ELC.FOSL.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_elc_fosl_zs` |
| [World Bank WDI Electricity production from hydroelectric sources (% of total) (EG.ELC.HYRO.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.ELC.HYRO.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_elc_hyro_zs` |
| [World Bank WDI Electric power transmission and distribution losses (% of output) (EG.ELC.LOSS.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.ELC.LOSS.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_elc_loss_zs` |
| [World Bank WDI Electricity production from natural gas sources (% of total) (EG.ELC.NGAS.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.ELC.NGAS.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_elc_ngas_zs` |
| [World Bank WDI Electricity production from nuclear sources (% of total) (EG.ELC.NUCL.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.ELC.NUCL.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_elc_nucl_zs` |
| [World Bank WDI Electricity production from oil sources (% of total) (EG.ELC.PETR.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.ELC.PETR.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_elc_petr_zs` |
| [World Bank WDI Renewable electricity output (% of total electricity output) (EG.ELC.RNEW.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.ELC.RNEW.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_elc_rnew_zs` |
| [World Bank WDI Electricity production from renewable sources, excluding hydroelectric (kWh) (EG.ELC.RNWX.KH)](https://api.worldbank.org/v2/country/all/indicator/EG.ELC.RNWX.KH?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_elc_rnwx_kh` |
| [World Bank WDI Electricity production from renewable sources, excluding hydroelectric (% of total) (EG.ELC.RNWX.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.ELC.RNWX.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_elc_rnwx_zs` |
| [World Bank WDI Renewable energy consumption (% of total final energy consumption) (EG.FEC.RNEW.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.FEC.RNEW.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_fec_rnew_zs` |
| [World Bank WDI GDP per unit of energy use (PPP $ per kg of oil equivalent) (EG.GDP.PUSE.KO.PP)](https://api.worldbank.org/v2/country/all/indicator/EG.GDP.PUSE.KO.PP?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_gdp_puse_ko_pp` |
| [World Bank WDI GDP per unit of energy use (constant 2021 PPP $ per kg of oil equivalent) (EG.GDP.PUSE.KO.PP.KD)](https://api.worldbank.org/v2/country/all/indicator/EG.GDP.PUSE.KO.PP.KD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_gdp_puse_ko_pp_kd` |
| [World Bank WDI Energy imports, net (% of energy use) (EG.IMP.CONS.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.IMP.CONS.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_imp_cons_zs` |
| [World Bank WDI Alternative and nuclear energy (% of total energy use) (EG.USE.COMM.CL.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.USE.COMM.CL.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_use_comm_cl_zs` |
| [World Bank WDI Fossil fuel energy consumption (% of total) (EG.USE.COMM.FO.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.USE.COMM.FO.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_use_comm_fo_zs` |
| [World Bank WDI Energy use (kg of oil equivalent) per $1,000 GDP (constant 2021 PPP) (EG.USE.COMM.GD.PP.KD)](https://api.worldbank.org/v2/country/all/indicator/EG.USE.COMM.GD.PP.KD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_use_comm_gd_pp_kd` |
| [World Bank WDI Combustible renewables and waste (% of total energy) (EG.USE.CRNW.ZS)](https://api.worldbank.org/v2/country/all/indicator/EG.USE.CRNW.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_use_crnw_zs` |
| [World Bank WDI Electric power consumption (kWh per capita) (EG.USE.ELEC.KH.PC)](https://api.worldbank.org/v2/country/all/indicator/EG.USE.ELEC.KH.PC?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_use_elec_kh_pc` |
| [World Bank WDI Energy use (kg of oil equivalent per capita) (EG.USE.PCAP.KG.OE)](https://api.worldbank.org/v2/country/all/indicator/EG.USE.PCAP.KG.OE?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_eg_use_pcap_kg_oe` |
| [World Bank WDI PM2.5 air pollution, mean annual exposure (micrograms per cubic meter) (EN.ATM.PM25.MC.M3)](https://api.worldbank.org/v2/country/all/indicator/EN.ATM.PM25.MC.M3?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_atm_pm25_mc_m3` |
| [World Bank WDI PM2.5 pollution, population exposed to levels exceeding WHO Interim Target-1 value (% of total) (EN.ATM.PM25.MC.T1.ZS)](https://api.worldbank.org/v2/country/all/indicator/EN.ATM.PM25.MC.T1.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_atm_pm25_mc_t1_zs` |
| [World Bank WDI PM2.5 pollution, population exposed to levels exceeding WHO Interim Target-2 value (% of total) (EN.ATM.PM25.MC.T2.ZS)](https://api.worldbank.org/v2/country/all/indicator/EN.ATM.PM25.MC.T2.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_atm_pm25_mc_t2_zs` |
| [World Bank WDI PM2.5 pollution, population exposed to levels exceeding WHO Interim Target-3 value (% of total) (EN.ATM.PM25.MC.T3.ZS)](https://api.worldbank.org/v2/country/all/indicator/EN.ATM.PM25.MC.T3.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_atm_pm25_mc_t3_zs` |
| [World Bank WDI PM2.5 air pollution, population exposed to levels exceeding WHO guideline value (% of total) (EN.ATM.PM25.MC.ZS)](https://api.worldbank.org/v2/country/all/indicator/EN.ATM.PM25.MC.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_atm_pm25_mc_zs` |
| [World Bank WDI Bird species, threatened (EN.BIR.THRD.NO)](https://api.worldbank.org/v2/country/all/indicator/EN.BIR.THRD.NO?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_bir_thrd_no` |
| [World Bank WDI Disaster risk reduction progress score (1-5 scale; 5=best) (EN.CLC.DRSK.XQ)](https://api.worldbank.org/v2/country/all/indicator/EN.CLC.DRSK.XQ?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_clc_drsk_xq` |
| [World Bank WDI Droughts, floods, extreme temperatures (% of population, average 1990-2009) (EN.CLC.MDAT.ZS)](https://api.worldbank.org/v2/country/all/indicator/EN.CLC.MDAT.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_clc_mdat_zs` |
| [World Bank WDI Fish species, threatened (EN.FSH.THRD.NO)](https://api.worldbank.org/v2/country/all/indicator/EN.FSH.THRD.NO?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_fsh_thrd_no` |
| [World Bank WDI Total greenhouse gas emissions including LULUCF (Mt CO2e) (EN.GHG.ALL.LU.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.ALL.LU.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_all_lu_mt_ce_ar5` |
| [World Bank WDI Total greenhouse gas emissions excluding LULUCF (Mt CO2e) (EN.GHG.ALL.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.ALL.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_all_mt_ce_ar5` |
| [World Bank WDI Total greenhouse gas emissions excluding LULUCF per capita (t CO2e/capita) (EN.GHG.ALL.PC.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.ALL.PC.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_all_pc_ce_ar5` |
| [World Bank WDI Methane (CH4) emissions from Agriculture (Mt CO2e) (EN.GHG.CH4.AG.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CH4.AG.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_ch4_ag_mt_ce_ar5` |
| [World Bank WDI Methane (CH4) emissions from Building (Energy) (Mt CO2e) (EN.GHG.CH4.BU.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CH4.BU.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_ch4_bu_mt_ce_ar5` |
| [World Bank WDI Methane (CH4) emissions from Fugitive Emissions (Energy) (Mt CO2e) (EN.GHG.CH4.FE.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CH4.FE.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_ch4_fe_mt_ce_ar5` |
| [World Bank WDI Methane (CH4) emissions from Industrial Combustion (Energy) (Mt CO2e) (EN.GHG.CH4.IC.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CH4.IC.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_ch4_ic_mt_ce_ar5` |
| [World Bank WDI Methane (CH4) emissions from Industrial Processes (Mt CO2e) (EN.GHG.CH4.IP.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CH4.IP.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_ch4_ip_mt_ce_ar5` |
| [World Bank WDI Methane (CH4) emissions (total) excluding LULUCF (Mt CO2e) (EN.GHG.CH4.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CH4.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_ch4_mt_ce_ar5` |
| [World Bank WDI Methane (CH4) emissions from Power Industry (Energy) (Mt CO2e) (EN.GHG.CH4.PI.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CH4.PI.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_ch4_pi_mt_ce_ar5` |
| [World Bank WDI Methane (CH4) emissions from Transport (Energy) (Mt CO2e) (EN.GHG.CH4.TR.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CH4.TR.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_ch4_tr_mt_ce_ar5` |
| [World Bank WDI Methane (CH4) emissions from Waste (Mt CO2e) (EN.GHG.CH4.WA.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CH4.WA.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_ch4_wa_mt_ce_ar5` |
| [World Bank WDI Methane (CH4) emissions (total) excluding LULUCF (% change from 1990) (EN.GHG.CH4.ZG.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CH4.ZG.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_ch4_zg_ar5` |
| [World Bank WDI Carbon dioxide (CO2) emissions from Agriculture (Mt CO2e) (EN.GHG.CO2.AG.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.AG.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_ag_mt_ce_ar5` |
| [World Bank WDI Carbon dioxide (CO2) emissions from Building (Energy) (Mt CO2e) (EN.GHG.CO2.BU.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.BU.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_bu_mt_ce_ar5` |
| [World Bank WDI Carbon dioxide (CO2) emissions from Fugitive Emissions (Energy) (Mt CO2e) (EN.GHG.CO2.FE.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.FE.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_fe_mt_ce_ar5` |
| [World Bank WDI Carbon dioxide (CO2) emissions from Industrial Combustion (Energy) (Mt CO2e) (EN.GHG.CO2.IC.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.IC.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_ic_mt_ce_ar5` |
| [World Bank WDI Carbon dioxide (CO2) emissions from Industrial Processes (Mt CO2e) (EN.GHG.CO2.IP.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.IP.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_ip_mt_ce_ar5` |
| [World Bank WDI Carbon dioxide (CO2) net fluxes from LULUCF - Deforestation (Mt CO2e) (EN.GHG.CO2.LU.DF.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.LU.DF.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_lu_df_mt_ce_ar5` |
| [World Bank WDI Carbon dioxide (CO2) net fluxes from LULUCF - Forest Land (Mt CO2e) (EN.GHG.CO2.LU.FL.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.LU.FL.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_lu_fl_mt_ce_ar5` |
| [World Bank WDI Carbon dioxide (CO2) net fluxes from LULUCF - Total excluding non-tropical fires (Mt CO2e) (EN.GHG.CO2.LU.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.LU.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_lu_mt_ce_ar5` |
| [World Bank WDI Carbon dioxide (CO2) net fluxes from LULUCF - Other Land (Mt CO2e) (EN.GHG.CO2.LU.OL.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.LU.OL.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_lu_ol_mt_ce_ar5` |
| [World Bank WDI Carbon dioxide (CO2) net fluxes from LULUCF - Organic Soil (Mt CO2e) (EN.GHG.CO2.LU.OS.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.LU.OS.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_lu_os_mt_ce_ar5` |
| [World Bank WDI Carbon dioxide (CO2) emissions (total) excluding LULUCF (Mt CO2e) (EN.GHG.CO2.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_mt_ce_ar5` |
| [World Bank WDI Carbon dioxide (CO2) emissions excluding LULUCF per capita (t CO2e/capita) (EN.GHG.CO2.PC.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.PC.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_pc_ce_ar5` |
| [World Bank WDI Carbon dioxide (CO2) emissions from Power Industry (Energy) (Mt CO2e) (EN.GHG.CO2.PI.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.PI.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_pi_mt_ce_ar5` |
| [World Bank WDI Carbon intensity of GDP (kg CO2e per constant 2015 US$ of GDP) (EN.GHG.CO2.RT.GDP.KD)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.RT.GDP.KD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_rt_gdp_kd` |
| [World Bank WDI Carbon intensity of GDP (kg CO2e per 2021 PPP $ of GDP) (EN.GHG.CO2.RT.GDP.PP.KD)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.RT.GDP.PP.KD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_rt_gdp_pp_kd` |
| [World Bank WDI Carbon dioxide (CO2) emissions from Transport (Energy) (Mt CO2e) (EN.GHG.CO2.TR.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.TR.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_tr_mt_ce_ar5` |
| [World Bank WDI Carbon dioxide (CO2) emissions from Waste (Mt CO2e) (EN.GHG.CO2.WA.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.WA.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_wa_mt_ce_ar5` |
| [World Bank WDI Carbon dioxide (CO2) emissions (total) excluding LULUCF (% change from 1990) (EN.GHG.CO2.ZG.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.ZG.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_co2_zg_ar5` |
| [World Bank WDI F-gases emissions from Industrial Processes (Mt CO2e) (EN.GHG.FGAS.IP.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.FGAS.IP.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_fgas_ip_mt_ce_ar5` |
| [World Bank WDI Nitrous oxide (N2O) emissions from Agriculture (Mt CO2e) (EN.GHG.N2O.AG.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.N2O.AG.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_n2o_ag_mt_ce_ar5` |
| [World Bank WDI Nitrous oxide (N2O) emissions from Building (Energy) (Mt CO2e) (EN.GHG.N2O.BU.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.N2O.BU.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_n2o_bu_mt_ce_ar5` |
| [World Bank WDI Nitrous oxide (N2O) emissions from Fugitive Emissions (Energy) (Mt CO2e) (EN.GHG.N2O.FE.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.N2O.FE.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_n2o_fe_mt_ce_ar5` |
| [World Bank WDI Nitrous oxide (N2O) emissions from Industrial Combustion (Energy) (Mt CO2e) (EN.GHG.N2O.IC.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.N2O.IC.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_n2o_ic_mt_ce_ar5` |
| [World Bank WDI Nitrous oxide (N2O) emissions from Industrial Processes (Mt CO2e) (EN.GHG.N2O.IP.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.N2O.IP.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_n2o_ip_mt_ce_ar5` |
| [World Bank WDI Nitrous oxide (N2O) emissions (total) excluding LULUCF (Mt CO2e) (EN.GHG.N2O.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.N2O.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_n2o_mt_ce_ar5` |
| [World Bank WDI Nitrous oxide (N2O) emissions from Power Industry (Energy) (Mt CO2e) (EN.GHG.N2O.PI.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.N2O.PI.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_n2o_pi_mt_ce_ar5` |
| [World Bank WDI Nitrous oxide (N2O) emissions from Transport (Energy) (Mt CO2e) (EN.GHG.N2O.TR.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.N2O.TR.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_n2o_tr_mt_ce_ar5` |
| [World Bank WDI Nitrous oxide (N2O) emissions from Waste (Mt CO2e) (EN.GHG.N2O.WA.MT.CE.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.N2O.WA.MT.CE.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_n2o_wa_mt_ce_ar5` |
| [World Bank WDI Nitrous oxide (N2O) emissions (total) excluding LULUCF (% change from 1990) (EN.GHG.N2O.ZG.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.N2O.ZG.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_n2o_zg_ar5` |
| [World Bank WDI Total greenhouse gas emissions excluding LULUCF (% change from 1990) (EN.GHG.TOT.ZG.AR5)](https://api.worldbank.org/v2/country/all/indicator/EN.GHG.TOT.ZG.AR5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_ghg_tot_zg_ar5` |
| [World Bank WDI Plant species (higher), threatened (EN.HPT.THRD.NO)](https://api.worldbank.org/v2/country/all/indicator/EN.HPT.THRD.NO?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_hpt_thrd_no` |
| [World Bank WDI Mammal species, threatened (EN.MAM.THRD.NO)](https://api.worldbank.org/v2/country/all/indicator/EN.MAM.THRD.NO?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_mam_thrd_no` |
| [World Bank WDI Rural population living in areas where elevation is below 5 meters (% of total population) (EN.POP.EL5M.RU.ZS)](https://api.worldbank.org/v2/country/all/indicator/EN.POP.EL5M.RU.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_pop_el5m_ru_zs` |
| [World Bank WDI Urban population living in areas where elevation is below 5 meters (% of total population) (EN.POP.EL5M.UR.ZS)](https://api.worldbank.org/v2/country/all/indicator/EN.POP.EL5M.UR.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_pop_el5m_ur_zs` |
| [World Bank WDI Population living in areas where elevation is below 5 meters (% of total population) (EN.POP.EL5M.ZS)](https://api.worldbank.org/v2/country/all/indicator/EN.POP.EL5M.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_pop_el5m_zs` |
| [World Bank WDI Population living in slums (% of urban population) (EN.POP.SLUM.UR.ZS)](https://api.worldbank.org/v2/country/all/indicator/EN.POP.SLUM.UR.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_pop_slum_ur_zs` |
| [World Bank WDI Population in urban agglomerations of more than 1 million (% of total population) (EN.URB.MCTY.TL.ZS)](https://api.worldbank.org/v2/country/all/indicator/EN.URB.MCTY.TL.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_en_urb_mcty_tl_zs` |
| [World Bank WDI Aquaculture production (metric tons) (ER.FSH.AQUA.MT)](https://api.worldbank.org/v2/country/all/indicator/ER.FSH.AQUA.MT?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_fsh_aqua_mt` |
| [World Bank WDI Capture fisheries production (metric tons) (ER.FSH.CAPT.MT)](https://api.worldbank.org/v2/country/all/indicator/ER.FSH.CAPT.MT?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_fsh_capt_mt` |
| [World Bank WDI Total fisheries production (metric tons) (ER.FSH.PROD.MT)](https://api.worldbank.org/v2/country/all/indicator/ER.FSH.PROD.MT?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_fsh_prod_mt` |
| [World Bank WDI Water productivity, total (constant 2015 US$ GDP per cubic meter of total freshwater withdrawal) (ER.GDP.FWTL.M3.KD)](https://api.worldbank.org/v2/country/all/indicator/ER.GDP.FWTL.M3.KD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_gdp_fwtl_m3_kd` |
| [World Bank WDI Annual freshwater withdrawals, agriculture (% of total freshwater withdrawal) (ER.H2O.FWAG.ZS)](https://api.worldbank.org/v2/country/all/indicator/ER.H2O.FWAG.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_h2o_fwag_zs` |
| [World Bank WDI Annual freshwater withdrawals, domestic (% of total freshwater withdrawal) (ER.H2O.FWDM.ZS)](https://api.worldbank.org/v2/country/all/indicator/ER.H2O.FWDM.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_h2o_fwdm_zs` |
| [World Bank WDI Annual freshwater withdrawals, industry (% of total freshwater withdrawal) (ER.H2O.FWIN.ZS)](https://api.worldbank.org/v2/country/all/indicator/ER.H2O.FWIN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_h2o_fwin_zs` |
| [World Bank WDI Level of water stress: freshwater withdrawal as a proportion of available freshwater resources (ER.H2O.FWST.ZS)](https://api.worldbank.org/v2/country/all/indicator/ER.H2O.FWST.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_h2o_fwst_zs` |
| [World Bank WDI Annual freshwater withdrawals, total (billion cubic meters) (ER.H2O.FWTL.K3)](https://api.worldbank.org/v2/country/all/indicator/ER.H2O.FWTL.K3?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_h2o_fwtl_k3` |
| [World Bank WDI Annual freshwater withdrawals, total (% of internal resources) (ER.H2O.FWTL.ZS)](https://api.worldbank.org/v2/country/all/indicator/ER.H2O.FWTL.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_h2o_fwtl_zs` |
| [World Bank WDI Renewable internal freshwater resources, total (billion cubic meters) (ER.H2O.INTR.K3)](https://api.worldbank.org/v2/country/all/indicator/ER.H2O.INTR.K3?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_h2o_intr_k3` |
| [World Bank WDI Renewable internal freshwater resources per capita (cubic meters) (ER.H2O.INTR.PC)](https://api.worldbank.org/v2/country/all/indicator/ER.H2O.INTR.PC?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_h2o_intr_pc` |
| [World Bank WDI Terrestrial protected areas (% of total land area) (ER.LND.PTLD.ZS)](https://api.worldbank.org/v2/country/all/indicator/ER.LND.PTLD.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_lnd_ptld_zs` |
| [World Bank WDI Marine protected areas (% of territorial waters) (ER.MRN.PTMR.ZS)](https://api.worldbank.org/v2/country/all/indicator/ER.MRN.PTMR.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_mrn_ptmr_zs` |
| [World Bank WDI Terrestrial and marine protected areas (% of total territorial area) (ER.PTD.TOTL.ZS)](https://api.worldbank.org/v2/country/all/indicator/ER.PTD.TOTL.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_er_ptd_totl_zs` |
| [World Bank WDI Time to obtain an electrical connection (days) (IC.ELC.DURS)](https://api.worldbank.org/v2/country/all/indicator/IC.ELC.DURS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ic_elc_durs` |
| [World Bank WDI Firms using banks to finance investment (% of firms) (IC.FRM.BNKS.ZS)](https://api.worldbank.org/v2/country/all/indicator/IC.FRM.BNKS.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ic_frm_bnks_zs` |
| [World Bank WDI Value lost due to electrical outages (% of sales for affected firms) (IC.FRM.OUTG.ZS)](https://api.worldbank.org/v2/country/all/indicator/IC.FRM.OUTG.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ic_frm_outg_zs` |
| [World Bank WDI Investment in energy with private participation (current US$) (IE.PPI.ENGY.CD)](https://api.worldbank.org/v2/country/all/indicator/IE.PPI.ENGY.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ie_ppi_engy_cd` |
| [World Bank WDI Investment in ICT with private participation (current US$) (IE.PPI.ICTI.CD)](https://api.worldbank.org/v2/country/all/indicator/IE.PPI.ICTI.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ie_ppi_icti_cd` |
| [World Bank WDI Investment in transport with private participation (current US$) (IE.PPI.TRAN.CD)](https://api.worldbank.org/v2/country/all/indicator/IE.PPI.TRAN.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ie_ppi_tran_cd` |
| [World Bank WDI Investment in water and sanitation with private participation (current US$) (IE.PPI.WATR.CD)](https://api.worldbank.org/v2/country/all/indicator/IE.PPI.WATR.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ie_ppi_watr_cd` |
| [World Bank WDI Public private partnerships investment in energy (current US$) (IE.PPN.ENGY.CD)](https://api.worldbank.org/v2/country/all/indicator/IE.PPN.ENGY.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ie_ppn_engy_cd` |
| [World Bank WDI Public private partnerships investment in ICT (current US$) (IE.PPN.ICTI.CD)](https://api.worldbank.org/v2/country/all/indicator/IE.PPN.ICTI.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ie_ppn_icti_cd` |
| [World Bank WDI Public private partnerships investment in transport (current US$) (IE.PPN.TRAN.CD)](https://api.worldbank.org/v2/country/all/indicator/IE.PPN.TRAN.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ie_ppn_tran_cd` |
| [World Bank WDI Public private partnerships investment in water and sanitation (current US$) (IE.PPN.WATR.CD)](https://api.worldbank.org/v2/country/all/indicator/IE.PPN.WATR.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ie_ppn_watr_cd` |
| [World Bank WDI Industrial design applications, nonresident, by count (IP.IDS.NRCT)](https://api.worldbank.org/v2/country/all/indicator/IP.IDS.NRCT?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ip_ids_nrct` |
| [World Bank WDI Industrial design applications, resident, by count (IP.IDS.RSCT)](https://api.worldbank.org/v2/country/all/indicator/IP.IDS.RSCT?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ip_ids_rsct` |
| [World Bank WDI Trademark applications, nonresident, by count (IP.TMK.NRCT)](https://api.worldbank.org/v2/country/all/indicator/IP.TMK.NRCT?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ip_tmk_nrct` |
| [World Bank WDI Trademark applications, resident, by count (IP.TMK.RSCT)](https://api.worldbank.org/v2/country/all/indicator/IP.TMK.RSCT?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ip_tmk_rsct` |
| [World Bank WDI CPIA public sector management and institutions cluster average (1=low to 6=high) (IQ.CPA.PUBS.XQ)](https://api.worldbank.org/v2/country/all/indicator/IQ.CPA.PUBS.XQ?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_iq_cpa_pubs_xq` |
| [World Bank WDI Air transport, registered carrier departures worldwide (IS.AIR.DPRT)](https://api.worldbank.org/v2/country/all/indicator/IS.AIR.DPRT?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_is_air_dprt` |
| [World Bank WDI Air transport, freight (million ton-km) (IS.AIR.GOOD.MT.K1)](https://api.worldbank.org/v2/country/all/indicator/IS.AIR.GOOD.MT.K1?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_is_air_good_mt_k1` |
| [World Bank WDI Air transport, passengers carried (IS.AIR.PSGR)](https://api.worldbank.org/v2/country/all/indicator/IS.AIR.PSGR?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_is_air_psgr` |
| [World Bank WDI Railways, goods transported (million ton-km) (IS.RRS.GOOD.MT.K6)](https://api.worldbank.org/v2/country/all/indicator/IS.RRS.GOOD.MT.K6?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_is_rrs_good_mt_k6` |
| [World Bank WDI Railways, passengers carried (million passenger-km) (IS.RRS.PASG.KM)](https://api.worldbank.org/v2/country/all/indicator/IS.RRS.PASG.KM?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_is_rrs_pasg_km` |
| [World Bank WDI Rail lines (total route-km) (IS.RRS.TOTL.KM)](https://api.worldbank.org/v2/country/all/indicator/IS.RRS.TOTL.KM?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_is_rrs_totl_km` |
| [World Bank WDI Liner shipping connectivity index (maximum value in 2004 = 100) (IS.SHP.GCNW.XQ)](https://api.worldbank.org/v2/country/all/indicator/IS.SHP.GCNW.XQ?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_is_shp_gcnw_xq` |
| [World Bank WDI Container port traffic (TEU: 20 foot equivalent units) (IS.SHP.GOOD.TU)](https://api.worldbank.org/v2/country/all/indicator/IS.SHP.GOOD.TU?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_is_shp_good_tu` |
| [World Bank WDI Mobile cellular subscriptions (IT.CEL.SETS)](https://api.worldbank.org/v2/country/all/indicator/IT.CEL.SETS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_it_cel_sets` |
| [World Bank WDI Mobile cellular subscriptions (per 100 people) (IT.CEL.SETS.P2)](https://api.worldbank.org/v2/country/all/indicator/IT.CEL.SETS.P2?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_it_cel_sets_p2` |
| [World Bank WDI Fixed telephone subscriptions (IT.MLT.MAIN)](https://api.worldbank.org/v2/country/all/indicator/IT.MLT.MAIN?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_it_mlt_main` |
| [World Bank WDI Fixed telephone subscriptions (per 100 people) (IT.MLT.MAIN.P2)](https://api.worldbank.org/v2/country/all/indicator/IT.MLT.MAIN.P2?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_it_mlt_main_p2` |
| [World Bank WDI Fixed broadband subscriptions (IT.NET.BBND)](https://api.worldbank.org/v2/country/all/indicator/IT.NET.BBND?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_it_net_bbnd` |
| [World Bank WDI Fixed broadband subscriptions (per 100 people) (IT.NET.BBND.P2)](https://api.worldbank.org/v2/country/all/indicator/IT.NET.BBND.P2?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_it_net_bbnd_p2` |
| [World Bank WDI Secure Internet servers (IT.NET.SECR)](https://api.worldbank.org/v2/country/all/indicator/IT.NET.SECR?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_it_net_secr` |
| [World Bank WDI Secure Internet servers (per 1 million people) (IT.NET.SECR.P6)](https://api.worldbank.org/v2/country/all/indicator/IT.NET.SECR.P6?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_it_net_secr_p6` |
| [World Bank WDI Individuals using the Internet, female (% of female population) (IT.NET.USER.FE.ZS)](https://api.worldbank.org/v2/country/all/indicator/IT.NET.USER.FE.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_it_net_user_fe_zs` |
| [World Bank WDI Individuals using the Internet, male (% of male population) (IT.NET.USER.MA.ZS)](https://api.worldbank.org/v2/country/all/indicator/IT.NET.USER.MA.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_it_net_user_ma_zs` |
| [World Bank WDI Individuals using the Internet (% of population) (IT.NET.USER.ZS)](https://api.worldbank.org/v2/country/all/indicator/IT.NET.USER.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_it_net_user_zs` |
| [World Bank WDI Agriculture, forestry, and fishing, value added (% of GDP) (NV.AGR.TOTL.ZS)](https://api.worldbank.org/v2/country/all/indicator/NV.AGR.TOTL.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_nv_agr_totl_zs` |
| [World Bank WDI Adjusted savings: education expenditure (current US$) (NY.ADJ.AEDU.CD)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.AEDU.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_aedu_cd` |
| [World Bank WDI Adjusted savings: education expenditure (% of GNI) (NY.ADJ.AEDU.GN.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.AEDU.GN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_aedu_gn_zs` |
| [World Bank WDI Adjusted savings: carbon dioxide damage (current US$) (NY.ADJ.DCO2.CD)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.DCO2.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_dco2_cd` |
| [World Bank WDI Adjusted savings: carbon dioxide damage (% of GNI) (NY.ADJ.DCO2.GN.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.DCO2.GN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_dco2_gn_zs` |
| [World Bank WDI Adjusted savings: net forest depletion (current US$) (NY.ADJ.DFOR.CD)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.DFOR.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_dfor_cd` |
| [World Bank WDI Adjusted savings: net forest depletion (% of GNI) (NY.ADJ.DFOR.GN.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.DFOR.GN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_dfor_gn_zs` |
| [World Bank WDI Adjusted savings: consumption of fixed capital (current US$) (NY.ADJ.DKAP.CD)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.DKAP.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_dkap_cd` |
| [World Bank WDI Adjusted savings: consumption of fixed capital (% of GNI) (NY.ADJ.DKAP.GN.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.DKAP.GN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_dkap_gn_zs` |
| [World Bank WDI Adjusted savings: mineral depletion (current US$) (NY.ADJ.DMIN.CD)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.DMIN.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_dmin_cd` |
| [World Bank WDI Adjusted savings: mineral depletion (% of GNI) (NY.ADJ.DMIN.GN.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.DMIN.GN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_dmin_gn_zs` |
| [World Bank WDI Adjusted savings: energy depletion (current US$) (NY.ADJ.DNGY.CD)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.DNGY.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_dngy_cd` |
| [World Bank WDI Adjusted savings: energy depletion (% of GNI) (NY.ADJ.DNGY.GN.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.DNGY.GN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_dngy_gn_zs` |
| [World Bank WDI Adjusted savings: particulate emission damage (current US$) (NY.ADJ.DPEM.CD)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.DPEM.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_dpem_cd` |
| [World Bank WDI Adjusted savings: particulate emission damage (% of GNI) (NY.ADJ.DPEM.GN.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.DPEM.GN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_dpem_gn_zs` |
| [World Bank WDI Adjusted savings: natural resources depletion (% of GNI) (NY.ADJ.DRES.GN.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.DRES.GN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_dres_gn_zs` |
| [World Bank WDI Adjusted savings: gross savings (% of GNI) (NY.ADJ.ICTR.GN.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.ICTR.GN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_ictr_gn_zs` |
| [World Bank WDI Adjusted savings: net national savings (current US$) (NY.ADJ.NNAT.CD)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.NNAT.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_nnat_cd` |
| [World Bank WDI Adjusted savings: net national savings (% of GNI) (NY.ADJ.NNAT.GN.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.NNAT.GN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_nnat_gn_zs` |
| [World Bank WDI Adjusted net savings, including particulate emission damage (current US$) (NY.ADJ.SVNG.CD)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.SVNG.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_svng_cd` |
| [World Bank WDI Adjusted net savings, including particulate emission damage (% of GNI) (NY.ADJ.SVNG.GN.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.SVNG.GN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_svng_gn_zs` |
| [World Bank WDI Adjusted net savings, excluding particulate emission damage (current US$) (NY.ADJ.SVNX.CD)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.SVNX.CD?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_svnx_cd` |
| [World Bank WDI Adjusted net savings, excluding particulate emission damage (% of GNI) (NY.ADJ.SVNX.GN.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.ADJ.SVNX.GN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_adj_svnx_gn_zs` |
| [World Bank WDI Coal rents (% of GDP) (NY.GDP.COAL.RT.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.GDP.COAL.RT.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_gdp_coal_rt_zs` |
| [World Bank WDI Forest rents (% of GDP) (NY.GDP.FRST.RT.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.GDP.FRST.RT.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_gdp_frst_rt_zs` |
| [World Bank WDI Mineral rents (% of GDP) (NY.GDP.MINR.RT.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MINR.RT.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_gdp_minr_rt_zs` |
| [World Bank WDI Natural gas rents (% of GDP) (NY.GDP.NGAS.RT.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.GDP.NGAS.RT.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_gdp_ngas_rt_zs` |
| [World Bank WDI Oil rents (% of GDP) (NY.GDP.PETR.RT.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PETR.RT.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_gdp_petr_rt_zs` |
| [World Bank WDI Total natural resources rents (% of GDP) (NY.GDP.TOTL.RT.ZS)](https://api.worldbank.org/v2/country/all/indicator/NY.GDP.TOTL.RT.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_ny_gdp_totl_rt_zs` |
| [World Bank WDI School enrollment, primary and secondary (gross), gender parity index (GPI) (SE.ENR.PRSC.FM.ZS)](https://api.worldbank.org/v2/country/all/indicator/SE.ENR.PRSC.FM.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_se_enr_prsc_fm_zs` |
| [World Bank WDI Primary completion rate, total (% of relevant age group) (SE.PRM.CMPT.ZS)](https://api.worldbank.org/v2/country/all/indicator/SE.PRM.CMPT.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_se_prm_cmpt_zs` |
| [World Bank WDI Mortality rate, under-5 (per 1,000 live births) (SH.DYN.MORT)](https://api.worldbank.org/v2/country/all/indicator/SH.DYN.MORT?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_dyn_mort` |
| [World Bank WDI People using at least basic drinking water services, rural (% of rural population) (SH.H2O.BASW.RU.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.H2O.BASW.RU.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_h2o_basw_ru_zs` |
| [World Bank WDI People using at least basic drinking water services, urban (% of urban population) (SH.H2O.BASW.UR.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.H2O.BASW.UR.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_h2o_basw_ur_zs` |
| [World Bank WDI People using at least basic drinking water services (% of population) (SH.H2O.BASW.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.H2O.BASW.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_h2o_basw_zs` |
| [World Bank WDI People using safely managed drinking water services, rural (% of rural population) (SH.H2O.SMDW.RU.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.H2O.SMDW.RU.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_h2o_smdw_ru_zs` |
| [World Bank WDI People using safely managed drinking water services, urban (% of urban population) (SH.H2O.SMDW.UR.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.H2O.SMDW.UR.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_h2o_smdw_ur_zs` |
| [World Bank WDI People using safely managed drinking water services (% of population) (SH.H2O.SMDW.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.H2O.SMDW.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_h2o_smdw_zs` |
| [World Bank WDI Community health workers (per 1,000 people) (SH.MED.CMHW.P3)](https://api.worldbank.org/v2/country/all/indicator/SH.MED.CMHW.P3?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_med_cmhw_p3` |
| [World Bank WDI Mortality rate attributed to household and ambient air pollution, age-standardized (per 100,000 population) (SH.STA.AIRP.P5)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.AIRP.P5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_airp_p5` |
| [World Bank WDI People using at least basic sanitation services, rural (% of rural population) (SH.STA.BASS.RU.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.BASS.RU.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_bass_ru_zs` |
| [World Bank WDI People using at least basic sanitation services, urban (% of urban population) (SH.STA.BASS.UR.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.BASS.UR.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_bass_ur_zs` |
| [World Bank WDI People using at least basic sanitation services (% of population) (SH.STA.BASS.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.BASS.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_bass_zs` |
| [World Bank WDI People with basic handwashing facilities including soap and water, rural (% of rural population) (SH.STA.HYGN.RU.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.HYGN.RU.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_hygn_ru_zs` |
| [World Bank WDI People with basic handwashing facilities including soap and water, urban (% of urban population) (SH.STA.HYGN.UR.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.HYGN.UR.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_hygn_ur_zs` |
| [World Bank WDI People with basic handwashing facilities including soap and water (% of population) (SH.STA.HYGN.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.HYGN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_hygn_zs` |
| [World Bank WDI Prevalence of underweight, weight for age (% of children under 5) (SH.STA.MALN.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.MALN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_maln_zs` |
| [World Bank WDI People practicing open defecation, rural (% of rural population) (SH.STA.ODFC.RU.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.ODFC.RU.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_odfc_ru_zs` |
| [World Bank WDI People practicing open defecation, urban (% of urban population) (SH.STA.ODFC.UR.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.ODFC.UR.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_odfc_ur_zs` |
| [World Bank WDI People practicing open defecation (% of population) (SH.STA.ODFC.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.ODFC.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_odfc_zs` |
| [World Bank WDI Mortality rate attributed to unintentional poisoning (per 100,000 population) (SH.STA.POIS.P5)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.POIS.P5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_pois_p5` |
| [World Bank WDI Mortality rate attributed to unintentional poisoning, female (per 100,000 female population) (SH.STA.POIS.P5.FE)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.POIS.P5.FE?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_pois_p5_fe` |
| [World Bank WDI Mortality rate attributed to unintentional poisoning, male (per 100,000 male population) (SH.STA.POIS.P5.MA)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.POIS.P5.MA?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_pois_p5_ma` |
| [World Bank WDI People using safely managed sanitation services, rural (% of rural population) (SH.STA.SMSS.RU.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.SMSS.RU.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_smss_ru_zs` |
| [World Bank WDI People using safely managed sanitation services, urban (% of urban population) (SH.STA.SMSS.UR.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.SMSS.UR.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_smss_ur_zs` |
| [World Bank WDI People using safely managed sanitation services (% of population) (SH.STA.SMSS.ZS)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.SMSS.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_smss_zs` |
| [World Bank WDI Mortality rate attributed to unsafe water, unsafe sanitation and lack of hygiene (per 100,000 population) (SH.STA.WASH.P5)](https://api.worldbank.org/v2/country/all/indicator/SH.STA.WASH.P5?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sh_sta_wash_p5` |
| [World Bank WDI Poverty headcount ratio at $3.00 a day (2021 PPP) (% of population) (SI.POV.DDAY)](https://api.worldbank.org/v2/country/all/indicator/SI.POV.DDAY?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_si_pov_dday` |
| [World Bank WDI Population growth (annual %) (SP.POP.GROW)](https://api.worldbank.org/v2/country/all/indicator/SP.POP.GROW?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sp_pop_grow` |
| [World Bank WDI Population, total (SP.POP.TOTL)](https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sp_pop_totl` |
| [World Bank WDI Urban population growth (annual %) (SP.URB.GROW)](https://api.worldbank.org/v2/country/all/indicator/SP.URB.GROW?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sp_urb_grow` |
| [World Bank WDI Urban population (SP.URB.TOTL)](https://api.worldbank.org/v2/country/all/indicator/SP.URB.TOTL?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sp_urb_totl` |
| [World Bank WDI Urban population (% of total population) (SP.URB.TOTL.IN.ZS)](https://api.worldbank.org/v2/country/all/indicator/SP.URB.TOTL.IN.ZS?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_sp_urb_totl_in_zs` |
| [World Bank WDI Fuel imports (% of merchandise imports) (TM.VAL.FUEL.ZS.UN)](https://api.worldbank.org/v2/country/all/indicator/TM.VAL.FUEL.ZS.UN?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_tm_val_fuel_zs_un` |
| [World Bank WDI ICT goods imports (% total goods imports) (TM.VAL.ICTG.ZS.UN)](https://api.worldbank.org/v2/country/all/indicator/TM.VAL.ICTG.ZS.UN?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_tm_val_ictg_zs_un` |
| [World Bank WDI Ores and metals imports (% of merchandise imports) (TM.VAL.MMTL.ZS.UN)](https://api.worldbank.org/v2/country/all/indicator/TM.VAL.MMTL.ZS.UN?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_tm_val_mmtl_zs_un` |
| [World Bank WDI Fuel exports (% of merchandise exports) (TX.VAL.FUEL.ZS.UN)](https://api.worldbank.org/v2/country/all/indicator/TX.VAL.FUEL.ZS.UN?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_tx_val_fuel_zs_un` |
| [World Bank WDI ICT goods exports (% of total goods exports) (TX.VAL.ICTG.ZS.UN)](https://api.worldbank.org/v2/country/all/indicator/TX.VAL.ICTG.ZS.UN?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_tx_val_ictg_zs_un` |
| [World Bank WDI Ores and metals exports (% of merchandise exports) (TX.VAL.MMTL.ZS.UN)](https://api.worldbank.org/v2/country/all/indicator/TX.VAL.MMTL.ZS.UN?format=json&date=1990:2026) | 7. World energy and climate indicators | World | country | CC BY 4.0 (World Bank WDI) | 9,576 | `wave10.wb_tx_val_mmtl_zs_un` |
<!-- wave10:end -->

## Weekly brief (`scripts/weekly_brief.py`, `brief/latest.json`, `brief/latest.html`)

Built weekly by `.github/workflows/weekly-brief.yml` (spec: docs/product/weekly-brief.md), from
fixed templates (the `TEMPLATES` table in the script, also in the JSON) with no language model and
no new source. It reads the app's own files: the day archive (`eu-days` branch `eu/day/`),
`prices.json` (eu-days), `outages.json` (eu-data), and the bundled `us/queues_live.json`,
`us/plants.json` and `eu/plants.json`. Each sentence carries its source, the file's URL and that
file's "as of" date.

| Figure | Rule |
|---|---|
| Weekly mean day-ahead price per zone | mean of the 15-minute prices of the newest 7 archive days (computed), against the 7 days before; only zones with prices in at least 95 % of the slots of both weeks; the two weeks must be consecutive, else the section is skipped |
| Week's highest / lowest price | the largest / smallest 15-minute price of the 7 days, passed through; a zone is named when it exceeds the max (or undercuts the min) of `prices.json` for its 12-month `period` |
| Solar, wind, load records | the day files' `highlights` (scripts/day_highlights.py: EU sums of the member states reporting), the week's largest against all archive days |
| Plants offline | `outages.json` `total` and the three largest `countries`, passed through; compared with the previous brief's stored figure (`carry`) |
| US queues | `queues_live.json` `active` and `active_mw` per market, passed through; compared with the previous brief when the queue's `read` date changed |
| Capacity added | US: sum of EIA-860M `points` with status operating whose year (earliest operating year of the plant's fuel group) is the release year; Europe: count and sum of powerplantmatching units >= 20 MW by commissioning year, newest year and the one before |

## Download centre index (`scripts/build_downloads.py`, `downloads.json`)

Per dataset of the Layers panel (`app/datasets.json`, `wave9.json`, `wave10.json`): its files
(the paths `frontend/src/app/data.ts` loads, the live copy on `eu-data`/`eu-days`, public R2
tiles), lake table names from `agent/catalog/*.yaml`, and per file the licence (the file's own
`licence`, else the table in the script as this document or the catalogue states it, else the
licence named in the file's `source`), the attribution (the file's `source`) and the "as of"
date (the file's `as_of`, `fetched`, `at`, `date`, `release` or `edition`). The page
`?downloads` (`frontend/src/ui/Downloads.tsx`) links a file only when every part of its
licence is on its allowlist; Global Energy Monitor files stay view only by project rule.
Spec: docs/product/download-centre.md.
