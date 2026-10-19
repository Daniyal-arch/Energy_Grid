# Dataset catalogue: Europe, United States, world

What the atlas could add, at two levels: **broad** (country, region, market; yearly to
hourly) and **granular** (asset, node, county; hourly or finer). Each row: what it gives,
access, licence, and why it matters for the product. Status: **have** (on the map), **wave 2**
(briefs 06–08 in `docs/tasks/`), **candidate**. Licences must allow a paid product: rows
marked *NC* (non-commercial) are for research views only, or need a licence.

Researched 2026-10-11. Check each source's terms again before building (rule 2: probe first).

## Europe

### Broad

| Dataset | Gives | Access | Licence | Why | Status |
|---|---|---|---|---|---|
| Eurostat energy balances (`nrg_bal_*`) | supply, transformation, final use by sector and fuel, yearly | API, no key | CC BY 4.0 | country profiles beyond power: heat, transport, industry | have (17) |
| Eurostat retail prices (`nrg_pc_204/205`, gas `nrg_pc_202/203`) | household and business electricity and gas prices by band, half-yearly | API, no key | CC BY 4.0 | "what consumers pay" next to wholesale | have (13) |
| EEA greenhouse-gas inventories | national emissions by sector, yearly | download | CC BY 4.0 | context for the transition tab | candidate |
| ACER market monitoring data | cross-border capacity use, convergence, retail | reports/xlsx | reuse with attribution | explains price splits | candidate |
| ENTSO-E TYNDP projects | planned transmission and storage projects, cost, dates | download (xlsx, shapes) | ENTSO-E terms | "what grid is coming" layer | have (17) |
| ENTSOG TYNDP | planned gas infrastructure | download | ENTSOG terms | gas future layer | candidate |
| AURES II / national auction results | renewable auction rounds, prices, winners | download | open (check) | price trend of new capacity | candidate |
| EU Hydrogen Observatory | electrolysers, H₂ projects, costs | download | check | hydrogen layer | candidate |
| Ember monthly/yearly, IRENA, GEM | generation, capacity, assets | API/download | CC BY 4.0 | | have |

### Granular

| Dataset | Gives | Access | Licence | Why | Status |
|---|---|---|---|---|---|
| ENTSO-E imbalance prices and volumes (A85/A86), balancing reserves | 15-min balancing prices per area | API (`ENTSOE_API_KEY`) | ENTSO-E terms | trader view, volatility | brief 16 (in progress) |
| ENTSO-E transmission outages (A78/A79), redispatch | planned and forced line outages | API | ENTSO-E terms | why flows/prices change | have (17) |
| ENTSO-E output per unit (A73), installed per unit (A71) | plants hour by hour | API | ENTSO-E terms | | have |
| **Germany MaStR** (Marktstammdatenregister) | every generating unit, storage, grid connection point (8 M+ records), daily dump | bulk XML + SOAP API (`open-mastr`) | dl-de/by-2-0 (check) | the most complete national asset register in Europe | have (11) |
| Germany SMARD (Bundesnetzagentur) | market data, generation, consumption, 15 min | API, no key | CC BY 4.0 | German detail beyond ENTSO-E | have (17) |
| Germany netztransparenz.de | redispatch, curtailment (EinsMan), EEG data | download | check | curtailment = wasted renewables | have (17) |
| France RTE éCO2mix | 15-min mix, CO₂ intensity, exchanges, regional | API (data.rte-france.com, free key) | Etalab open licence | regional France | candidate |
| Spain REE REData | real-time mix, regional, prices | API, no key | open, attribution | regional Spain | candidate |
| **Spain grid access capacity per node** (REE / CNMC, monthly) | free capacity for generation and demand at each transmission node | published maps/tables (check format) | public | **site screening**: where can a new plant or data centre connect | have (09) |
| **Netherlands capaciteitskaart** (Netbeheer Nederland) | grid congestion for feed-in and offtake by area, TenneT HV layer | data export (+ Liander WFS via PDOK) | check | **site screening**; NL is Europe's most congested grid | have (09) |
| **GB NESO TEC register** | every project holding transmission capacity, twice weekly | CKAN API, no key | NESO Open Data Licence | GB connection queue (like LBNL's) | have (09) |
| GB NESO embedded register, carbon intensity API | distribution-connected projects; regional CO₂ forecast | API | NESO OD / CC BY | | carbon intensity: brief 16; embedded register candidate |
| Denmark Energinet Energi Data Service | 5-min production, CO₂, prices | API, no key | CC BY 4.0 | | brief 16 |
| Finland Fingrid open data | 3-min data | API (free `FINGRID_API_KEY`) | CC BY 4.0 | | candidate |
| Belgium Elia open data | 15-min load, solar/wind incl. forecasts, balancing | API | Elia open data | | candidate |
| EMODnet human activities | offshore wind farms (polygons, status), cables, pipelines | WFS/download | CC BY 4.0 | offshore layer | wind farms on the map (2026-10-17); cables, pipelines candidate |
| EU ETS / EEA industrial emissions; GIE ALSI | CO₂ per installation; LNG per terminal | | | | wave 2 (08) |
| EV charging: national registers (DE Ladesäulenregister), EAFO | charge points with power | download | varies | demand-side layer | candidate |

## United States

### Broad

| Dataset | Gives | Access | Licence | Why | Status |
|---|---|---|---|---|---|
| EIA-861 / 861M | retail sales, revenue, customers, price by utility and state | download / API | public domain | "what Americans pay" by state | have (13) |
| EIA SEDS | state energy production, consumption, prices, all fuels, yearly | API | public domain | state profiles | have (17) |
| EIA STEO / AEO | short-term and long-term outlooks | API | public domain | forecasts beside history | have (17) |
| NREL ATB | technology costs and projections | download | CC BY 4.0 | cost context | candidate |
| LBNL utility-scale solar / wind market reports | PPA prices, capacity factors, costs by project vintage | xlsx | public | price of new capacity | candidate |
| EIA-860M, LBNL queue, USWTDB, EIA-930 | | | | | have |

### Granular

| Dataset | Gives | Access | Licence | Why | Status |
|---|---|---|---|---|---|
| **ISO nodal prices and queues via `gridstatus`** | LMPs at every node (5-min/hourly), load, fuel mix, each ISO's live interconnection queue | open-source Python library over the ISOs' public APIs (some need free keys) | library MIT; data per ISO | nodal price heat map; queues fresher than LBNL's yearly file | have (10; PJM waits for its key, NYISO queue bot-blocked) |
| EIA-923 | generation and fuel per plant, monthly | download / API | public domain | capacity factor per plant | have (17) |
| EPA eGRID | emissions and rates per plant, yearly | download | public domain | CO₂ intensity per plant | have (17) |
| EPA GHGRP (FLIGHT) | GHG per large facility, all sectors, yearly | API/download | public domain | industry emitters | have (17) |
| PUDL (Catalyst Cooperative) | cleaned, joined EIA 860/923/930, FERC 1/714, EPA CEMS | nightly builds on AWS, Zenodo | open (check terms) | saves building every join ourselves | have (17, queried in place) |
| **EAGLE-I power outages** (ORNL) | customers out per county every 15 min, 2014– | figshare / ORNL | open (check) | outage map, storms | have (12) |
| DOE OE-417 | major disturbances and incidents | download | public domain | reliability events | candidate |
| NREL AFDC station locator | every EV charger, power, network | API (free `NREL_API_KEY`) | public | demand-side layer | brief 16 |
| OpenEI Utility Rate Database | retail tariffs per utility | API | open | tariff explorer (product) | candidate |
| USGS USPVDB | utility solar farms as polygons | download | public domain | solar footprint | have (2026-10-17) |
| EIA natural gas pipelines, LNG terminals, Henry Hub | gas network and prices | download/API | public domain | US gas layer | candidate |
| EPA CAMPD, ISO hub prices | | | | | have |

## World

### Broad

| Dataset | Gives | Access | Licence | Why | Status |
|---|---|---|---|---|---|
| Energy Institute Statistical Review | energy and emissions by country and fuel, 1965– | xlsx | free with attribution | long history for every country | have (17, fetched with a browser) |
| Our World in Data energy | merged indicators per country | CSV/GitHub | CC BY 4.0 | quick consistent indicators | candidate |
| EDGAR (JRC) | emissions by country and sector, gridded | download | CC BY 4.0 | emissions context, heat maps | have (17) |
| IMF fossil fuel subsidies | explicit/implicit subsidies by country | download | IMF terms | "who pays for fossil" story | candidate |
| Ember, IRENA, World Bank | | | | | have |

### Granular

| Dataset | Gives | Access | Licence | Why | Status |
|---|---|---|---|---|---|
| **Global Renewables Watch** (Microsoft/Planet) | 375,197 wind turbines and 86,410 solar farms detected from satellites, quarterly 2017–2024 | GitHub releases (GeoPackage) | MIT | every wind turbine and solar farm worldwide, with build dates | have (17) |
| TransitionZero Solar Asset Mapper (TZ-SAM) | solar plants from satellites, 183 countries | Zenodo | *NC* (CC BY-NC 4.0) | research view only | candidate (NC) |
| Global Solar Atlas, Global Wind Atlas | resource rasters (PVOUT, wind speed at 100 m) | download (large) | CC BY 4.0 | "where the resource is" | brief 16 part E (download approval) |
| Climate TRACE; world HV grid (Overture) | | | | | wave 2 (06, 07) |
| WRI Aqueduct 4.0 | water stress, flood risk per basin | download | CC BY 4.0 | **site screening** (data centres need water) | have (12) |
| GHSL / WorldPop population grids | people per km² | download | CC BY 4.0 | demand and access context | have (17) |
| ERA5 (Copernicus) | hourly weather reanalysis, 1940– | CDS API (free account) | Copernicus licence (commercial OK) | capacity factors anywhere | candidate |
| Renewables.ninja | simulated hourly wind/solar output anywhere | API (free account) | *NC* | research view only | candidate (NC) |
| NASA Black Marble | night lights, monthly | download | public domain | electrification, outages after disasters | blocked (17: `NASA_EARTHDATA_TOKEN`) |
| Global Dam Watch / GRanD | dams and reservoirs | download | CC BY 4.0 | hydro layer | candidate |
| Live markets: Japan JEPX (30-min area prices), Mexico CENACE (nodal prices), India Grid-India, South Africa Eskom, Chile CEN, NZ EMI, Korea KPX, Alberta AESO, Turkey EPİAŞ | prices, load, mix | downloads/APIs (some keys) | check each | the live map beyond Europe/US | JEPX, CENACE have (17); Grid-India blocked (refuses GitHub runners); keys pending for AESO, KPX, EPİAŞ |
| WDPA protected areas | | download | *NC* | exclusion zones for screening | candidate (NC: needs licence) |

## Picks for the product

The paid use cases (PLAN.md) are site screening, alerts and history/exports. The datasets
that serve them best, in order:

1. **Grid capacity and queues where you connect:** GB TEC register, Spain node capacity,
   Netherlands congestion map, ISO queues via gridstatus (plus LBNL, have).
2. **Prices where you connect:** US nodal LMPs (gridstatus), EU imbalance prices.
3. **Every asset:** Germany MaStR, Global Renewables Watch, EIA-923 output per plant.
4. **Risk:** EAGLE-I outages, WRI Aqueduct water stress, curtailment (netztransparenz).
5. **What consumers pay:** Eurostat and EIA-861 retail prices.

Suggested cloud wave 3 (one brief each): (1) GB TEC + NL capacity + Spain node capacity as a
"Connect here?" layer; (2) US nodal prices and ISO queues via gridstatus; (3) Germany MaStR;
(4) EAGLE-I outages + Aqueduct; (5) Eurostat + EIA-861 retail prices.

## Sources

- Global Renewables Watch: https://github.com/microsoft/global-renewables-watch, https://arxiv.org/pdf/2503.14860
- TZ-SAM licence: https://zenodo.org/records/11368204
- Netherlands capacity map model: https://modellen.netbeheernederland.nl/capaciteitskaart/2.1/index.html
- NESO TEC register: https://neso.energy/data-portal/transmission-entry-capacity-tec-register
- EAGLE-I: https://figshare.com/articles/dataset/The_Environment_for_Analysis_of_Geo-Located_Energy_Information_s_Recorded_Electricity_Outages_2014-2022/24237376
- gridstatus: https://opensource.gridstatus.io/
- open-mastr: https://pypi.org/project/open-mastr/0.14.5
- WRI Aqueduct 4.0: https://github.com/wri/Aqueduct40
- Spain capacity maps (CNMC): https://www.cnmc.es/prensa/mapa-capacidad-transporte-20260213
- JEPX: https://jepx.jp/en/electricpower/market-data/spot/ave_day.html
- PUDL: https://catalyst.coop/pudl
