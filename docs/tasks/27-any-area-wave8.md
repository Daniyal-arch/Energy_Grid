# 27. Any area, any level: the agent's area analytics and data wave 8

## Goal

Two parts in one session.

**A. Area analytics.** The agent answers for whatever area the user means: a country, a region,
a county, a city, a district or neighbourhood, a polygon drawn on the map, a circle around a
place, a bidding zone, a grid operator's territory, several of these together, or the whole
world. It shows **only the data inside that area**: its queries filter by the area's outline on
the server, its maps are clipped to the outline and framed on it, and every figure says which
area it covers and how it was computed. The agent reads the data directly, so clipping happens
in the query: the browser receives only the rows inside.

**B. Data wave 8.** The datasets that make area answers useful at every level: outlines at every
administrative level, rasters summed inside any polygon, energy figures per small area, and the
asset layers that peer platforms show and the atlas still lacks. The list comes from a review of
peer platforms and where they get their data (below).

Part A comes first: it is the frame every dataset in Part B plugs into.

## Read first

- `vault/index.md`, then `vault/backend/agent-tools.md`, `agent-graph.md`, `backend-service.md`,
  `vault/data/lake.md`, `vault/data/coverage-and-gaps.md`, `vault/frontend/map-rendering.md`
  (`clipToArea`, the area veil), `vault/frontend/state-and-datasets.md` (`area`, `drawn`).
- Backend: `backend/tools/places.py` (gazetteer), `tools/sql.py`, `tools/site.py` (it already
  sums the R2 population grid around a point), `backend/data/duck.py` (DuckDB with `httpfs` and
  `spatial`), `backend/data/guard.py` (the SQL guard), `agent/mapspec.py`,
  `agent/prompts/*.md`, `agent/skills/places-and-shapes/SKILL.md`, `agent/evals/`.
- Frontend: `frontend/src/app/agent.ts` (`viewOf()` sends the view; today `area` is the
  country list only), `src/lib/area.ts` (`AreaSpec`, `AreaShape`: one ring today),
  `src/map/areaLayers.ts`, `src/map/agentLayers.ts`.
- `docs/DATA_LAKE.md` sections 3 to 5 (partitions, Hilbert order, GeoParquet with a `bbox`
  column), `docs/DATASETS.md` (what was considered before; do not repeat rows marked "have").

## How to work

- Chat in the caveman style (`.claude/skills/caveman`); docs, code, commits and the PR in normal
  English. Update the vault at the end (`.claude/skills/atlas-vault`).
- One commit per step of Part A and per dataset family of Part B; ruff, pytest (root and
  `backend/`) and `npm run build` green at each commit.
- **Probe before building** (`scripts/probe_*.py` or `backend/probes/`) and put each probe's
  output in the PR: licence text as found, size, row counts, timings.
- **Explain large downloads first** (sizes below) and run them in GitHub Actions; outputs go to
  R2 (`lake/` for Parquet, COG for rasters, PMTiles for map geometry), never into git.
- Same access rules as brief 26: an honest client name, no bypassing of refusals, logins or
  terms; when a licence is unclear, write the question into the PR and leave the dataset out.

## Part A: area analytics

### A1. One area object and `resolve_area`

An area is one record, kept in the result store like a query result so maps and later turns
reuse it:

```
Area {
  area_id: "a_" + 12 hex,         # stable hash of the outline
  name, level,                    # world | group | country | region | county | locality |
                                  # neighbourhood | nuts0..nuts3 | lau | us_state | us_county |
                                  # us_place | us_tract | lsoa | msoa | iris | nl_buurt |
                                  # urban_centre | bidding_zone | operator | polygon | circle | bbox
  iso3: [...], parents: [...],    # the countries and larger areas it lies in
  geometry,                       # MultiPolygon, WKB, EPSG:4326
  bbox, area_km2,                 # geodesic area (computed)
  source: {dataset, licence}      # where the outline comes from
}
```

New tool `resolve_area` (agent and MCP):

- **From the view.** The browser sends its area: the countries (`area`), and, new, the drawn
  polygon or circle (`drawn`, an `AreaSpec`) with its name. `viewOf()` in `app/agent.ts` adds
  it. "Here", "this area", "what I drew" resolve to it; with nothing drawn, "here" means the map
  on screen (the camera's bounds, level `bbox`).
- **From text.** The gazetteer plus the outlines of B1, ranked by level and population.
  Ambiguous names return candidates with their parents ("Paris, France" and "Paris, Texas";
  "Limburg" in NL and BE); the agent picks the one in view or asks.
- **Unions and groups.** "Benelux", "the Nordics", "Bavaria and Baden-Württemberg": the union
  of resolved areas. Named groups (EU-27, Nordics, Baltics, Western Balkans, CWE...) come from a
  small YAML list in `agent/` with a source for each membership.
- **Buffers and intersections.** "Within 20 km of Rotterdam port" (circle or buffer around a
  point, line or polygon); "the protected areas in Bavaria" (intersection).
- **Grid areas.** Bidding zones (have), ISO/RTO and balancing areas (US), grid operator
  territories where published (MaStR per municipality, EIA-861 territories; have).
- **Never an invented outline.** When no outline exists at the asked level, say so and offer
  the nearest one, named: a city as its municipality (LAU, commune) or as its GHSL urban
  centre; a neighbourhood as the national small-area unit.

Each resolved area carries its own figures: `area_km2` and the population summed inside (A4),
with their sources.

### A2. Every query inside the area

- **`run_sql` sees the areas.** The tool registers the turn's resolved areas as a read-only
  view `areas(area_id, name, level, geometry, xmin, ymin, xmax, ymax)` in the DuckDB session and
  two macros: `in_area(lon, lat, 'a_…')` (bbox test first, then `ST_Contains`) and
  `area_geom('a_…')`. The guard allows these names and nothing else new.
- **Prune before the exact test.** Write the bbox as plain `lon BETWEEN … AND lat BETWEEN …`
  first, so the Hilbert-sorted lake files skip row groups, then the exact test. Measure it
  (A7) on the large tables.
- **Points** (plants, substations, units, chargers, data centres): counted and summed inside.
- **Lines** (grid, pipelines, roads): `km inside` from `ST_Intersection`, geodesic length,
  labelled "km of line inside the area (computed)".
- **Polygons** (protected areas, flood zones, solar farms): the share of the area they cover,
  geodesic, labelled.
- **Tables keyed by region** (NUTS, admin-1, LSOA, IRIS, counties): when the area is that
  region, join by key. When the area is drawn, **never split a region's total by area share**
  (that is an estimate, hard rule 1): sum the regions wholly inside, list the regions that lie
  partly inside with their full values, and say so ("3 regions lie partly inside; their totals
  are shown, not split").
- **Live figures** (ENTSO-E, EIA-930) are per zone or country: the answer names the zones the
  area touches and gives their figures as such.
- **No area named and none on screen:** the dataset's whole coverage, aggregated for a world or
  continent view (A3). The default is never "the first 200 rows".

### A3. Any level, the right detail

- **Every record counted, drawn at a readable density.** The cartographer gets the number of
  rows inside the area. Up to ~20,000 points: points. More: the existing hexbin and grid styles,
  or H3 cells computed in SQL (DuckDB `h3` community extension; probe that it installs in the
  Lambda image), each cell with its count and sum, and a key that says so. Records are never
  dropped to make a map clearer (owner's rule).
- **Shapes one level below the area** for choropleths: world to countries; a country to
  admin-1 or NUTS 2/3; a region to counties, LAU or communes; a city to districts,
  neighbourhoods, IRIS, LSOA or Dutch buurten; a US state to counties, then tracts. New
  `data.shapes` values in MapSpec: `admin2`, `lau`, `divisions:<subtype>`, `us_places`,
  `us_tracts`, `lsoa`, `msoa`, `iris`, `nl_buurt`, `urban_centres`, `h3:<res>` and `area` (the
  area itself). The backend serves them simplified per country (`/api/shapes/{set}/{iso3}`, from
  R2); the app does not bundle them.
- **MapSpec gains `area: {area_id}`.** The app fetches the outline (`/api/areas/{area_id}`,
  saved with the map record), draws it with the existing outline and veil, fits the camera to
  its bbox and clips the agent's layers with it (`clipToArea`). It also sets the app's own area
  to it, so the base layers (grid, plants) are clipped the same way and the context panel's area
  card shows the area. `AreaSpec` gains a multipolygon kind (`{kind: "shape", polygons}`):
  countries with islands and unions are not one ring.
- **Multi-map answers** keep one area per panel (comparing two cities side by side) or one area
  for all panels.

### A4. Rasters summed in any polygon: `area_stats`

New tool `area_stats(area_id, measures[])`, zonal statistics over cloud-optimised GeoTIFFs read
by HTTP range (rasterio in the Lambda image; probe the image size and cold start):

| Measure | Raster (B2) | Rule shown with the figure |
|---|---|---|
| people | GHSL population, 100 m (Europe, US) and 1 km (world) | sum of the cells whose centre lies inside |
| built-up area | GHSL built-up surface | sum of the cells whose centre lies inside |
| land cover shares | ESA WorldCover 10 m, or its 1 km class-share COG for large areas | share of cells per class |
| slope classes | slope computed from Copernicus DEM GLO-30 | share of cells per class |
| solar and wind resource | Global Solar Atlas PVOUT, Global Wind Atlas speed at 100 m | mean of the cells (and range) |
| flood depth | JRC river flood hazard RP100 (have) | share of cells above 0 m, above 1 m |

- Above a cell budget, read a COG overview and name the cell size used.
- Water stress (Aqueduct) and protected areas stay polygon datasets (A2).
- The figures are passthrough sums and shares of published cells, never interpolated.

### A5. The skill and the prompts

- New skill `agent/skills/area-analysis/SKILL.md`: resolve first; the area's own figures; each
  dataset's count or sum inside; a choropleth one level down; comparison with the parent area or
  peers when asked; how to say partial coverage ("12 of 14 grid operators in this area publish
  free capacity"), from the coverage registry for the countries the area touches.
- A level matrix in the catalogue: which dataset exists at which level (country, region,
  municipality, small area, point), so the agent knows what a city question can be answered
  with.
- Update `places-and-shapes`, `make-map` (the `area` field, the shapes one level down) and the
  router and cartographer prompts.

### A6. API

`GET /api/areas/resolve?q=`, `GET /api/areas/{area_id}` (outline as GeoJSON, its figures,
sources), `GET /api/shapes/{set}/{iso3}`. MCP gets `resolve_area` and `area_stats`.

### A7. Done-check for Part A

- `resolve_area` resolves ten names at six levels (country, region, county, city,
  neighbourhood, zone), two ambiguous ones, a drawn polygon, a circle, a union and a buffer.
- A timing table in the PR for `in_area` on three large tables (Overture substations, MaStR
  units, Global Renewables Watch) at four sizes (country, region, city, drawn polygon), from the
  Lambda-sized container; target under 5 s for a city.
- `area_stats` population of Berlin equals the GHSL sum computed independently in the probe.
- An agent map with the area outline, clipped, the camera on the area; choropleths one level
  down for a country, a region and a city.
- Twenty new eval cases in `agent/evals/` (fake model in CI, one real run's log in the PR), for
  example: solar farms in Bavaria; free grid capacity within 30 km of Lyon; substations in a
  drawn polygon; km of high-voltage line in Greater London; data centres in Dublin and the
  bidding zone they sit in; population and protected-area share of the Ruhr; coal plants of the
  world by country; Paris, France against Paris, Texas; a neighbourhood of Amsterdam.

## Part B: data wave 8

### What peer platforms show, and where their data comes from (research 2026-10-29)

| Platform | What it shows | Where its data comes from | What the atlas takes |
|---|---|---|---|
| Electricity Maps (app; open-source parsers in `electricitymaps-contrib`, AGPL-3.0) | live mix and CO₂ for ~200 zones, ~75 production and ~38 exchange parsers | each zone's TSO or market API (ENTSO-E, EIA-930, national operators), listed per zone in the repo's data-sources file; capacity from Ember, IRENA, GEM, ENTSO-E, EIA | the list of public endpoints per zone, to extend "Live grids beyond Europe" with our own fetchers. Do not copy AGPL code into this repository |
| Open Infrastructure Map | power, telecoms, oil and gas, water | OpenStreetMap tags | nothing new: the atlas has OSM power through Overture |
| Global Energy Monitor trackers, GEM.wiki | plants, mines, pipelines, terminals, steel, cement; ownership chains | company filings, government registers, news; CC BY 4.0 | the Global Energy Ownership Tracker (B4) |
| EIA U.S. Energy Atlas | 84 layers, 60 from EIA forms | EIA-860, 923, 176, 757, 820 and others; transmission from HIFLD (HIFLD Open was deactivated on 2025-08-26; lines archived on DataLumos; substations removed since 2022) | the US midstream layers the atlas lacks (B4) |
| Siting platforms (Transect, Paces, LandGate, Acres, PVcase, ICF EnergyInSite) | parcels, wetlands, flood zones, soils, land cover, slope, brownfields, historic places, irradiance, lines and substations, substation capacity | parcels licensed (Regrid, ReportAll); USFWS NWI, FEMA NFHL, USDA SSURGO, NLCD, USGS 3DEP, EPA, NRHP, NSRDB, HIFLD; Transect's injection capacity "with base and N-1 scenarios" is its own power-flow modelling on planning cases (CEII) | the open layers: land cover, slope, flood, wetlands (B2, B4). Not parcels (licensed) and not modelled capacity (brief 26 publishes only what operators publish) |
| JRC Energy and Industry Geography Lab | power plants (JRC-PPDB-OPEN), hydropower, energy-intensive industry (EU ETS + E-PRTR), hydrogen | JRC's own harmonisation of EU registers; public FTP, © JRC attribution | industry sites where brief 24 did not place them (B4) |
| Hotmaps, Pan-European Thermal Atlas | heat demand density at 100 m, excess heat | national statistics broken down with open data (top-down) | heat demand and excess heat (B4), licence to check |
| GHSL (JRC) | population, built-up, Urban Centre Database R2024 | Sentinel and Landsat with census data | population and built-up rasters (B2), city outlines worldwide (B1) |
| TransitionZero TZ-SAM | solar farms from satellites, 183 countries | its own detection; CC BY-NC 4.0 | nothing: non-commercial, and Global Renewables Watch (have) covers it |
| WECC wildfire updates, NASA FIRMS, EFFIS | lines near active fires | satellites (VIIRS, MODIS); WECC counts a line within 3 miles of an active fire | fires near the grid (B4) |
| Grid Status, Interconnection.fyi | ISO prices, load, queues | the ISOs' APIs and queue files | nothing new: brief 10 |

### B1. Outlines at every level (Part A depends on these)

| Dataset | Levels | Licence | Notes |
|---|---|---|---|
| Overture Maps divisions, `division_area` | country down to locality, neighbourhood and microhood, worldwide | **check**: older release notes say ODbL, a mirror says CDLA-Permissive-2.0; record the current release's statement | monthly GeoParquet on S3 and Azure; read only the needed columns by range; keep id, names, subtype, country, region, parent ids, geometry; a simplified copy for maps |
| geoBoundaries ADM2 | second level, worldwide | CC BY 4.0 | ADM1 is in the lake already |
| US Census TIGER/Line | places, tracts, ZCTAs (counties if missing) | public domain | |
| UK ONS boundaries | LAD, MSOA, LSOA 2021 | OGL v3 | join keys for B3 |
| France IGN / INSEE | communes, IRIS | Licence Ouverte 2.0 | join keys for Agence ORE |
| Netherlands CBS wijk- en buurtkaart | municipalities, districts, neighbourhoods | CC BY 4.0 | join keys for CBS figures |
| Eurostat GISCO LAU 2024 | every EU municipality, with population | © EuroGeographics; commercial use needs a EuroGeographics licence | use only if the licence check allows; otherwise Overture `localadmin` plus the national sets |
| GHS Urban Centre Database R2024 | 11,422 urban centres with ~2,600 attributes, 1975-2030 | CC BY 4.0 per JRC (confirm on the download page) | ~1.7 GB zip; city outlines worldwide and their figures |

### B2. Rasters for `area_stats`

| Raster | Licence | Access |
|---|---|---|
| GHSL population (E2025, 100 m for Europe and the US, 1 km world) and built-up surface | CC BY 4.0 | COG on R2 (DATA_LAKE "Future" row) |
| ESA WorldCover 10 m v200 | CC BY 4.0 | AWS open data `s3://esa-worldcover` (eu-central-1), COG in 3x3 degree tiles: read in place; build a 1 km class-share COG in Actions for large areas |
| Copernicus DEM GLO-30 | check the Copernicus DEM licence | AWS open data, read in place; slope computed (in Actions for a 1 km slope-class COG; on the fly for small areas) |
| Global Solar Atlas PVOUT, Global Wind Atlas 100 m | CC BY 4.0 | brief 16 part E: use its COGs if they landed, else add them |

### B3. Energy figures per small area

| Dataset | Level | Licence | What |
|---|---|---|---|
| France, Agence ORE: annual electricity and gas consumption | IRIS, commune, EPCI, department, region; 2011-2024 | Licence Ouverte 2.0 | by sector and NAF code; ODS API; method changed in 2022 for IRIS (say so) |
| UK, DESNZ subnational electricity and gas consumption | LSOA (domestic only), MSOA, local authority, postcode | OGL v3 | meters, total, mean and median per meter |
| UK, DESNZ regional renewable statistics | local authority | OGL v3 | sites, capacity, generation per technology |
| Netherlands, CBS Kerncijfers wijken en buurten | neighbourhood | CC BY 4.0 | average electricity and gas per dwelling |
| Netherlands, grid operators' small-consumer data per postcode range (Liander, Enexis, Stedin) | postcode range | check each | probe and keep only what is open |
| Denmark, Energi Data Service consumption and production per municipality | municipality, hourly | CC BY 4.0 | probe the dataset names |
| US, DOE LEAD tool | state, county, city, tract | public (check the download terms) | energy burden, average bills per fuel |
| US, Census ACS heating fuel (table B25040) | tract | public domain | API; `CENSUS_API_KEY` optional |
| US, NREL SLOPE | county, city, tract | check | consumption and potentials; skip if the terms are unclear |
| European cities, Global Covenant of Mayors emission inventories (JRC, ~6,200 cities) | city | unclear ("all rights reserved" unless stated) | probe the JRC data catalogue; a data request if needed |

### B4. Asset layers peers show and the atlas lacks

| Dataset | Gives | Licence | Notes |
|---|---|---|---|
| EIA midstream layers | US refineries, gas processing plants, underground gas storage, petroleum terminals, crude, product and HGL pipelines, ethanol and biodiesel plants | public domain | EIA Atlas ArcGIS services; one layer group "Oil and gas (US)" |
| EEA Industrial Reporting database (EU Registry + E-PRTR + LCP, v15, 2007-2023) | every reporting facility with position, releases to air, water and land, large combustion plants' fuel input | check the EEA record's access constraints | coordinate with brief 24 (ETS positions): add the facilities and releases it does not cover |
| Global Dam Watch | 41,145 barriers, 35,295 reservoirs | CC BY 4.0 | Figshare; hydro context |
| GEM Global Energy Ownership Tracker | owners and ownership chains for nine GEM trackers | CC BY 4.0 | GEM form download through the existing GEM workflow (repo secrets); join to plants and mines by GEM ids; the agent answers "who owns" |
| CO2StoP (SETIS) | CO₂ storage units and capacity in Europe | re-use authorised with acknowledgement | KML and CSV; mostly more than ten years old: show the vintage |
| Hotmaps heat demand density and excess heat sites | 100 m heat demand, EU28 | check (project repositories) | for district heating and data-centre waste heat |
| NASA FIRMS active fires (VIIRS, MODIS) | fire detections, last 24 h and 7 days | NASA open data | `FIRMS_MAP_KEY` (free, 5,000 transactions per 10 minutes); live layer; computed count of lines within 4.8 km (3 miles) of a detection, labelled with WECC's rule |
| EFFIS burnt areas | EU burnt areas of about 30 ha and more | check the EFFIS terms | yearly |
| US wetlands (USFWS NWI) and flood zones (FEMA NFHL) | siting constraints | public domain | large: PMTiles plus the agent reading the services in place for small areas; optional, last |

Not added: parcels (licensed), TZ-SAM, GADM, WDPA and the GEM earthquake model
(non-commercial), line ratings (PyPSA's `s_nom` is modelled, not published), any modelled
capacity.

### B5. For every dataset

- A probe with licence text, size and a few rows; then the build script, the lake table
  (GeoParquet with `bbox`, Hilbert-sorted, metadata as in DATA_LAKE section 4) and a catalogue
  YAML entry whose examples were run (the answers from the probe or the build).
- A layer with its key and source, a `datasets.json` entry with coverage, a row in
  `docs/DATA_SOURCES.md`, `docs/DATA_LAKE.md` and `data/coverage.yaml` where it is a family.
- The level matrix (A5) updated.

## Keys and sizes

- Keys: `FIRMS_MAP_KEY` (free, https://firms.modaps.eosdis.nasa.gov/api/map_key/),
  `CENSUS_API_KEY` (optional, https://api.census.gov/data/key_signup.html); GEM through the
  existing workflow. Document each in `.env.example`; a script skips what its key lacks and says
  so.
- Sizes (state them in the PR before each download): Overture divisions (probe; read only the
  needed columns), GHS-UCDB ~1.7 GB zip, GHSL 100 m population for Europe and the US (probe),
  WorldCover and the DEM read in place (the derived 1 km COGs ~0.1 GB each), the B3 tables and
  B4 layers under 1 GB together except NWI and NFHL (probe first, last).

## Deliverables

- Backend: `resolve_area`, `area_stats`, the `areas` view and macros in `run_sql`, the guard
  update, the new API routes, MCP tools, MapSpec `area` and new `shapes` values (regenerate the
  schema and TS types with `backend/scripts/gen_mapspec.py`), skill `area-analysis`, prompts,
  evals.
- Frontend: `viewOf()` sends `drawn`; multipolygon `AreaSpec`; the agent's map sets the app's
  area, clips and frames; child-level shapes fetched from the backend.
- Data: B1 to B4 in the lake and on the map, each with its catalogue entry and docs rows.
- `docs/AGENT.md` (area section), `docs/DATASETS.md` (wave 8 rows marked have or blocked), the
  vault notes changed, `vault/log.md`.

## Done-check

- Part A's checks (A7).
- Every B dataset is built, or listed in the PR as blocked with the reason (licence unclear,
  key missing, source closed) and its data request text.
- `uv run ruff check . && uv run ruff format .`, `uv run pytest`, `cd backend && uv run pytest`,
  `cd frontend && npm run build`.

## Out of scope

- Estimates of any kind: no area-weighted splitting of regional totals, no modelled capacity,
  no interpolated rasters.
- Licensed or non-commercial sources (above), sources behind a login.
- New floating panels: an area is shown with the existing outline, veil and area card.
