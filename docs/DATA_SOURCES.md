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

## LNG send-out (`scripts/fetch_eu_dossier.py`, in `dossier.json`)

GIE ALSI (same key as AGSI+), daily for the EU and the 12 countries with terminals (BE,
DE, ES, FI, FR, GR, HR, IT, LT, NL, PL, PT), last ~400 days, passthrough:
- `sendOut`: LNG regasified into the grid, GWh/day
- `dtrs`: declared total reference send-out, the terminals' declared send-out
  capacity, GWh/day
- `inventory.gwh`: LNG in tanks

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

## Notes

- ENTSO-E allows 400 requests a minute; the scripts ask four at a time. A full snapshot
  (~270 requests) took about a minute on 2026-10-05; single answers range from 0.3 s
  to 50 s.
- Energy-Charts answers 429 to bursts. `scripts/fetch_eu_reference.py` still asks it
  one request at a time for installed capacity.
