# 28. Wave 9: what customers need, in every category, for every EU-27 country, the UK and the US

## Goal

A big data wave in one run, in three parts:

- **A. Finish wave 8.** Build the sources brief 27 found but did not load, and retry the blocked
  ones with the official routes named below.
- **B. Wave 9.** New datasets in 17 categories chosen by what the atlas's customers ask.
  Customers include developers, data-centre builders, grid planners, traders, lenders, insurers,
  industrial buyers and municipal planners. Every category has its EU, UK and US sources,
  with the same consistency rule as brief 27.
- **C. Customer views.** Turn the data into answers people buy. One dashboard preset and one
  agent skill per customer task (data-centre siting, battery siting, offshore wind, physical
  risk, revenues...). These use the existing Layers panel, context panel and Ask chat; no new
  panels.

**Search beyond the seed lists.** The tables below are a start, not the limit. For each
category, look for more sources on these portals:

- data.europa.eu, data.gov, data.gov.uk and the national portals
- the regulators and grid operators
- Zenodo, Figshare and Mendeley Data
- Copernicus, NASA and USGS
- open-energy collections (Open Energy Platform, Open Power System Data, PUDL, the
  openmod list)
- the data pages behind peer platforms

Add every source that fits the rules. Target: **at least 100 datasets probed and at least 60
built**. Record each one's status in the registry.

## Read first

- `vault/index.md`, `vault/data/coverage-and-gaps.md`, `vault/data/lake.md`,
  `vault/backend/agent-tools.md` (areas: `resolve_area`, `in_area`, `area_stats`, the level
  matrix `agent/areas/levels.yaml`), `vault/frontend/state-and-datasets.md` (dashboards),
  `vault/gotchas.md` (wave 8 lessons).
- `docs/tasks/27-any-area-wave8.md` (the consistency rule, the level ladder, the rules for
  areas), PR #17's description (what was built and blocked), `docs/research/small-area-energy.md`,
  `data/coverage.yaml`, `.github/workflows/wave8.yml` (the pattern for heavy builds in Actions).

## How to work

- **Token budget.** Use the skills: `.claude/skills/caveman` (level full) for chat;
  `.claude/skills/atlas-vault` (vault first, read only what a step needs, never re-read a file);
  `.claude/skills/obsidian-markdown` for the vault notes. Keep probe output short in chat: the
  licence line, size, rows and timing. Full output goes into the PR.
- One commit per category or source family. Ruff, `uv run pytest`, `cd backend && uv run pytest`
  and `cd frontend && npm run build` must be green at every commit.
- **Probe before building**, state each download's size before starting it, and run heavy
  builds in GitHub Actions (a `wave9.yml` like `wave8.yml`, groups per category). Outputs go to
  R2 (`lake/` Parquet and GeoParquet, COG, PMTiles), never git.
- **Do not stop between categories.** When a source is blocked, record it in its registry cell
  and in the PR with the reason and a data-request text, then move on. Blocked means: licence
  unclear or non-commercial, key missing, login, closed, or HTTP 451/403 to honest clients.
- Same access rules as briefs 26 and 27: an honest client name; never bypass refusals, logins,
  terms or deliberate encoding; respect CEII.
- Do not change the GISCO country and NUTS shapes the app uses. The owner is deciding about
  their licence.

## The rules every dataset follows

1. **Consistency across the 29 places.** Every category becomes one or more families in
   `data/coverage.yaml`. Each family has a cell for each of the 27 member states, GB and US,
   and no blank cell at the end. Use the level ladder of brief 27. A pan-European source comes
   first, national sources fill the gaps below it, and the UK and US equivalents sit in the
   same family.
2. **Sourced values only** (hard rule 1). Values are passthrough or computed in a build script
   with the method stated. Never estimate. **No composite "site scores"**: a customer view
   shows each criterion with its own source; it never ranks sites by a made-up weighting.
3. **Licence fit for a paid product.** Leave out non-commercial sources (CC BY-NC, "research
   only") and say why. Excluded so far: Net Zero Tracker (CC BY-NC 4.0 since 2024-12-02),
   TZ-SAM, GADM, WDPA, Renewables.ninja, EM-DAT, ESWD, TeleGeography's cable map, parcels.
4. **Agent-ready.** Each dataset needs:
   - a lake table: GeoParquet with a `bbox` column, Hilbert-sorted, and the metadata of
     DATA_LAKE section 4;
   - a catalogue YAML entry whose examples were run;
   - a row in `agent/areas/levels.yaml`.

   It must work with `in_area` and, for rasters, `area_stats`. A dataset on the map is a layer
   in the existing Layers panel, grouped by category, with its key and source, plus a
   `datasets.json` entry with coverage.

## Who the customers are and what they ask

| Customer | Questions they pay to answer | Categories |
|---|---|---|
| Solar, wind and battery developers | Where can I connect, how much land is free of constraints, what earns most, how long is the queue? | 1, 2, 3, 4, 9 |
| Data-centre and large-load developers | Where is power available soonest? Then fibre, water, land, permitting, incentives, in that order ([LBNL/DOE siting webinar](https://eta-publications.lbl.gov/sites/default/files/2026-10/eif_webinar_siting_v2.pdf), [datacentres.com scorecard](https://www.datacentres.com/news/the-ten-factor-site-selection-scorecard-how-developers-rank-power-land-and-commu-slot3-2026-09-01)) | 2, 5, 10, 11, 1, 8 |
| Grid operators and planners | Where is demand growing, what is planned, where are the constraints? | 2, 5, 12, 13 |
| Traders and storage operators | Balancing and capacity prices, congestion, curtailment, fleet build-out | 3, 2 |
| Lenders, investors, insurers | Exposure of assets to heat, drought, wildfire, flood, sea level and earthquakes; public money; ownership ([Morgan Stanley](https://www.morganstanley.com/content/dam/im/assets/publication/thought-leadership/article/article_mappingawarmingworld_a4.pdf), [ICF ClimateSight](https://netzerocompare.com/software/icf-climatesight-energy-risk-tool)) | 4, 8, 7 |
| Offshore wind developers | Depth, seabed, shipping, zones, ports | 6 |
| Industrial energy buyers, hydrogen, CCS | Clusters, heat, water, CO₂ storage, tariffs | 7, 11, 12, 2 |
| Municipal and heat-network planners, EV operators | Heat demand and sources, building stock, EV uptake, charging gaps | 5, 12, 13, 9 |
| Journalists, policy, researchers | Who owns what, who pays, how fair the transition is | 8, 9, 14 |

## Part A: finish wave 8

| Family | Places | Source (route to try) |
|---|---|---|
| Consumption per small area | BE | Fluvius open data (per municipality and statistical sector), Sibelga, ORES, RESA |
| | DE | Destatis regional statistics table 43531 (industry energy use per district, dl-de/by-2-0) |
| | IT | Terna's yearly statistics: consumption per province (find the xlsx; else record it as PDF-only) |
| | MT | NSO non-residential consumption per district |
| | others | the leads in `docs/research/small-area-energy.md`; one more search pass per dark country |
| Heating fuel per small area | DE | Zensus 2022 heating type per municipality and 100 m cell (dl-de/by-2-0) |
| | IE | CSO census small-area statistics, central heating (CC BY 4.0) |
| | US | ACS B25040 per tract (needs `CENSUS_API_KEY`) |
| National small-area outlines | the 22 member states marked "partial" | census small areas: IT ISTAT sezioni di censimento, ES INE secciones censales, PT INE BGRI, AT Statistik Austria Zählsprengel, CZ ČSÚ ZSJ, DK DAGI, FI Paavo postal areas, DE Zensus 100 m grid, PL, others by research |
| Flood zones | GB | Environment Agency Flood Map for Planning (OGL), SEPA, Natural Resources Wales, DfI Northern Ireland |
| | US | FEMA NFHL (5.8 M zones): PMTiles plus reading the service in place for small areas |
| Oil and gas facilities | US | EIA's layer downloads page (eia.gov/maps/layer_info-m.php) in place of the token-gated services |
| | GB | the NSTA open-data hub (search ArcGIS Hub for the NSTA organisation; pipelines, surface infrastructure, wells) |
| CO₂ storage | US | NATCARB (NETL EDX), EPA Class VI permits (find the moved tracker) |
| Fires | all | FIRMS once `FIRMS_MAP_KEY` is set (run the group); EFFIS by data request |

## Part B: wave 9 by category (seeds; search for more)

"(check)" means the licence must be confirmed by a probe. "(research)" means no seed was found
for that region: find one, or record `not_published` with evidence.

### 1. Land, permitting and planning

| Topic | EU-27 | UK | US |
|---|---|---|---|
| Renewables acceleration areas and zoning | RED III Art. 15b mapping and 15c designations per member state (research per country; most were not designated at the Feb 2026 deadline: [CAN Europe tracker](https://caneurope.org/acceleration-areas-progress)); DE wind areas of the Länder regional plans | Scotland NPF4 areas; England and Wales (research) | BLM solar designated leasing areas (Western Solar Plan) and wind areas; DOE NIETC corridors |
| Agricultural land quality | ESDAC (check: registration) | Natural England Agricultural Land Classification (OGL); Scotland, Wales (research) | USDA prime farmland (gNATSGO/SSURGO, public domain) |
| Brownfield and contaminated land | FR Géorisques sites et sols pollués (Licence Ouverte); others (research) | brownfield land registers on planning.data.gov.uk (OGL) | EPA RE-Powering America's Land screened sites; EPA Cleanups (public domain) |
| Land prices | Eurostat agricultural land prices and rents (`apri_lprc`, NUTS 2) | (research) | USDA NASS land values per state |
| Heritage and aviation constraints | UNESCO World Heritage (check); airports (OurAirports, public domain) | Historic England listed sites (OGL); airports | NRHP (public domain); FAA obstruction determinations; NEXRAD radar sites |
| Major energy consents | national permit registers (research) | Planning Inspectorate DCO register (OGL) | FERC hydro licences, EIA-860M planned units (have) |

### 2. Grid planning, connection and network charges

| Topic | EU-27 | UK | US |
|---|---|---|---|
| Planned grid by national plan | DE NEP/BBPlG projects (BNetzA Netzausbau, check), FR RTE SDDR, ES planning 2025-2030, others (research) | NESO ETYS, HND and the 2025-26 connections reform (Gate 2) outcomes | MISO MTEP, SPP ITP, PJM RTEP, ERCOT RPG, CAISO TPP project lists |
| Locational network charges | ENTSO-E overview of transmission tariffs (per country) | NESO TNUoS tariffs per generation and demand zone | OpenEI Utility Rate Database (check CC0; `NREL_API_KEY`) |
| Large-load (data-centre) queues | NL congestion offtake (have), IE EirGrid and CSO data-centre consumption (CC BY 4.0), others (research) | TEC demand entries (have) | ERCOT large-load interconnection updates (research the machine-readable form), PJM load forecast |
| Curtailment and constraint costs | DE (have); ES, IT, FR, NL, IE (research) | NESO constraint costs | CAISO curtailment; ERCOT (research) |
| Distribution network data | (research per DSO) | DNO open-data portals (NGED, SSEN, Northern Powergrid; UKPN, ENWL, SPEN need keys) | utility hosting-capacity maps (brief 26) |

### 3. Markets and revenues

| Topic | EU-27 | UK | US |
|---|---|---|---|
| Balancing and reserves (FCR, aFRR, mFRR) | ENTSO-E balancing documents (A81-A89, `ENTSOE_API_KEY`) for every country; national CC BY sets (Svenska kraftnät, Fingrid, Energinet); regelleistung.net (check) | Elexon Insights (check the licence) | ISO ancillary-service prices (gridstatus) |
| Capacity markets | IT, PL, BE, IE CRM auction results (research) | EMR Capacity Market register and auction results | PJM RPM, MISO PRA, ISO-NE FCA, NYISO ICAP results |
| Support schemes and contracts | national auction results (have, AURES) | LCCC CfD register (allocation rounds, strike prices, generation) | (research: state RPS solicitations) |
| Guarantees of origin | AIB issuance and cancellation statistics per country | REGO statistics (Ofgem) | (research) |
| Storage fleet | MaStR (DE, have), Terna storage requests (have), others (research) | REPD batteries (have) | EIA-860M batteries (have) |

### 4. Physical climate and hazard risk

| Hazard | EU-27 | UK | US |
|---|---|---|---|
| Earthquake | ESHM20 ([EFEHR](https://efehr.org/earthquake-hazard/data-access), CC BY 4.0) | ESHM20 | USGS NSHM 2023 |
| Heat | Copernicus CDS climate indicators (CC BY 4.0; `CDSAPI_KEY`) or NEX-GDDP-CMIP6 on AWS, read in place: days above 35 °C per period and scenario, computed and labelled | same | same |
| Drought | European Drought Observatory (check) | (research) | US Drought Monitor (weekly polygons) |
| Wildfire hazard | EFFIS fire danger (check), JRC wildfire hazard (research) | (research) | USFS Wildfire Risk to Communities / Wildfire Hazard Potential |
| Coastal flood and sea level | JRC coastal flood hazard (check) | Environment Agency (Part A) | NOAA sea level rise data |
| Landslides | ELSUS (check: registration) | (research; BGS GeoSure is licensed) | USGS landslide inventory and susceptibility |
| Storms | (research) | (research) | NOAA Storm Events |
| Geomagnetic storms (transformer risk) | (research) | (research) | USGS geoelectric hazard maps |
| Ground motion and subsidence | EGMS (check: login) | EGMS | (research) |

### 5. Demand and electrification

| Topic | EU-27 | UK | US |
|---|---|---|---|
| EV registrations per area | FR Agence ORE per commune and charging type, NL RDW (CC0), DE KBA per district (check), others (research); EAFO per country (check) | DfT VEH0142/VEH0135 per LSOA and LA (OGL) | AFDC registrations per state |
| Heat pumps per area | (research per country) | MCS installations per LA (check) | ACS heating fuel (Part A) |
| Rooftop solar per area | MaStR (have), Agence ORE production per commune, CBS solar per municipality, others (research) | DESNZ sub-regional FiT and MCS statistics | LBNL Tracking the Sun |
| Building energy certificates | FR ADEME DPE (Licence Ouverte), IE SEAI BER (check), NL EP-online (key), others (research) | EPC statistics per LA (OGL; address-level records need a licence: aggregates only) | city benchmarking (NYC LL84, Chicago, DC, Boston..., public) |
| Data centres | EED Art. 12 aggregates per country (Commission, [COM(2026) 500](https://www.cdep.ro/afaceri_europene/CE/2026/COM_2026_500_EN_ACT_part1_v4.pdf)); IE CSO data-centre electricity | (research) | (research: state reports) |
| Degree days | Eurostat `nrg_chdd` (NUTS 3) | Met Office HadUK-Grid (OGL, check) | NOAA CPC degree days per state |

### 6. Offshore and maritime

| Topic | EU-27 and UK | US |
|---|---|---|
| Depth | EMODnet bathymetry DTM (check), GEBCO grid (public domain) | NOAA bathymetry; GEBCO |
| Shipping | EMODnet vessel density (CC BY 4.0) | MarineCadastre.gov AIS vessel transit counts |
| Zones and leases | EMODnet maritime spatial planning; Crown Estate and Crown Estate Scotland leasing rounds (check) | BOEM wind energy areas and lease areas |
| Seabed | EMODnet geology, seabed substrate (CC BY 4.0) | USGS usSEABED |
| Ports | World Port Index (NGA, public domain) | same |
| Marine protected areas | Natura 2000 marine (have) | NOAA MPA inventory |

### 7. Supply chain, materials and industry

| Topic | EU-27 | UK | US |
|---|---|---|---|
| Clean-tech factories (batteries, solar, wind, electrolysers) | (research: national and EU trackers with an open licence) | (research) | Clean Investment Monitor (Rhodium/MIT, check) |
| Critical minerals | EGDI / Minerals4EU deposits (check) | BGS (check) | USGS MRDS, USGS critical mineral deposits |
| Biogas, biomethane, landfill gas | EBA map (check), national registers (research) | REPD (have) | EPA LMOP, EPA AgSTAR digesters |
| Hydrogen storage potential | salt-cavern potential (Caglayan et al. 2020, check) | same | (research) |

### 8. Finance, public money and incentives

| Topic | EU-27 | UK | US |
|---|---|---|---|
| Public grants and loans | Kohesio (cohesion projects with positions), CINEA Innovation Fund and CEF Energy data hubs (raw export, check), EIB projects (check), state aid transparency awards (check) | National Wealth Fund investments (research) | USAspending.gov awards (DOE), DOE LPO portfolio |
| Tax-credit and transition areas | Just Transition Fund territories, JRC coal regions | (research: freeports, investment zones) | NETL IRA energy communities ([EDX](https://edx.netl.doe.gov/dataset/ira-energy-community-data-layers)), CDFI NMTC low-income tracts, Opportunity Zones |
| Ownership | GEM (have) | same | same |

### 9. Social and community

| Topic | EU-27 | UK | US |
|---|---|---|---|
| Income per area | Eurostat household income (NUTS 2) | ONS income estimates (MSOA) | ACS median income per tract (`CENSUS_API_KEY`) |
| Community energy | REScoop members (check), national registers (research) | (research) | NREL Sharing the Sun (community solar) |
| Buildings near a site | Overture buildings read in place for small areas (count inside; ODbL) | same | same |

### 10. Telecom and digital

| Topic | EU-27 and UK | US |
|---|---|---|
| Exchange points and colocation sites | PeeringDB (facility positions; check the terms) | same |
| Broadband coverage | Commission "Broadband coverage in Europe" study (NUTS 3, check); Ofcom Connected Nations (OGL) | FCC National Broadband Map (H3 hexagons, public) |

### 11. Water and cooling

| Topic | EU-27 | UK | US |
|---|---|---|---|
| Water use and stress | EEA water exploitation index per river basin (CC BY 4.0); Aqueduct (have) | Environment Agency abstraction licences (check) | USGS water use per county |
| Wastewater plants (heat, reuse, water for electrolysis) | EEA UWWTD (CC BY 4.0) | (check: UWWTD to 2020; national) | EPA CWNS / ECHO facilities |
| River discharge | GloFAS (`CDSAPI_KEY`) | same | USGS NWIS |

### 12. Heat networks and geothermal

| Topic | EU-27 | UK | US |
|---|---|---|---|
| District heating areas | DK, SE, FI, DE municipal heat plans (research); Hotmaps potential (have) | DESNZ heat network zoning maps (check) | (research) |
| Geothermal heat flow | IHFC Global Heat Flow Database (CC BY 4.0); EGDI (check) | same | SMU geothermal (check) |
| Pumped hydro potential | ANU RE100 atlas (check: attribution "Pumped hydro site data: RE100 Group ANU") | same | same |

### 13. Mobility

| Topic | EU-27 | UK | US |
|---|---|---|---|
| Freight and charging corridors | TEN-T network (TENtec) | National Highways Strategic Road Network (OGL) | FHWA Alternative Fuel Corridors, National Highway Freight Network |
| Rail electrification | Overture rail with its electrified attribute | same | same |
| Airports | OurAirports | same | same |

### 14. Nuclear

| Topic | EU-27 | UK | US |
|---|---|---|---|
| Reactors and new-build | IAEA PRIS (check); GEM (have) | ONR licensed sites (research) | NRC operating reactors and advanced-reactor applications |

### 15. Air quality near plants

| Topic | EU-27 | UK | US |
|---|---|---|---|
| Measured air quality | EEA air quality statistics per station (CC BY 4.0) | DEFRA AURN (OGL) | EPA AQS annual summaries |

### 16. Reliability below the country

| Topic | EU-27 | UK | US |
|---|---|---|---|
| Interruptions per area | FR Enedis per department (Licence Ouverte), others (research) | Ofgem RIIO-ED2 interruptions per DNO (check) | EIA-861 reliability per utility (SAIDI, SAIFI) |

### 17. Night lights and activity

| Topic | All |
|---|---|
| Night lights (electrification, outages after disasters) | NASA Black Marble (`NASA_EARTHDATA_TOKEN`) |

## Part C: customer views

- **Dashboards** (the existing `DASHBOARDS` in `store.ts`, no new panels): one preset per task.
  Each sets the layers, the area and the camera, and has a blurb saying what it answers:
  - Data-centre siting
  - Battery storage siting
  - Solar and wind siting
  - Offshore wind
  - Physical risk to grid assets
  - Grid planning
  - Balancing and capacity revenues
  - Industrial decarbonisation (heat, CO₂, hydrogen)
  - Heat networks
  - EV and electrification
  - Public money and incentives
- **Agent skills** (`agent/skills/<name>/SKILL.md`), one per task. Each is a checklist that
  runs in order: power first for data centres, then fibre, water, land, permitting and
  incentives. Each criterion names the datasets and SQL patterns to use, how to report a
  missing source, and that there is no composite score.
- **Evals:** at least 30 new cases across the categories, with answers from the built tables.
- **Layers panel:** with many more datasets, group the rows by category (the existing panel and
  row style: name and an ON/OFF switch, details on click) and add a filter box at the top of the
  panel.

## Keys (document each in `.env.example`; scripts skip and say so when missing)

| Key | Where | For |
|---|---|---|
| `FIRMS_MAP_KEY` | https://firms.modaps.eosdis.nasa.gov/api/map_key/ | fires |
| `CENSUS_API_KEY` | https://api.census.gov/data/key_signup.html | ACS heating fuel, income |
| `NREL_API_KEY` | https://developer.nrel.gov/signup/ | Utility Rate Database, AFDC |
| `CDSAPI_KEY` | https://cds.climate.copernicus.eu (free account) | climate indicators, GloFAS |
| `NASA_EARTHDATA_TOKEN` | https://urs.earthdata.nasa.gov | Black Marble |
| `FINGRID_API_KEY` | https://data.fingrid.fi | Finnish reserves |

## Sizes

Probe each, and state the size in chat and in the PR before downloading. The largest are
expected to be:

- FEMA NFHL and FCC broadband: read in place or build PMTiles in Actions.
- SSURGO/gNATSGO: use the farmland class raster only.
- Climate projections: read in place, keeping only computed indicators.
- Overture buildings: read in place, never copied.
- EMODnet bathymetry: a COG.

## Deliverables

- Part A cells built or re-recorded with new evidence.
- Part B: the datasets in the lake and on the map, catalogue entries, `levels.yaml` rows,
  registry families with 29 cells each, rows in `docs/DATA_SOURCES.md` and
  `docs/DATA_LAKE.md`, and `docs/DATASETS.md` (wave 9 marked built or blocked).
- Part C: dashboards, skills, evals, the grouped Layers panel.
- `docs/research/wave9-sources.md`: every source probed (category, places, level, licence
  quote, size, status, link, checked date), including the ones found beyond the seeds.
- Vault notes updated, `vault/log.md`.

## Done-check

- At least 100 sources probed and at least 60 built; the PR has a table per category with 29
  columns (built / partial / not published / blocked).
- `scripts/coverage.py` passes with no blank cell.
- Each dashboard opens with its layers and area; each skill runs one eval with the fake model.
- `uv run ruff check . && uv run ruff format .`, `uv run pytest`, `cd backend && uv run pytest`,
  `cd frontend && npm run build`.

## Out of scope

- Estimates and composite scores.
- Non-commercial or licensed sources, logins.
- New floating panels.
- Changing the GISCO shapes (owner decision pending).
