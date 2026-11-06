# Data lake: full-detail data for the agent

The map files in `frontend/public/data/` keep only what the map draws (sums, thresholds,
simplified outlines). The agent needs the full detail. This document says which data is kept
in full as Parquet on R2, which is read live from the source's API, how the Parquet is written
and indexed, and how big it gets. Sizes are estimates until each pipeline writes its measured
size to the catalogue (below); update this file then.

## 1. The rule: API or Parquet

A dataset is **read live from its API** (no Parquet copy) when all of these hold, checked
with a probe (`scripts/probe_*.py`, rule 2):

1. **Filters on the server**: the API filters by the agent's dimensions (place, time, id), so
   an answer never needs a full download.
2. **Fast**: a typical agent question needs at most ~5 requests and ~5 s.
3. **History**: the API serves the whole period the agent needs, not only the current state.
4. **Limits**: one server key covers the agent's load (≥ 60 requests/min or a generous daily
   quota), at no cost per request.
5. **Reliable**: documented, versioned, and up (Energy-Charts, answering 503 since 2026-09-24,
   fails this).
6. **Licence** allows serving answers from it.

Two special cases:
- **Already in a public cloud bucket as Parquet or Zarr** (PUDL, ARCO-ERA5): query in place,
  but only if the probe, run from where the agent runs, meets rule 2. Overture fails it (a
  query by power class reads part of every file in a region: tens of seconds to minutes), so
  the lake keeps its own power extract (section 6).
- **Current-state APIs** (registers that show only today: NESO TEC, the Dutch capacity map,
  REE's node file, MaStR): read today's state from the API, but keep **snapshots** as Parquet,
  because the history exists nowhere else.

Anything else (no API, slow or one-window-at-a-time APIs, bulk files only) is kept as Parquet.

**PUDL in place, measured** (`scripts/probe_pudl.py` on a GitHub runner, 2026-10-13; DuckDB
over HTTPS range requests, `stable/` release; cold = first query, warm = DuckDB's metadata
cache filled):

| Question | File | Cold | Warm |
|---|---|---:|---:|
| EPA CEMS hourly, one plant (Barry, 3) in July 2023 | `core_epacems__hourly_emissions.parquet`, 4.88 GB, 10,180 row groups of 100,000 rows | 1.7 s | 0.6 s |
| EPA CEMS hourly, one state (TX) in 2023 | same | **24.3 s** | 0.7 s |
| EIA-923 monthly generation, one plant, every month | `core_eia923__monthly_generation.parquet`, one row group | 1.4 s | 0.3 s |

The state-year question fails rule 2 cold: the file is sorted by neither state nor year, so
DuckDB reads the footers of all 10,180 row groups before it can skip. Proposal (not built):
an extract `lake/pudl_cems/hourly/year=Y/` sorted by `state, plant_id_eia,
operating_datetime_utc` (~0.5 GB a year), refreshed with PUDL's releases; until then plant and
plant-month questions go to PUDL in place, state and national ones need the extract.

## 2. Where it lives

- Bucket: `infraatlas-raw` (private; the GEM rule already keeps licensed raw files there),
  prefix `lake/`. The agent reads with a read-only R2 token; open datasets can be copied to a
  public bucket later if a public download is wanted.
- Layout (Hive partitioning, lower-case names):
  ```
  lake/<dataset>/<table>/<partition>=<value>/part-<n>.parquet
  lake/<dataset>/<table>.parquet                 (small tables, one file)
  lake/<dataset>/_catalog.json                   (per dataset)
  lake/_catalog.json                             (all datasets)
  ```
  e.g. `lake/eaglei/outages/year=2024/part-0.parquet`,
  `lake/mastr/units_solar/snapshot=2026-10-01/land=BY/part-0.parquet`.
- Written only by GitHub Actions (the same jobs that build the map files); a laptop never
  holds the raw files. Each file ≤ 250 MB (wrangler's single upload limit is ~300 MB; larger
  tables are partitioned further).
- Writes are atomic per partition: a new file is uploaded, then the catalogue is updated.
  Snapshots are never overwritten.

## 3. Three layers, and when to partition by place

1. **Source tables**: one dataset per source (`lake/entsoe/`, `lake/eaglei/`, `lake/mastr/`),
   as published, typed and documented. Licence, refresh and columns differ by source, so
   sources are never mixed in one file.
2. **Standard keys in every table**: `iso2` and `iso3` (ISO 3166-1), `admin1` (state,
   province, Land) where the source has it, and position as `lon`/`lat` or `geometry`. Any
   dataset is filtered by country the same way.
3. **Topic views** on top (in `lake.duckdb` and the catalogue), no copies: `plants` (GEM,
   MaStR, EIA-860, JRC, with a `source` column), `prices` (ENTSO-E, US nodal, retail),
   `outages`, `emissions` (EU ETS, Climate TRACE, PUDL), `grid_capacity` (TEC, NL, REE, ISO
   queues), `water_risk`.

Folders by place only when a table is large **and** most questions ask one place: each
partition file must stay ≥ ~50 MB (many small files are slower than a few large ones). Else
the country is the first sort column, and min/max statistics do the skipping.

| Table kind | Example | Partition | Sort |
|---|---|---|---|
| one country | EAGLE-I (US), MaStR (DE), NESO (GB) | year or snapshot (MaStR solar also by Land) | the entity id, then time |
| many countries, medium | ENTSO-E, Eurostat, GEM | year | `area`/`iso2`, then time or id |
| world, small (< 1 GB) | Aqueduct, Global Renewables Watch | none or a few files | `iso3`, then Hilbert |
| world, large | Overture power extract, US nodal prices | release or market, then year (one file per band or month) | `iso3`/node, then Hilbert or time |

## 4. How each file is written (the standard)

Writer: `scripts/lake.py` (DuckDB `COPY ... TO ... (FORMAT parquet)`, the engine the agent
reads with). It writes one ordered file per partition: DuckDB's partitioned writer runs in
parallel and does not keep the sort order, which would defeat the skipping (tested
2026-10-13 on DuckDB 1.5.6: ordered single files give non-overlapping row groups).

| Setting | Value | Why |
|---|---|---|
| Format | Parquet, format version 2 | current standard; delta encodings for integers and timestamps |
| Compression | zstd, level 9 | best size/speed for read-mostly data (written once, read many times) |
| Row group | ~1,000,000 rows (≈ 32–128 MB uncompressed) | big enough for compression, small enough to skip; a remote reader fetches only the row groups it needs by HTTP range |
| File size | 50–250 MB; small tables one file | few files = few requests |
| Encoding | dictionary for strings and codes (DuckDB's default) | zone, county, type columns become small integers |
| Statistics | min/max per row group for every column (default) | row-group skipping |
| Bloom filters | on id columns (DuckDB writes them for dictionary-encoded columns) | point lookups ("unit 11WD7…", "county 48201") skip row groups without the id |
| Key-value metadata | `source`, `licence`, `retrieved_at`, `script`, `source_version`, `rows` | every file says where it came from (hard rule 1) |

Types:
- Time: `TIMESTAMP WITH TIME ZONE` stored as UTC (`ts`, the interval's start), plus
  `resolution_min` where it varies. Sources that publish local times without a zone keep that
  column as published (`ts_local`) next to UTC when the zone is known.
- Measurements: `FLOAT` (32-bit) when the source has ≤ 7 significant digits (MW to 0.1,
  customers), else `DOUBLE`. Money and prices: `DECIMAL(p, s)` with the source's precision
  (prices keep the source's precision, CLAUDE.md).
- Codes: the source's own ids (EIC, FIPS, MaStR number, pfaf_id), never re-keyed.
- Geometry: GeoParquet 1.1, WKB in `geometry`, CRS EPSG:4326, plus a `bbox` covering column
  (`struct<xmin, ymin, xmax, ymax>`, declared in the GeoParquet metadata), rows sorted along a
  Hilbert curve (`ST_Hilbert`) so nearby features share row groups.

## 5. Indexing

Parquet has no B-tree; reads are fast because whole parts of files are skipped. Four layers:

1. **Partitions** (directories): the first filter of almost every question (year, snapshot,
   country, market). DuckDB skips whole files by path.
2. **Sort order = clustered index**: rows are sorted by the columns the agent filters on next
   (e.g. `fips, ts` or `area, psr_type, ts`), so each row group covers a narrow range and the
   min/max statistics skip the rest.
3. **Bloom filters** on id columns, for "this one unit / county / node" lookups.
4. **Dimension tables**: one small table per entity (areas, units, counties, nodes) with
   names, codes and positions; the big fact tables carry only ids.

The agent opens `lake/_catalog.json` (or a read-only `lake.duckdb` holding a view per table)
and queries with DuckDB over `httpfs` against R2's S3 endpoint.

`lake/lake.duckdb` (`scripts/lake_catalog.py`, daily, `.github/workflows/lake-catalog.yml`):
one schema per dataset with a view per table (`eaglei.outages`, `entsoe.prices`, …) and the
topic views of section 3 in `main`. DuckDB binds a view when it creates it, so the file is
built where R2 is readable; the workflow derives S3 credentials from the Cloudflare API token
(key id = the token's id, secret = SHA-256 of the token; masked, never written to the file).
The agent attaches it and brings its own read-only R2 secret:

```sql
ATTACH 'lake.duckdb' AS lake (READ_ONLY);
CREATE SECRET (TYPE r2, KEY_ID '…', SECRET '…', ACCOUNT_ID '…');
SELECT sum(value) * 0.25 FROM lake.main.outages
WHERE source = 'EAGLE-I' AND area = '48201' AND start >= '2024-01-01' AND start < '2025-01-01';
-- 176,042,304.25 customer-hours (as the map's file), 5.4 s from a GitHub runner
``` A question such as "hours
without power in Harris County in 2024" reads one year's file, the row groups whose `fips`
range holds 48201, and two columns: a few MB, not 1.4 GB.

## 6. Schemas

Common columns: `ts` (UTC start), `resolution_min`. `*_id` columns are the source's ids.

### EAGLE-I outages (`lake/eaglei/`), adding now

| Table | Columns | Partition | Sort | Bloom |
|---|---|---|---|---|
| `outages` | `fips` VARCHAR(5), `ts` TIMESTAMP (as published), `customers_out` INTEGER | `year` | `fips, ts` | `fips` |
| `counties` | `fips`, `county`, `state`, `mcc_customers` INTEGER (ORNL's modelled customers) | none | `fips` | |
| `coverage`, `dqi` | EAGLE-I's `coverage_history.csv` and `DQI.csv` as published | none | | |

### MaStR, every German unit (`lake/mastr/`), adding now

| Table | Key columns | Partition | Sort | Bloom |
|---|---|---|---|---|
| `units_solar`, `units_wind`, `units_storage`, `units_combustion`, `units_biomass`, `units_hydro`, `units_nuclear`, `units_other` | `mastr_nr` (SEE…), `eeg_mastr_nr`, `status`, `gross_kw`, `net_kw`, `commissioned`, `decommissioned`, `ags` (municipality key), `postcode`, `lon`, `lat` (where public), `operator_nr`, `grid_operator_nr`, `voltage_level`, and the type's own columns (hub height, rotor diameter; panel orientation, usage; storage kWh…) | `snapshot`, and `land` (state) for solar | `ags, mastr_nr` | `mastr_nr` |
| `operators`, `grid_connection_points`, `locations` | as published | `snapshot` | id | id |

Snapshots: the newest, plus one per year (the others are dropped after a year).

### WRI Aqueduct 4.0 (`lake/aqueduct/`, `source_version` 4.0), adding now

| Table | Columns | Sort |
|---|---|---|
| `baseline_annual` (GeoParquet) | `aq30_id`, `pfaf_id`, `gid_0`, `gid_1`, `name_0`, `name_1`, `area_km2`, then for each of the 13 indicators (`bws`, `bwd`, `iav`, `sev`, `gtd`, `rfr`, `cfr`, `drr`, `ucw`, `cep`, `udw`, `usa`, `rri`) `_raw` DOUBLE, `_score` FLOAT, `_cat` SMALLINT (WRI's no-data -9999), `_label`; the weighted scores; `geometry`, `bbox` | Hilbert |
| `basins` (GeoParquet) | `pfaf_id`, `iso2`, `iso3`, `admin1` (the country and province holding most of the basin), `geometry`, `bbox` | Hilbert |
| `baseline_monthly` | `pfaf_id`, `month`, per indicator `_raw/_score/_cat` | `pfaf_id, month` |
| `future_annual` | `pfaf_id`, `scenario`, `year`, per indicator | `pfaf_id, scenario, year` |

### ENTSO-E history (`lake/entsoe/`), 2015 onward

| Table | Columns | Partition | Sort | Bloom |
|---|---|---|---|---|
| `areas` | `area` (EIC), `code` (DE-LU), `kind` (BZN/CTY/CTA), `name`, `country`, `iso2`, `iso3` | | `code, kind` | |
| `prices` (A44) | `ts`, `area`, `area_eic`, `resolution_min`, `price` DECIMAL(9,2), `currency`, `sequence` (classification sequence: EXAA, intraday auctions) | `year` | `area, ts` | |
| `load` (A65) | `ts`, `area`, `resolution_min`, `actual_mw` (A16), `day_ahead_mw` (A01) | `year` | `area, ts` | |
| `generation` (A75) | `ts`, `area`, `psr_type`, `resolution_min`, `generation_mw`, `consumption_mw` | `year` | `area, psr_type, ts` | |
| `forecast_wind_solar` (A69) | `ts`, `area`, `psr_type`, `resolution_min`, `forecast_mw` | `year` | `area, psr_type, ts` | |
| `flows` (A11) | `ts`, `out_area`, `in_area`, `resolution_min`, `mw` | `year` | `out_area, in_area, ts` | |
| `units` | `unit_eic`, `plant_eic`, `name`, `area`, `psr_type`, `capacity_mw` (A71), `lon`, `lat` (JRC-PPDB) | | `unit_eic` | `unit_eic` |
| `unit_output` (A73) | `ts`, `unit_eic`, `area`, `resolution_min`, `mw` | `year` | `unit_eic, ts` | `unit_eic` |
| `capacity` (A68) | `ts`, `area`, `psr_type`, `capacity_mw` | `year` | `area, psr_type, ts` | |
| `transfer_capacity` (A61, A31) | `ts`, `out_zone`, `in_zone`, `doc`, `resolution_min`, `mw` | `year` | `out_zone, in_zone, ts` | |
| `outages` (A80) | `mrid`, `revision`, `doc_status`, `zone`, `asset_eic`, `asset_name`, `plant_eic`, `plant_name`, `psr_type`, `type`, `reason`, `reason_text`, `start`, `end`, `point_start`, `resolution_min`, `available_mw`, `nominal_mw` (one row per point of the available-capacity curve, every revision) | `year` of start | `asset_eic, start, revision` | `asset_eic` |

| `imbalance_price` (A85) | `ts`, `zone`, `category` (A05 deficit, A04 excess), `price` DECIMAL(12,3), `currency` (as published: EUR, PLN, CZK, HUF, RON …), `resolution_s` | `zone`, `year` | `zone, category, ts` | |

Every table also carries `iso2`, `iso3` (from the area code) and `admin1` (NULL). A78
(transmission unavailability) is not built yet: it is asked per border and was not probed.

### Overture power extract (`lake/overture_power/`), with task 07

| Table | Columns | Partition | Sort |
|---|---|---|---|
| `lines` (GeoParquet) | `id` (Overture), `class` (power_line/cable/minor_line), `kv` (highest voltage, from OSM's tag), `voltage` (the tag as published), `circuits`, `cables`, `frequency`, `operator`, `name`, `dc`, `cable`, `iso3`, `geometry`, `bbox` | `release` (one file per longitude band) | `iso3`, Hilbert |
| `sites` (GeoParquet: substations, plants, converters…) | `id`, `class`, `kv`, `voltage`, `operator`, `name`, the OSM tags as a map, `iso3`, `geometry`, `bbox` | `release` (one file per longitude band) | `iso3`, Hilbert |

Lines from 60 kV (and all cables and substations); no towers, poles or single generators.
Each monthly release is kept until the next; one per year is kept for good. The world map
tiles (`grid/world-hv.pmtiles`) are cut from the same extract.

### Registers kept as snapshots (current-state APIs)

| Table | Columns | Partition |
|---|---|---|
| `lake/neso_tec/projects` | the TEC register as published (project, customer, site, MW connected, MW change, cumulative MW, effective date, status, agreement, TO, plant type, project id, gate) | `snapshot` (twice weekly) |
| `lake/nl_capacity/areas` | area id, name, operator, offtake and feed-in status, queues (MW), requests; geometry only when it changes | `snapshot` (monthly) |
| `lake/ree_nodes/nodes` | every column of "Ficha Capacidades" with normalised names | `snapshot` (monthly) |
| `lake/euets/installations`, `verified_emissions`, `eea_link` | registry extracts (all years 2005–, allocations, surrenders) and the EEA id/position link | `snapshot` (weekly) for installations |

### Future (shapes fixed when built)

- `lake/us_lmp/day_ahead` (task 10): `ts`, `node_id`, `lmp`, `congestion`, `loss` DECIMAL(9,2);
  partition `market`, `year`, `month`; sort `node_id, ts`; bloom `node_id`; `nodes` dimension
  with published positions. Real-time 5-minute prices: API only (recent), not stored.
- GeoParquet for Global Renewables Watch, USPVDB, GRanD, TYNDP projects (EMODnet answers by WFS: API).
- Rasters are **Cloud-Optimized GeoTIFF**, the raster standard, not Parquet. Built (task 16):
  `lake/atlas/atlas-pvout.tif` (Global Solar Atlas PVOUT) and `lake/atlas/atlas-wind100.tif`
  (Global Wind Atlas, mean wind speed at 100 m), listed under `rasters` in
  `lake/atlas/_catalog.json` (`scripts/build_atlas.py`). Population grids later.
- `lake/afdc/stations` (GeoParquet, partition `snapshot`): every public US charging station
  with every AFDC field (`scripts/fetch_ev_chargers.py`); waits for `NREL_API_KEY`.

## 7. Every dataset: API or Parquet, and its size

### Measured (`lake/_catalog.json`, 2026-10-17)

Written by `scripts/lake_catalog.py`; these replace the estimates below where a dataset is
built. Parquet, zstd level 9, on R2.

| Dataset (`lake/…`) | Tables | Rows | Size | Estimate was |
|---|---:|---:|---:|---|
| `mastr` (one snapshot, 2026-10-13) | 12 | 28,165,719 | 1.31 GB | ~0.6 GB per snapshot |
| `eaglei` (2014–2025) | 4 | 249,320,127 | 0.25 GB | ~0.8 GB |
| `aqueduct` | 4 | 429,196 | 0.22 GB | ~0.15 GB |
| `eia930` (2015-07 → today) | 4 | 22,445,487 | 0.05 GB | ~0.1 GB |
| `gem` (private) | 54 | 895,568 | 0.03 GB | ~0.1 GB |
| `nl_capacity` (one snapshot) | 1 | 924 | 0.012 GB | ~0.01 GB/yr |
| `entsog` (2021-10 → today, see below) | 3 | 2,093,461 | 0.011 GB | ~0.05 GB |
| `power_plants_eu` (JRC-PPDB, powerplantmatching) | 3 | 316,535 | 0.009 GB | ~0.01 GB |
| `osm` (one snapshot) | 5 | 22,549 | 0.008 GB | ~0.05 GB |
| `euets` | 3 | 672,978 | 0.007 GB | ~0.01 GB |
| `lbnl_queue`, `eia860m`, `irena`, `neso_tec`, `ree_nodes` | 6 | 271,317 | 0.003 GB | ~0.04 GB |
| `entsoe` (task 14: `areas`, `units` so far; years backfilling) | 2 | 1,875 | 0.00003 GB | ~1.2 GB |
| **All built** | **101** | **304.6 M** | **1.91 GB** | |

Added 2026-10-18 (task 16): `entsoe/imbalance_price` (2015 → today) 13,728,572 rows, 0.026 GB
(estimate was +0.05 GB/yr); `atlas` rasters (COG, not Parquet): `atlas-pvout.tif` 0.49 GB and
`atlas-wind100.tif` 14.07 GB, the wind atlas as downloaded (its own COG, float32 at ~250 m),
which takes the bucket past R2's 10 GB free storage.

MaStR is twice the estimate (every column of every unit, 6.6 M solar rows); EAGLE-I a third
of it (sorted by county and time, its 249 M rows compress to ~1 byte each).

**ENTSOG keeps about five years in its API** (2026-10-13): older months answer 404 "Data on
the TP is archived on a rolling basis … check the TP Archives in the Help Section". The lake
holds what the API serves (from 2021-10); the years before are in ENTSOG's archive files,
not fetched (a source change: the brief expected 2015–).

Sizes below: estimated Parquet (zstd) on R2, ±50 %. Snapshots per year where noted.

### On the map today

| Dataset | Access | Kept as | Why | Size |
|---|---|---|---|---|
| ENTSO-E (prices, load, generation, flows, per unit, capacity, forecasts, outages) | API, key; one area and ≤ 1 year per request | Parquet, 2015– | history across zones and years is thousands of requests | ~1.2 GB, +0.12 GB/yr |
| ENTSOG gas flows | API, no key; slow for many points; ~5 years served | Parquet, 2021-10– (older: ENTSOG archive files) | | 0.011 GB measured |
| GIE AGSI+ / ALSI | API, key, filters, full history | API | passes all six | 0 |
| Ember | API, all countries in one request | API | | 0 |
| IRENA capacity | yearly xlsx | Parquet | no API | ~0.005 GB |
| World Bank WDI | API | API | | 0 |
| GEM trackers (licensed) | downloads | Parquet, private | no API; licence: never public | ~0.1 GB |
| OSM-derived files (Europe grid, cables, data centres) | Overpass (slow) | Parquet snapshots | | ~0.05 GB |
| Overture power (lines ≥ 60 kV, substations, plants) | public GeoParquet on S3, too slow to query live | GeoParquet extract | fails rule 2 | ~0.5–1 GB |
| JRC-PPDB, powerplantmatching | downloads | Parquet | | ~0.01 GB |
| EIA-930 hourly | API, key, 5,000 rows per request | Parquet, 2015– | history = thousands of requests; recent hours by API | ~0.1 GB |
| EIA-860M | monthly xlsx | Parquet snapshots | | ~0.02 GB/yr |
| LBNL queue | yearly xlsx | Parquet | | ~0.005 GB |
| USWTDB turbines | API with filters | API | | 0 |
| EPA CAMPD hourly per unit | API, key; national pulls slow | query in place (PUDL's EPA CEMS Parquet on public S3) | already Parquet | 0 |
| ISO hub prices | ISO APIs | API (recent); history with task 10 | | 0 |
| Open-Meteo, ECMWF open data | API / rolling files | API | | 0 |
| Live grids (AEMO, ONS, Taipower, IESO) | live APIs | API | | 0 |

### Added this sprint

| Dataset | Access | Kept as | Why | Size |
|---|---|---|---|---|
| EU ETS registry | daily extract files, no query API | Parquet | | ~0.01 GB |
| EEA industrial register | Discodata SQL API | API | SQL over HTTP, fast | 0 |
| Climate TRACE | API with filters | API | | 0 |
| NESO TEC register | CKAN SQL API, current only | API + snapshots | history nowhere else | ~0.02 GB/yr |
| Dutch capacity map | ArcGIS query API, current only | API + snapshots | | ~0.01 GB/yr |
| REE node capacities | monthly xlsx | Parquet snapshots | no API | ~0.005 GB/yr |
| Eurostat retail prices | API | API | | 0 |
| EIA retail (861M) | API | API | | 0 |

### Adding now

| Dataset | Access | Kept as | Why | Size |
|---|---|---|---|---|
| EAGLE-I outages | 12 CSVs, 11.6 GB, no API | Parquet | no API | ~0.8 GB, +0.1 GB/yr |
| MaStR | bulk XML (~2.5 GB zip); SOAP API with registration and ~10,000 calls/day | Parquet snapshots | API far too limited | ~0.6 GB per snapshot |
| WRI Aqueduct 4.0 | 262 MB zip, no API | GeoParquet | no API | ~0.15 GB |

### Wave 5 (brief 17, built 2026-10-18)

| Dataset | Access | Kept as | Size (measured) |
|---|---|---|---|
| NUTS 2024, bidding zones from NUTS, CGAZ admin-1 (`shapes/*`) | downloads (360 MB CGAZ) | GeoParquet | 1,798 + 43 + 3,224 rows, ~0.11 GB |
| GeoNames cities15000 (`places/cities`) | download | GeoParquet | 34,167 rows, 0.002 GB |
| EIA-923 via PUDL | public Parquet on S3 | in place (no copy) | 0 |
| EPA eGRID2023 (`egrid/plants`) | xlsx | GeoParquet | 12,612 rows, 0.003 GB |
| EPA GHGRP 2023 (`ghgrp/facilities`) | xlsx + Envirofacts API | GeoParquet | 6,470 rows, 0.0005 GB |
| netztransparenz redispatch 2013-2020 (`netztransparenz/redispatch`) | open archive zip | Parquet | 40,118 rows, 0.0004 GB |
| SMARD | API, no key | API (catalogue only) | 0 |
| TYNDP 2024 projects (`tyndp/projects`) | JSON endpoints of the project map | GeoParquet | 363 rows, 0.0001 GB |
| ENTSO-E transmission outages A78 (`entsoe/transmission_outages`) | API, 246 border directions | Parquet, partition fetched day | 6,056 rows, 0.00015 GB a day |
| Global Renewables Watch v1.0 (`grw/solar`, `grw/wind`) | GitHub release, 453 MB GeoPackages | GeoParquet (+ `grid/grw.pmtiles` public) | see the catalogue |
| Eurostat nrg_bal_c, EIA SEDS, EIA STEO | APIs | API | 0 |
| EDGAR 2025 booklet (`edgar/ghg_by_sector`) | xlsx | Parquet | 261,365 rows, 0.002 GB |
| JEPX spot (`jepx/spot`) | CSV per year | Parquet, partition year | 9,696 rows a year, 0.0005 GB |
| CENACE PML (`cenace/pml`) | web service | Parquet, partition date | 62,640 rows a day, 0.0003 GB |
| GHSL population 2025 (`ghsl/population`) | 484 MB zip | Parquet (+ `grid/population-0.1deg.i32` public, 26 MB) | 4,569 rows |
| Energy Institute review (`ei_review/series`) | xlsx via a browser (`browser-fetch.yml`), raw file in `sources/ei/` | Parquet, long | 277,731 rows, 0.0015 GB |

### Wave 6 (brief 21, built 2026-10-19)

| Dataset | Access | Kept as | Size (measured) |
|---|---|---|---|
| Capareseau substations (`capareseau/substations`) | site JSON + CSV | GeoParquet, partition snapshot | 3,116 rows, 0.0003 GB |
| Terna Econnextion (`econnextion/requests`) | download-center JSON | Parquet, snapshot | 582 rows |
| Elia capacity (`elia_hosting/capacity`) | xlsx via a browser | Parquet, snapshot | blocked (Cloudflare) |
| E-REDES reception capacity (`eredes_capacity/substations`) | API (Opendatasoft) | Parquet, snapshot | 470 rows |
| ESB Networks heatmap (`esb_heatmap/transformers`) | xlsx | GeoParquet, snapshot | 46,527 rows, 0.002 GB |
| PSE Art. 7(8l) list, full switchgears (`pse_capacity/*`) | xlsx | Parquet, snapshot | 886 + 69 rows |
| Substations worldwide | our `overture_power/sites` | PMTiles `grid/world-substations.pmtiles` (public) | 870,774 points, 0.025 GB |
| MaStR grid operators (`mastr_grid/operators`) | our `mastr/*` | Parquet, snapshot | 15,213 rows |
| EIA-861 service territory | PUDL Parquet | in place | 0 |
| EMODnet cables, pipelines | WFS | API | 0 |
| Natura 2000 (`protected/natura2000`; PAD-US blocked) | ArcGIS services, paged | GeoParquet (+ `grid/protected.pmtiles`, 29 MB) | 27,173 rows |
| JRC flood RP100 (`lake/flood/*.tif`) | 171 MB + 49 MB zips | COG (classes) + tiles and lookups (public) | 0.06 GB lookups |
| Overture roads and rail (`overture_transport/segments`) | Overture S3 | GeoParquet, partition release (+ `grid/roads-rail.pmtiles`, 150 MB) | 5,939,529 rows, 0.80 GB |
| Hydrogen Observatory (`hydrogen/projects`) | xlsx | GeoParquet | 238 rows |
| AURES II (`aures/auctions`) | xlsx (Mendeley) | Parquet | 820 rows |
| NREL ATB 2025 (`atb/electricity`) | 321 MB CSV | Parquet | 1,161,588 rows, 0.007 GB |
| ENTSOG TYNDP 2026 (`entsog_tyndp/projects`) | xlsx | Parquet | 347 rows |
| GHG inventories (Eurostat `env_air_gge`) | API | API | 0 |
| FERC 714 | PUDL Parquet | in place | 0 |
| éCO2mix régional, REData by community, Transpower, Eskom | APIs | API | 0 |

### Wave 7 (brief 22, the coverage registry `data/coverage.yaml`)

| Dataset | Access | Kept as | Size (measured) |
|---|---|---|---|
| Room to connect, ten countries and two distribution grids (`connect_eu/<cc>`) | operators' JSON, ArcGIS layers, HTML tables, CSV | GeoParquet (Parquet for AT, DE, SE), snapshot partition | ~5,500 rows a snapshot, < 0.001 GB |
| Redispatch, countertrading, congestion costs (`entsoe/congestion_*`), NESO constraints, CAISO curtailment | ENTSO-E API, NESO CSV, CAISO xlsx | Parquet, snapshot partition | see the catalogue |
| CO₂ per kWh: RTE éCO2mix, REE, EirGrid, EIA-930 grid monitor | APIs and EIA's xlsx | API (no lake copy) | 0 |
| Every unit, national registers (`registers/<cc>`: gb, fr, dk, se, ie, be, fi) | CSV, xlsx, ArcGIS, ODRÉ export | GeoParquet where positioned, snapshot partition | ~30,000 positioned rows plus FR's register |
| Prices: GB market index and system prices (Elexon), SEM day-ahead, US real-time hubs | Elexon API, ENTSO-E API, gridstatus | API (no lake copy; the ENTSO-E lake holds the SEM) | 0 |
| What UK consumers pay (DESNZ international energy prices) | DESNZ xlsx, four tables | API (no lake copy; three small sheets) | 0 |
| UK ETS emissions per installation | UK ETS registry xlsx | in `ets.json` (no lake copy; ~800 rows) | 0 |
| GB plants offline (Elexon REMIT) | Elexon API | API (no lake copy; the API keeps the history) | 0 |
| US gas: EIA storage, Henry Hub, citygate; EIA pipelines | EIA API v2, ArcGIS | API (no lake copy; EIA keeps the history) | 0 |
| Power cuts, SAIDI and SAIFI (World Bank) | World Bank API | API (no lake copy; 29 countries × 6 years) | 0 |
| EV charging points and stations (`ev_eu/<cc>`: BNetzA, IRVE, OpenStreetMap) | CSV, Overpass API | GeoParquet, snapshot partition | DE 116,422 rows (4.7 MB); FR and OSM see the catalogue |

### Brief 23 (room to connect, one schema)

| Dataset | Access | Kept as | Size (measured) |
|---|---|---|---|
| Room to connect, every operator in one schema (`connect/harmonised`) | the operators' files, ArcGIS layers, PDF tables, Opendatasoft, JSON | GeoParquet (point = node position or area label point; outline as JSON text), snapshot partition | 19,266 rows, 1.7 MB (2026-10-27); 24,696 rows with brief 26 (53 operators, 2026-10-28) |

### Wave 8 (brief 27, any-area analytics)

| Dataset | Access | Kept as | Size (measured) |
|---|---|---|---|
| Outlines at every level (`outlines/*`: divisions, adm2, us_places, us_cousub, us_tracts, uk_ons, fr_iris, nl_cbs, small_areas, urban_centres, geostat_grid, names) | Overture S3 Parquet, Census zips, ONS/ArcGIS GeoJSON, IGN GeoPackage, CBS, national WFS | GeoParquet, Hilbert-sorted, bbox column; `names` without geometry | divisions 1,082,068 rows 2.26 GB; names 3,397,857 rows 0.12 GB; the rest 0.48 GB |
| Energy per small area (`small_area_energy/*`: consumption, heating, poverty, renewables) | ORE, DESNZ, Nomis, CBS, EDS, E-REDES, SCB, CSO, ICAEN, DOE LEAD, Eurostat | Parquet, iso3 partition | FR 5.2 M rows, GB 1.8 M, SE 0.37 M; ~0.1 GB |
| Rasters for area_stats (`rasters/*`: GHSL population and built-up tiles, class shares, Hotmaps heat density) | JRC FTP zips, ESA WorldCover and Copernicus DEM on AWS (read in place) | COG (ZSTD), 3 arc-second tiles plus 30 arc-second layers | built-up 0.77 GB tiles + 126 MB world; slope shares 650 MB; population similar to built-up |
| EEA Industrial Reporting (`industrial/*`), Global Dam Watch (`dams/*`), CO2StoP (`co2stop/*`), Hotmaps sites (`hotmaps/*`), GEM ownership (`gem_ownership/*`), TRI (`tri/releases`), EA Pollution Inventory (`uk_pi/releases`) | EEA WebDAV CSV, figshare GeoPackage, JRC zip, Hotmaps GitLab CSV, R2 private xlsx, EPA CSV, EA CKAN zip | GeoParquet where positioned, Parquet otherwise | TRI 77,295 rows 7.2 MB; PI 31,384 rows 0.4 MB; dams 41,145 + 35,295 rows |

API-or-Parquet: the Census ACS (B25040) and FIRMS stay API calls (keys in the environment); the
rest are files without a query API and land in the lake.

### Future (docs/DATASETS.md)

| Dataset | Access | Kept as | Size |
|---|---|---|---|
| US nodal prices, day-ahead (`lake/us_lmp/day_ahead`, built: `scripts/fetch_us_nodes.py`) | the markets' files, one day per request | Parquet | ~1 GB/yr (measured 2.7 MB a day, six markets) |
| US nodal prices, real-time 5-min | ISO APIs | API, recent only | 0 |
| ISO live queues (`lake/iso_queues/requests`, built: `scripts/fetch_us_queues.py`) | the markets' files, current only | weekly snapshots | ~0.01 GB/yr |
| ENTSO-E imbalance prices (A85; built: `lake/entsoe/imbalance_price`, task 16) | API, one zip of XML documents per area and 60 days | Parquet with ENTSO-E | +0.05 GB/yr |
| ENTSO-E imbalance volumes (A86) | API | Parquet with ENTSO-E (not built) | +0.02 GB/yr |
| netztransparenz redispatch, curtailment | downloads | Parquet | ~0.3 GB |
| SMARD, Energinet, Fingrid, Elia, RTE, REE REData | APIs with history | API | 0 |
| Eurostat balances, EIA SEDS/STEO/AEO, OWID, EDGAR (country) | APIs | API | 0 |
| Energy Institute review, EEA GHG, ACER, AURES, H₂ observatory | downloads | Parquet | ~0.05 GB |
| EIA-923, eGRID history, FERC | PUDL on public S3 | in place | 0 |
| GHGRP | Envirofacts API | API | 0 |
| NREL AFDC, OpenEI URDB | APIs | API | 0 |
| EMODnet wind farms | WFS, no key, the whole layer in seconds | API (on the map since 2026-10-17) | 0 |
| USPVDB | download (~10 MB zip), quarterly | on the map as JSON (2026-10-17); GeoParquet later | ~0.01 GB |
| GRanD, TYNDP projects | downloads | GeoParquet | ~0.1 GB |
| Global Renewables Watch | GeoPackage per quarter | GeoParquet | ~0.2 GB |
| Global Solar / Wind Atlas | rasters | COG | ~1 GB at 1 km (~8 GB at 250 m) |
| Population grid (GHSL) | raster | COG | ~0.3 GB at 1 km |
| ERA5 | ARCO-ERA5 Zarr on Google Cloud | in place | 0 |
| NASA Black Marble | NASA API | API | 0 |
| JEPX, CENACE history | file downloads | Parquet | ~0.2 GB |
| Other live markets (Grid-India, Eskom, CEN, EMI, KPX, AESO, EPİAŞ) | APIs | API | 0 |

### Totals

| Part | Size |
|---|---|
| Parquet, datasets on the map and added this sprint | ~1.6 GB |
| Parquet, adding now (EAGLE-I, MaStR, Aqueduct) | ~1.6 GB |
| Overture power extract | ~0.5–1 GB |
| **Lake today** | **~4 GB** |
| Parquet, future datasets | ~3.5 GB |
| Rasters (COG, 1 km) | ~1.3 GB |
| Map tiles (PMTiles, public bucket) | ~0.3 GB |
| **In about a year** | **~9 GB** (≈ 16 GB with 250 m rasters) |
| Growth | ~1.5 GB a year (mostly nodal prices, MaStR's yearly snapshot, ENTSO-E) |

Cost: R2 stores 10 GB free and charges nothing for downloads; beyond that $0.015 per GB a
month (15 GB ≈ $0.08 a month). Reads: 10 M free requests a month.

## 8. Catalogue

`lake/<dataset>/_catalog.json`, written by each pipeline after a successful upload:

```json
{
  "dataset": "eaglei",
  "source": "EAGLE-I recorded electricity outages, ORNL (figshare 24237376)",
  "licence": "CC BY 4.0",
  "script": "scripts/build_us_outages.py",
  "updated": "2026-10-13T10:00:00Z",
  "tables": {
    "outages": {
      "path": "lake/eaglei/outages/year=*/part-*.parquet",
      "partitions": ["year"], "sort": ["fips", "ts"], "bloom": ["fips"],
      "rows": 0, "bytes": 0,
      "columns": {"fips": "VARCHAR", "ts": "TIMESTAMP", "customers_out": "INTEGER"}
    }
  }
}
```

`lake/_catalog.json` lists every dataset with its size; this file's estimates are replaced by
those numbers.

## 9. Upgrade path (not now)

At tens of GB, or when several writers need transactions: move the tables to Apache Iceberg
with Cloudflare R2 Data Catalog (Iceberg on the same bucket, readable by DuckDB, Spark and
others). The file standard above stays the same; Iceberg adds the table metadata on top.

<!-- wave9:begin (generated by scripts/wave9.py render) -->
### Wave 9 (brief 28)

| Table | Kept as | Rows | Positioned |
|---|---|---|---|
| `wave9/be_fluvius_consumption` | Parquet | 540,342 | no |
| `wave9/de_zensus_heating` | GeoParquet (bbox, Hilbert order) | 2,628,942 | 2628942 |
| `wave9/ie_cso_saps_heating` | Parquet | 18,920 | no |
| `wave9/it_istat_sezioni` | GeoParquet (bbox, Hilbert order) | 756,376 | 756376 |
| `wave9/es_ine_secciones` | GeoParquet (bbox, Hilbert order) | 36,477 | 36477 |
| `wave9/fi_paavo` | GeoParquet (bbox, Hilbert order) | 3,026 | 3026 |
| `wave9/cz_zsj` | GeoParquet (bbox, Hilbert order) | 23,605 | 23605 |
| `wave9/ee_grid` | GeoParquet (bbox, Hilbert order) | 45,636 | 45636 |
| `wave9/gb_ea_flood_zones` | GeoParquet (bbox, Hilbert order) | 415,408 | 415408 |
| `wave9/us_eia_refineries` | GeoParquet (bbox, Hilbert order) | 130 | 130 |
| `wave9/us_eia_gas_processing` | GeoParquet (bbox, Hilbert order) | 478 | 478 |
| `wave9/us_eia_gas_pipelines` | GeoParquet (bbox, Hilbert order) | 32,961 | 32921 |
| `wave9/us_eia_crude_pipelines` | GeoParquet (bbox, Hilbert order) | 236 | 236 |
| `wave9/us_eia_lng` | GeoParquet (bbox, Hilbert order) | 8 | 8 |
| `wave9/us_eia_product_terminals` | GeoParquet (bbox, Hilbert order) | 1,474 | 1474 |
| `wave9/us_eia_gas_storage` | GeoParquet (bbox, Hilbert order) | 412 | 412 |
| `wave9/us_eia_hgl_pipelines` | GeoParquet (bbox, Hilbert order) | 133 | 133 |
| `wave9/us_eia_product_pipelines` | GeoParquet (bbox, Hilbert order) | 329 | 329 |
| `wave9/us_eia_crude_rail` | GeoParquet (bbox, Hilbert order) | 99 | 99 |
| `wave9/us_eia_biodiesel` | GeoParquet (bbox, Hilbert order) | 75 | 75 |
| `wave9/us_eia_ethanol` | GeoParquet (bbox, Hilbert order) | 197 | 197 |
| `wave9/us_natcarb` | GeoParquet (bbox, Hilbert order) | 186,675 | 186675 |
| `wave9/us_blm_solar_dla` | GeoParquet (bbox, Hilbert order) | 153 | 153 |
| `wave9/gb_ne_alc` | GeoParquet (bbox, Hilbert order) | 1,826 | 1826 |
| `wave9/fr_georisques_ssp` | GeoParquet (bbox, Hilbert order) | 12,431 | 12431 |
| `wave9/gb_brownfield_register` | GeoParquet (bbox, Hilbert order) | 40,229 | 38175 |
| `wave9/us_epa_repowering` | GeoParquet (bbox, Hilbert order) | 190,976 | 190976 |
| `wave9/us_epa_frs_cleanups` | GeoParquet (bbox, Hilbert order) | 45,924 | 45924 |
| `wave9/eu_land_prices` | Parquet | 12,354 | no |
| `wave9/world_ourairports` | GeoParquet (bbox, Hilbert order) | 86,337 | 86337 |
| `wave9/gb_he_listed` | GeoParquet (bbox, Hilbert order) | 379,686 | 379686 |
| `wave9/us_nrhp` | GeoParquet (bbox, Hilbert order) | 74,636 | 74636 |
| `wave9/us_nexrad` | GeoParquet (bbox, Hilbert order) | 210 | 210 |
| `wave9/gb_pins_dco` | GeoParquet (bbox, Hilbert order) | 295 | 292 |
| `wave9/gb_neso_etys` | GeoParquet (bbox, Hilbert order) | 34 | 34 |
| `wave9/gb_neso_tnuos` | Parquet | 572 | no |
| `wave9/us_openei_urdb` | Parquet | 58,920 | no |
| `wave9/ie_cso_datacentres` | Parquet | 132 | no |
| `wave9/gb_neso_constraint_costs` | Parquet | 210 | no |
| `wave9/gb_nged_opendata` | GeoParquet (bbox, Hilbert order) | 7,211 | 6053 |
| `wave9/gb_ssen_opendata` | GeoParquet (bbox, Hilbert order) | 1,317 | 1245 |
| `wave9/gb_npg_opendata` | Parquet | 445 | no |
| `wave9/dk_energinet_reserves` | Parquet | 728,595 | no |
| `wave9/gb_elexon_balancing` | Parquet | 48 | no |
| `wave9/us_iso_as_prices` | Parquet | 19,344 | no |
| `wave9/gb_emr_cm_register` | Parquet | 29,864 | no |
| `wave9/eu_eshm20` | GeoParquet (bbox, Hilbert order) | 100,636 | 100636 |
| `wave9/us_usgs_nshm` | GeoParquet (bbox, Hilbert order) | 9,794 | 9794 |
| `wave9/us_drought_monitor` | GeoParquet (bbox, Hilbert order) | 5 | 5 |
| `wave9/eu_jrc_coastal_flood` | GeoParquet (bbox, Hilbert order) | 20,865 | 20865 |
| `wave9/us_usgs_landslides` | GeoParquet (bbox, Hilbert order) | 680,497 | 680497 |
| `wave9/us_noaa_storm_events` | GeoParquet (bbox, Hilbert order) | 72,360 | 43917 |
| `wave9/us_usgs_geoelectric` | GeoParquet (bbox, Hilbert order) | 1,616 | 1616 |
| `wave9/fr_ore_ev_commune` | Parquet | 773,782 | no |
| `wave9/nl_rdw_vehicles` | Parquet | 9 | no |
| `wave9/de_kba_districts` | Parquet | 448 | no |
| `wave9/gb_dft_veh0142` | Parquet | 2,520 | no |
| `wave9/us_afdc_registrations` | Parquet | 51 | no |
| `wave9/fr_ore_solar_commune` | Parquet | 141,589 | no |
| `wave9/nl_cbs_solar` | Parquet | 78,944 | no |
| `wave9/gb_desnz_subregional_fit` | Parquet | 4,606 | no |
| `wave9/fr_ademe_dpe` | Parquet | 715 | no |
| `wave9/ie_seai_ber` | Parquet | 5,698,560 | no |
| `wave9/gb_epc_stats` | Parquet | 90 | no |
| `wave9/us_nyc_ll84` | GeoParquet (bbox, Hilbert order) | 103,259 | 99526 |
| `wave9/eu_degree_days` | Parquet | 39,600 | no |
| `wave9/us_cpc_degree_days` | Parquet | 48 | no |
| `wave9/ie_cso_dc_consumption` | Parquet | 1,650 | no |
| `wave9/eu_emodnet_wind_farms` | GeoParquet (bbox, Hilbert order) | 600 | 600 |
| `wave9/us_boem_wind_leases` | GeoParquet (bbox, Hilbert order) | 52 | 52 |
| `wave9/us_usseabed` | GeoParquet (bbox, Hilbert order) | 117,031 | 117031 |
| `wave9/us_usgs_mrds` | GeoParquet (bbox, Hilbert order) | 304,632 | 304613 |
| `wave9/eu_egdi_minerals` | GeoParquet (bbox, Hilbert order) | 28,223 | 28223 |
| `wave9/us_epa_lmop` | GeoParquet (bbox, Hilbert order) | 542 | 542 |
| `wave9/us_epa_agstar` | Parquet | 473 | no |
| `wave9/eu_salt_caverns` | GeoParquet (bbox, Hilbert order) | 119 | 119 |
| `wave9/us_usaspending_doe` | Parquet | 11,923 | no |
| `wave9/us_ira_energy_communities` | GeoParquet (bbox, Hilbert order) | 901 | 901 |
| `wave9/us_opportunity_zones` | GeoParquet (bbox, Hilbert order) | 8,765 | 8765 |
| `wave9/eu_household_income` | Parquet | 111,460 | no |
| `wave9/gb_ons_income_msoa` | Parquet | 7,264 | no |
| `wave9/us_nrel_sharing_sun` | Parquet | 4,810 | no |
| `wave9/eu_broadband_coverage` | Parquet | 1,404 | no |
| `wave9/eu_eea_wei` | Parquet | 21,006 | no |
| `wave9/us_usgs_water_use` | Parquet | 3,223 | no |
| `wave9/us_usgs_nwis_sites` | GeoParquet (bbox, Hilbert order) | 147,741 | 147729 |
| `wave9/world_ihfc_heat_flow` | GeoParquet (bbox, Hilbert order) | 91,182 | 91182 |
| `wave9/dk_district_heating` | GeoParquet (bbox, Hilbert order) | 6,263 | 6263 |
| `wave9/eu_tent_network` | GeoParquet (bbox, Hilbert order) | 4,767 | 4767 |
| `wave9/gb_srn` | GeoParquet (bbox, Hilbert order) | 43,040 | 43040 |
| `wave9/us_fhwa_afc` | GeoParquet (bbox, Hilbert order) | 2,275 | 2275 |
| `wave9/eu_eea_aq_stats` | GeoParquet (bbox, Hilbert order) | 16,343 | 16343 |
| `wave9/gb_defra_aurn` | GeoParquet (bbox, Hilbert order) | 2,448 | 2446 |
| `wave9/us_epa_aqs_annual` | GeoParquet (bbox, Hilbert order) | 65,709 | 65709 |
| `wave9/fr_enedis_interruptions` | Parquet | 94 | no |
| `wave9/us_eia861_reliability` | Parquet | 977 | no |
| `wave9/eu_ev_stock_nuts2` | Parquet | 15,106 | no |
| `wave9/eu_new_cars_fuel` | Parquet | 5,969 | no |
| `wave9/eu_heat_pumps` | Parquet | 24,857 | no |
| `wave9/eu_broadband_nuts2` | Parquet | 4,566 | no |
| `wave9/eu_rail_electrified` | Parquet | 2,651 | no |
| `wave9/eu_water_abstraction` | Parquet | 16,316 | no |
| `wave9/eu_water_use` | Parquet | 6,853 | no |
| `wave9/eu_wastewater_connected` | Parquet | 5,883 | no |
| `wave9/eu_nuclear_capacity` | Parquet | 3,363 | no |
| `wave9/eu_air_passengers` | Parquet | 10,203 | no |
| `wave9/eu_energy_productivity` | Parquet | 1,260 | no |
| `wave9/world_ourairports_runways` | GeoParquet (bbox, Hilbert order) | 48,405 | 15700 |
| `wave9/world_ourairports_navaids` | GeoParquet (bbox, Hilbert order) | 11,008 | 11008 |
| `wave9/us_epa_lmop_landfills` | GeoParquet (bbox, Hilbert order) | 2,323 | 2323 |
| `wave9/us_boem_active_leases` | GeoParquet (bbox, Hilbert order) | 4,892 | 4891 |
| `wave9/gb_dec_certificates` | Parquet | 90 | no |
| `wave9/gb_ulev_la` | Parquet | 484 | no |
| `wave9/us_smu_heat_flow` | GeoParquet (bbox, Hilbert order) | 106,468 | 0 |
| `wave9/eu_emodnet_platforms` | GeoParquet (bbox, Hilbert order) | 1,617 | 1617 |
| `wave9/eu_emodnet_pipelines` | GeoParquet (bbox, Hilbert order) | 3,951 | 3951 |
| `wave9/eu_emodnet_ocean_energy` | GeoParquet (bbox, Hilbert order) | 361 | 361 |
| `wave9/eu_emodnet_msp_zoning` | GeoParquet (bbox, Hilbert order) | 4,257 | 4257 |
| `wave9/eu_emodnet_ports` | GeoParquet (bbox, Hilbert order) | 946 | 946 |
| `wave9/eu_emodnet_port_goods` | GeoParquet (bbox, Hilbert order) | 429,668 | 429668 |
| `wave9/eu_emodnet_wwtp` | GeoParquet (bbox, Hilbert order) | 57,243 | 57243 |
| `wave9/eu_emodnet_nuclear` | GeoParquet (bbox, Hilbert order) | 121 | 121 |
| `wave9/eu_emodnet_desalination` | GeoParquet (bbox, Hilbert order) | 3,911 | 3911 |
| `wave9/eu_emodnet_hydrocarbon_licences` | GeoParquet (bbox, Hilbert order) | 28,506 | 28506 |
| `wave9/eu_emodnet_mpa` | GeoParquet (bbox, Hilbert order) | 826 | 826 |
| `wave9/eu_emodnet_military` | GeoParquet (bbox, Hilbert order) | 746 | 746 |
| `wave9/eu_emodnet_aggregates` | GeoParquet (bbox, Hilbert order) | 1,202 | 1202 |
| `wave9/eu_emodnet_substrate` | GeoParquet (bbox, Hilbert order) | 67,254 | 67254 |
| `wave9/eu_kohesio_2014_2020` | Parquet | 1,967,976 | no |
| `wave9/gb_npg_heatmap_substations` | GeoParquet (bbox, Hilbert order) | 670 | 670 |
| `wave9/gb_hnpd` | GeoParquet (bbox, Hilbert order) | 1,505 | 1495 |
| `wave9/eu_heat_production` | Parquet | 894,510 | no |
| `wave9/eu_network_costs` | Parquet | 81,164 | no |
| `wave9/eu_nonhousehold_prices` | Parquet | 2,307 | no |
| `wave9/eu_renewable_capacity` | Parquet | 18,961 | no |
| `wave9/eu_internet_households` | Parquet | 5,585 | no |
| `wave9/us_eia861_reliability_xlsx` | Parquet | 972 | no |
| `wave9/us_nrc_operating_reactors` | Parquet | 93 | no |
| `wave9/nl_cbs_datacentres` | Parquet | 16 | no |
| `wave9/eu_cleanh2_electrolyser_mfg` | Parquet | 11 | no |
| `wave9/de_emodnet_telecom_bsh` | GeoParquet (bbox, Hilbert order) | 28 | 28 |
| `wave9/es_emodnet_telecom_cica` | GeoParquet (bbox, Hilbert order) | 29 | 29 |
| `wave9/fr_emodnet_telecom_shom` | GeoParquet (bbox, Hilbert order) | 603 | 603 |
| `wave9/fr_emodnet_telecom_sigcables` | GeoParquet (bbox, Hilbert order) | 60 | 60 |
| `wave9/mt_emodnet_telecom` | GeoParquet (bbox, Hilbert order) | 6 | 6 |
<!-- wave9:end -->

<!-- wave10:begin (generated by scripts/wave9.py render) -->
### Wave 10 (brief 29)

| Table | Kept as | Rows | Positioned |
|---|---|---|---|
| `wave9/gb_desnz_elec_la` | Parquet | 7,770 | no |
| `wave9/gb_desnz_gas_la` | Parquet | 7,754 | no |
| `wave9/gb_desnz_gas_distribution` | Parquet | 35 | no |
| `wave9/gb_desnz_elec_distribution` | Parquet | 25 | no |
| `wave9/gb_desnz_tfec_la` | Parquet | 7,315 | no |
| `wave9/gb_desnz_ren_capacity_la` | Parquet | 4,606 | no |
| `wave9/gb_desnz_ren_generation_la` | Parquet | 4,582 | no |
| `wave9/gb_desnz_ren_sites_la` | Parquet | 4,606 | no |
| `wave9/gb_desnz_ghg_la` | Parquet | 7,657 | no |
| `wave9/gb_desnz_co2_la` | Parquet | 7,657 | no |
| `wave9/gb_desnz_ghg_dataset` | Parquet | 559,215 | no |
| `wave9/gb_dft_evcd_devices` | Parquet | 433 | no |
| `wave9/gb_dft_evcd_per_100k` | Parquet | 433 | no |
| `wave9/gb_dft_evcd_rapid` | Parquet | 433 | no |
| `wave9/gb_census_heating` | Parquet | 8,268 | no |
| `wave9/gb_census_accommodation` | Parquet | 5,724 | no |
| `wave9/gb_census_cars` | Parquet | 3,180 | no |
| `wave9/gb_census_tenure` | Parquet | 9,540 | no |
| `wave9/gb_census_bedrooms` | Parquet | 3,180 | no |
| `wave9/gb_census_travel_method` | Parquet | 7,632 | no |
| `wave9/gb_census_travel_distance` | Parquet | 6,996 | no |
| `wave9/gb_census_density` | Parquet | 331 | no |
| `wave9/gb_census_households` | Parquet | 1 | no |
| `wave9/eu_cei_cie011` | Parquet | 808 | no |
| `wave9/eu_cei_cie012` | Parquet | 1,616 | no |
| `wave9/eu_cei_gsr010` | Parquet | 21,420 | no |
| `wave9/eu_cei_gsr011` | Parquet | 492 | no |
| `wave9/eu_cei_gsr020` | Parquet | 315 | no |
| `wave9/eu_cei_gsr030` | Parquet | 564 | no |
| `wave9/eu_cei_pc020` | Parquet | 492 | no |
| `wave9/eu_cei_pc030` | Parquet | 1,622 | no |
| `wave9/eu_cei_pc031` | Parquet | 550 | no |
| `wave9/eu_cei_pc032` | Parquet | 285 | no |
| `wave9/eu_cei_pc034` | Parquet | 298 | no |
| `wave9/eu_cei_pc035` | Parquet | 145 | no |
| `wave9/eu_cei_pc040` | Parquet | 451 | no |
| `wave9/eu_cei_pc050` | Parquet | 451 | no |
| `wave9/eu_cei_srm010` | Parquet | 116 | no |
| `wave9/eu_cei_srm020` | Parquet | 36,368 | no |
| `wave9/eu_cei_srm030` | Parquet | 420 | no |
| `wave9/eu_cei_srm040` | Parquet | 3,168 | no |
| `wave9/eu_cei_wm010` | Parquet | 154 | no |
| `wave9/eu_cei_wm011` | Parquet | 510 | no |
| `wave9/eu_cei_wm020` | Parquet | 2,706 | no |
| `wave9/eu_cei_wm060` | Parquet | 451 | no |
| `wave9/eu_env_ac_aeint_r2` | Parquet | 5,354,167 | no |
| `wave9/eu_env_ac_aibrid_r2` | Parquet | 595,116 | no |
| `wave9/eu_env_ac_aibrid_rd` | Parquet | 86,264 | no |
| `wave9/eu_env_ac_aigg_q` | Parquet | 16,502 | no |
| `wave9/eu_env_ac_ainah_r2` | Parquet | 6,272,440 | no |
| `wave9/eu_env_ac_ainah_rd` | Parquet | 713,160 | no |
| `wave9/eu_env_ac_ccminv` | Parquet | 13,846 | no |
| `wave9/eu_env_ac_cepsgc1` | Parquet | 61,622 | no |
| `wave9/eu_env_ac_cepsgh1` | Parquet | 10,424 | no |
| `wave9/eu_env_ac_ch4fp` | Parquet | 19,233,000 | no |
| `wave9/eu_env_ac_co2fp` | Parquet | 19,233,000 | no |
| `wave9/eu_env_ac_cur` | Parquet | 420 | no |
| `wave9/eu_env_ac_curm` | Parquet | 75 | no |
| `wave9/eu_env_ac_egss1` | Parquet | 877,833 | no |
| `wave9/eu_env_ac_egss2` | Parquet | 5,789,110 | no |
| `wave9/eu_env_ac_egss3` | Parquet | 299 | no |
| `wave9/eu_env_ac_epiap1` | Parquet | 133,870 | no |
| `wave9/eu_env_ac_epigg1` | Parquet | 6,398 | no |
| `wave9/eu_env_ac_epissp1` | Parquet | 5,980 | no |
| `wave9/eu_env_ac_epite1` | Parquet | 558 | no |
| `wave9/eu_env_ac_epneis1` | Parquet | 2,922 | no |
| `wave9/eu_env_ac_eptrf1` | Parquet | 36,432 | no |
| `wave9/eu_env_ac_ghgfp` | Parquet | 19,233,000 | no |
| `wave9/eu_env_ac_hfcfp` | Parquet | 19,233,000 | no |
| `wave9/eu_env_ac_io10` | Parquet | 1,181,880 | no |
| `wave9/eu_env_ac_landfp` | Parquet | 165 | no |
| `wave9/eu_env_ac_mfa` | Parquet | 509,201 | no |
| `wave9/eu_env_ac_mfabi` | Parquet | 13,389 | no |
| `wave9/eu_env_ac_mfadpo` | Parquet | 35,446 | no |
| `wave9/eu_env_ac_mfain` | Parquet | 13,790 | no |
| `wave9/eu_env_ac_mid` | Parquet | 2,820 | no |
| `wave9/eu_env_ac_n2ofp` | Parquet | 19,233,000 | no |
| `wave9/eu_env_ac_nf3sf6fp` | Parquet | 19,233,000 | no |
| `wave9/eu_env_ac_pefa04` | Parquet | 301,792 | no |
| `wave9/eu_env_ac_pefa05` | Parquet | 4,564 | no |
| `wave9/eu_env_ac_pefafp` | Parquet | 80,400 | no |
| `wave9/eu_env_ac_pefasu` | Parquet | 8,152,111 | no |
| `wave9/eu_env_ac_pepsgg1` | Parquet | 39,490 | no |
| `wave9/eu_env_ac_pepsns1` | Parquet | 257,882 | no |
| `wave9/eu_env_ac_pepssp1` | Parquet | 32,268 | no |
| `wave9/eu_env_ac_pfcfp` | Parquet | 19,233,000 | no |
| `wave9/eu_env_ac_rme` | Parquet | 24,606 | no |
| `wave9/eu_env_ac_rmefd` | Parquet | 946,196 | no |
| `wave9/eu_env_ac_rp` | Parquet | 2,186 | no |
| `wave9/eu_env_ac_sd` | Parquet | 50,940 | no |
| `wave9/eu_env_ac_tax` | Parquet | 9,456 | no |
| `wave9/eu_env_ac_taxener` | Parquet | 3,535 | no |
| `wave9/eu_env_ac_taxind2` | Parquet | 431,730 | no |
| `wave9/eu_env_air_emis` | Parquet | 412,002 | no |
| `wave9/eu_env_air_emis_ind` | Parquet | 7,860 | no |
| `wave9/eu_env_air_no2` | Parquet | 3,240 | no |
| `wave9/eu_env_epea_cfin` | Parquet | 7,418 | no |
| `wave9/eu_env_epea_cint` | Parquet | 51,592 | no |
| `wave9/eu_env_epea_invap` | Parquet | 94,022 | no |
| `wave9/eu_env_epea_invgg` | Parquet | 3,624 | no |
| `wave9/eu_env_epea_invsp` | Parquet | 3,828 | no |
| `wave9/eu_env_epea_invte` | Parquet | 477 | no |
| `wave9/eu_env_epea_neep` | Parquet | 21,171 | no |
| `wave9/eu_env_epea_pap` | Parquet | 195,092 | no |
| `wave9/eu_env_epea_pgg` | Parquet | 26,444 | no |
| `wave9/eu_env_epea_psp` | Parquet | 22,488 | no |
| `wave9/eu_env_epea_trf` | Parquet | 20,044 | no |
| `wave9/eu_env_esst_cepgg` | Parquet | 142,792 | no |
| `wave9/eu_env_esst_cepggcp` | Parquet | 202,358 | no |
| `wave9/eu_env_esst_ceprw` | Parquet | 22,270 | no |
| `wave9/eu_env_esst_gg` | Parquet | 206,037 | no |
| `wave9/eu_env_esst_ggcp` | Parquet | 209,400 | no |
| `wave9/eu_env_esst_rw` | Parquet | 33,570 | no |
| `wave9/eu_env_wat_bal` | Parquet | 4,791 | no |
| `wave9/eu_env_wat_cat` | Parquet | 6,051 | no |
| `wave9/eu_env_wat_ind` | Parquet | 4,701 | no |
| `wave9/eu_env_wat_pop` | Parquet | 372 | no |
| `wave9/eu_env_wat_res` | Parquet | 7,192 | no |
| `wave9/eu_env_watabs_rb` | Parquet | 23,732 | no |
| `wave9/eu_env_watres_rb` | Parquet | 17,705 | no |
| `wave9/eu_env_watuse_rb` | Parquet | 7,030 | no |
| `wave9/eu_iww_eq_age` | Parquet | 2,236 | no |
| `wave9/eu_iww_eq_age_loa` | Parquet | 559 | no |
| `wave9/eu_iww_eq_loadcap` | Parquet | 2,626 | no |
| `wave9/eu_iww_eq_power_lo` | Parquet | 482 | no |
| `wave9/eu_nrg_bal_cv` | Parquet | 166,309 | no |
| `wave9/eu_nrg_bal_s` | Parquet | 1,966,518 | no |
| `wave9/eu_nrg_cb_bm` | Parquet | 12,332 | no |
| `wave9/eu_nrg_cb_cosm` | Parquet | 30,549 | no |
| `wave9/eu_nrg_cb_e` | Parquet | 36,635 | no |
| `wave9/eu_nrg_cb_eim` | Parquet | 17,165 | no |
| `wave9/eu_nrg_cb_em` | Parquet | 41,927 | no |
| `wave9/eu_nrg_cb_gas` | Parquet | 296,960 | no |
| `wave9/eu_nrg_cb_gasm` | Parquet | 125,203 | no |
| `wave9/eu_nrg_cb_h` | Parquet | 31,148 | no |
| `wave9/eu_nrg_cb_h2` | Parquet | 11,208 | no |
| `wave9/eu_nrg_cb_oil` | Parquet | 8,907,863 | no |
| `wave9/eu_nrg_cb_oilm` | Parquet | 2,904,030 | no |
| `wave9/eu_nrg_cb_pem` | Parquet | 206,979 | no |
| `wave9/eu_nrg_cb_rw` | Parquet | 674,532 | no |
| `wave9/eu_nrg_cb_sff` | Parquet | 696,518 | no |
| `wave9/eu_nrg_cb_sffm` | Parquet | 299,713 | no |
| `wave9/eu_nrg_chdd_a` | Parquet | 992 | no |
| `wave9/eu_nrg_chdd_m` | Parquet | 11,904 | no |
| `wave9/eu_nrg_chddr2_m` | Parquet | 691,200 | no |
| `wave9/eu_nrg_chp_cpfe` | Parquet | 73,831 | no |
| `wave9/eu_nrg_chp_f` | Parquet | 5,350 | no |
| `wave9/eu_nrg_chp_n` | Parquet | 5,201 | no |
| `wave9/eu_nrg_d_cv` | Parquet | 6,144 | no |
| `wave9/eu_nrg_d_hhq` | Parquet | 67,178 | no |
| `wave9/eu_nrg_d_indq_n` | Parquet | 1,001,830 | no |
| `wave9/eu_nrg_d_serq_n` | Parquet | 133,670 | no |
| `wave9/eu_nrg_d_traq` | Parquet | 102,962 | no |
| `wave9/eu_nrg_dhdc_c` | Parquet | 841 | no |
| `wave9/eu_nrg_dhdc_cpl` | Parquet | 6,572 | no |
| `wave9/eu_nrg_dhdc_e` | Parquet | 3,367 | no |
| `wave9/eu_nrg_dhdc_n` | Parquet | 1,759 | no |
| `wave9/eu_nrg_ind_ahbtc` | Parquet | 44,688 | no |
| `wave9/eu_nrg_ind_cotd` | Parquet | 10,172 | no |
| `wave9/eu_nrg_ind_di` | Parquet | 405 | no |
| `wave9/eu_nrg_ind_difec` | Parquet | 10,657 | no |
| `wave9/eu_nrg_ind_ebmg` | Parquet | 25,080 | no |
| `wave9/eu_nrg_ind_eff` | Parquet | 10,842 | no |
| `wave9/eu_nrg_ind_ei` | Parquet | 2,195 | no |
| `wave9/eu_nrg_ind_ep` | Parquet | 1,105 | no |
| `wave9/eu_nrg_ind_epsc` | Parquet | 20,760 | no |
| `wave9/eu_nrg_ind_esc` | Parquet | 32,692 | no |
| `wave9/eu_nrg_ind_esr` | Parquet | 405 | no |
| `wave9/eu_nrg_ind_fecf` | Parquet | 20,298 | no |
| `wave9/eu_nrg_ind_fechm2` | Parquet | 87 | no |
| `wave9/eu_nrg_ind_ffgae` | Parquet | 597 | no |
| `wave9/eu_nrg_ind_hpind` | Parquet | 2,920 | no |
| `wave9/eu_nrg_ind_hptctc` | Parquet | 127,568 | no |
| `wave9/eu_nrg_ind_ibmg` | Parquet | 25,080 | no |
| `wave9/eu_nrg_ind_id` | Parquet | 7,761 | no |
| `wave9/eu_nrg_ind_id3cf` | Parquet | 3,304 | no |
| `wave9/eu_nrg_ind_idooil` | Parquet | 4,466 | no |
| `wave9/eu_nrg_ind_ioc` | Parquet | 6,497 | no |
| `wave9/eu_nrg_ind_peh` | Parquet | 266,012 | no |
| `wave9/eu_nrg_ind_pehap` | Parquet | 155,618 | no |
| `wave9/eu_nrg_ind_pehcf` | Parquet | 928,323 | no |
| `wave9/eu_nrg_ind_pehnf` | Parquet | 156,820 | no |
| `wave9/eu_nrg_ind_psth2` | Parquet | 2,599 | no |
| `wave9/eu_nrg_ind_rcaebt` | Parquet | 3,192 | no |
| `wave9/eu_nrg_ind_rctcbt` | Parquet | 4,611 | no |
| `wave9/eu_nrg_ind_re` | Parquet | 19,264 | no |
| `wave9/eu_nrg_ind_ren` | Parquet | 2,343 | no |
| `wave9/eu_nrg_ind_resovsh` | Parquet | 10,032 | no |
| `wave9/eu_nrg_ind_stjpjss` | Parquet | 12,013 | no |
| `wave9/eu_nrg_ind_ured` | Parquet | 15,012 | no |
| `wave9/eu_nrg_ind_urhcd` | Parquet | 18,852 | no |
| `wave9/eu_nrg_ind_urtd` | Parquet | 33,452 | no |
| `wave9/eu_nrg_inf_bt` | Parquet | 6,926 | no |
| `wave9/eu_nrg_inf_epc` | Parquet | 93,704 | no |
| `wave9/eu_nrg_inf_epct` | Parquet | 6,230 | no |
| `wave9/eu_nrg_inf_h2stpc` | Parquet | 2,462 | no |
| `wave9/eu_nrg_inf_lbpc` | Parquet | 2,499 | no |
| `wave9/eu_nrg_inf_stcs` | Parquet | 625 | no |
| `wave9/eu_nrg_pc_202_c` | Parquet | 56,971 | no |
| `wave9/eu_nrg_pc_202_v` | Parquet | 850 | no |
| `wave9/eu_nrg_pc_203_c` | Parquet | 95,229 | no |
| `wave9/eu_nrg_pc_203_v` | Parquet | 1,617 | no |
| `wave9/eu_nrg_pc_204_v` | Parquet | 1,785 | no |
| `wave9/eu_nrg_pc_205_v` | Parquet | 2,315 | no |
| `wave9/eu_nrg_stk_gas` | Parquet | 6,738 | no |
| `wave9/eu_nrg_stk_gasm` | Parquet | 38,584 | no |
| `wave9/eu_nrg_stk_h2` | Parquet | 632 | no |
| `wave9/eu_nrg_stk_oam` | Parquet | 50,915,404 | no |
| `wave9/eu_nrg_stk_oem` | Parquet | 28,688 | no |
| `wave9/eu_nrg_stk_oil` | Parquet | 49,646 | no |
| `wave9/eu_nrg_stk_oilm` | Parquet | 7,886,384 | no |
| `wave9/eu_nrg_stk_oom` | Parquet | 21,952,802 | no |
| `wave9/eu_nrg_te_bio` | Parquet | 621,122 | no |
| `wave9/eu_nrg_te_eh` | Parquet | 205,930 | no |
| `wave9/eu_nrg_te_gas` | Parquet | 409,048 | no |
| `wave9/eu_nrg_te_gasm` | Parquet | 2,440,767 | no |
| `wave9/eu_nrg_te_h2` | Parquet | 19,694 | no |
| `wave9/eu_nrg_te_oil` | Parquet | 3,905,304 | no |
| `wave9/eu_nrg_te_oilm` | Parquet | 23,365,824 | no |
| `wave9/eu_nrg_te_sff` | Parquet | 1,447,808 | no |
| `wave9/eu_nrg_ti_bio` | Parquet | 621,262 | no |
| `wave9/eu_nrg_ti_coifpm` | Parquet | 7,284,668 | no |
| `wave9/eu_nrg_ti_eh` | Parquet | 205,947 | no |
| `wave9/eu_nrg_ti_gas` | Parquet | 409,049 | no |
| `wave9/eu_nrg_ti_gasm` | Parquet | 2,628,311 | no |
| `wave9/eu_nrg_ti_h2` | Parquet | 19,694 | no |
| `wave9/eu_nrg_ti_oil` | Parquet | 3,902,880 | no |
| `wave9/eu_nrg_ti_oilm` | Parquet | 24,235,212 | no |
| `wave9/eu_nrg_ti_sff` | Parquet | 1,447,806 | no |
| `wave9/eu_rail_eq_locon` | Parquet | 2,381 | no |
| `wave9/eu_rail_eq_locop` | Parquet | 1,671 | no |
| `wave9/eu_rail_eq_pa_csb` | Parquet | 836 | no |
| `wave9/eu_rail_eq_pa_cty` | Parquet | 829 | no |
| `wave9/eu_rail_eq_pa_nty` | Parquet | 1,683 | no |
| `wave9/eu_rail_eq_trset` | Parquet | 1,497 | no |
| `wave9/eu_rail_eq_vans` | Parquet | 241 | no |
| `wave9/eu_rail_eq_wagon` | Parquet | 3,588 | no |
| `wave9/eu_rail_if_line_ga` | Parquet | 6,897 | no |
| `wave9/eu_rail_if_line_na` | Parquet | 5,959 | no |
| `wave9/eu_rail_if_line_sp` | Parquet | 2,305 | no |
| `wave9/eu_rail_if_line_tr` | Parquet | 5,022 | no |
| `wave9/eu_rail_if_lvlcros` | Parquet | 1,260 | no |
| `wave9/eu_rail_if_tracks` | Parquet | 1,421 | no |
| `wave9/eu_rail_if_traff` | Parquet | 794 | no |
| `wave9/eu_road_eqr_busmot` | Parquet | 4,897 | no |
| `wave9/eu_road_eqr_bussea` | Parquet | 285 | no |
| `wave9/eu_road_eqr_busveh` | Parquet | 1,306 | no |
| `wave9/eu_road_eqr_carmot` | Parquet | 4,194 | no |
| `wave9/eu_road_eqr_carpda` | Parquet | 6,741 | no |
| `wave9/eu_road_eqr_lormot` | Parquet | 9,944 | no |
| `wave9/eu_road_eqr_lorrit` | Parquet | 3,557 | no |
| `wave9/eu_road_eqr_mopeds` | Parquet | 2,199 | no |
| `wave9/eu_road_eqr_motors` | Parquet | 1,305 | no |
| `wave9/eu_road_eqr_semit` | Parquet | 2,170 | no |
| `wave9/eu_road_eqr_spurp` | Parquet | 442 | no |
| `wave9/eu_road_eqr_tracmot` | Parquet | 4,458 | no |
| `wave9/eu_road_eqr_trail` | Parquet | 2,572 | no |
| `wave9/eu_road_eqr_trams` | Parquet | 163 | no |
| `wave9/eu_road_eqr_unlweig` | Parquet | 2,011 | no |
| `wave9/eu_road_eqr_zev` | Parquet | 11,403 | no |
| `wave9/eu_road_eqs_busage` | Parquet | 3,174 | no |
| `wave9/eu_road_eqs_busmot` | Parquet | 5,268 | no |
| `wave9/eu_road_eqs_bussea` | Parquet | 322 | no |
| `wave9/eu_road_eqs_busveh` | Parquet | 1,421 | no |
| `wave9/eu_road_eqs_carage` | Parquet | 2,729 | no |
| `wave9/eu_road_eqs_caremiss` | Parquet | 89 | no |
| `wave9/eu_road_eqs_carhab` | Parquet | 654 | no |
| `wave9/eu_road_eqs_carmot` | Parquet | 4,431 | no |
| `wave9/eu_road_eqs_lormot` | Parquet | 10,410 | no |
| `wave9/eu_road_eqs_lorroa` | Parquet | 6,990 | no |
| `wave9/eu_road_eqs_lorton` | Parquet | 3,761 | no |
| `wave9/eu_road_eqs_mopeds` | Parquet | 2,353 | no |
| `wave9/eu_road_eqs_motorc` | Parquet | 1,435 | no |
| `wave9/eu_road_eqs_roaene` | Parquet | 4,555 | no |
| `wave9/eu_road_eqs_semit` | Parquet | 2,262 | no |
| `wave9/eu_road_eqs_spurp` | Parquet | 486 | no |
| `wave9/eu_road_eqs_trail` | Parquet | 2,604 | no |
| `wave9/eu_road_eqs_trams` | Parquet | 308 | no |
| `wave9/eu_road_eqs_unlweig` | Parquet | 2,026 | no |
| `wave9/eu_road_eqs_zev` | Parquet | 11,334 | no |
| `wave9/eu_sdg_06_10` | Parquet | 1,308 | no |
| `wave9/eu_sdg_06_20` | Parquet | 435 | no |
| `wave9/eu_sdg_06_30` | Parquet | 308 | no |
| `wave9/eu_sdg_06_40` | Parquet | 350 | no |
| `wave9/eu_sdg_06_50` | Parquet | 336 | no |
| `wave9/eu_sdg_06_60` | Parquet | 1,034 | no |
| `wave9/eu_sdg_06_70` | Parquet | 285 | no |
| `wave9/eu_sdg_07_10` | Parquet | 1,687 | no |
| `wave9/eu_sdg_07_11` | Parquet | 1,687 | no |
| `wave9/eu_sdg_07_20` | Parquet | 591 | no |
| `wave9/eu_sdg_07_30` | Parquet | 1,105 | no |
| `wave9/eu_sdg_07_40` | Parquet | 2,283 | no |
| `wave9/eu_sdg_07_50` | Parquet | 2,388 | no |
| `wave9/eu_sdg_09_10` | Parquet | 2,988 | no |
| `wave9/eu_sdg_09_30` | Parquet | 2,585 | no |
| `wave9/eu_sdg_09_40` | Parquet | 2,346 | no |
| `wave9/eu_sdg_09_50` | Parquet | 1,605 | no |
| `wave9/eu_sdg_09_60` | Parquet | 1,380 | no |
| `wave9/eu_sdg_09_70` | Parquet | 929 | no |
| `wave9/eu_sdg_11_11` | Parquet | 1,377 | no |
| `wave9/eu_sdg_11_20` | Parquet | 1,371 | no |
| `wave9/eu_sdg_11_40` | Parquet | 4,796 | no |
| `wave9/eu_sdg_11_52` | Parquet | 1,064 | no |
| `wave9/eu_sdg_11_60` | Parquet | 510 | no |
| `wave9/eu_sdg_12_10` | Parquet | 60 | no |
| `wave9/eu_sdg_12_21` | Parquet | 984 | no |
| `wave9/eu_sdg_12_31` | Parquet | 420 | no |
| `wave9/eu_sdg_12_41` | Parquet | 420 | no |
| `wave9/eu_sdg_12_51` | Parquet | 894 | no |
| `wave9/eu_sdg_12_61` | Parquet | 349 | no |
| `wave9/eu_sdg_13_10` | Parquet | 2,790 | no |
| `wave9/eu_sdg_13_11` | Parquet | 45 | no |
| `wave9/eu_sdg_13_21` | Parquet | 1,440 | no |
| `wave9/eu_sdg_13_31` | Parquet | 458 | no |
| `wave9/eu_sdg_13_40` | Parquet | 2,340 | no |
| `wave9/eu_sdg_13_50` | Parquet | 330 | no |
| `wave9/eu_sdg_13_70` | Parquet | 33 | no |
| `wave9/eu_sdg_13_70a` | Parquet | 308 | no |
| `wave9/eu_ten00003` | Parquet | 963 | no |
| `wave9/eu_ten00006` | Parquet | 1,870 | no |
| `wave9/eu_ten00030` | Parquet | 2,122 | no |
| `wave9/eu_ten00062` | Parquet | 2,419 | no |
| `wave9/eu_ten00106` | Parquet | 3,257 | no |
| `wave9/eu_ten00108` | Parquet | 596 | no |
| `wave9/eu_ten00110` | Parquet | 579 | no |
| `wave9/eu_ten00121` | Parquet | 5,784 | no |
| `wave9/eu_ten00122` | Parquet | 5,784 | no |
| `wave9/eu_ten00123` | Parquet | 5,772 | no |
| `wave9/eu_ten00124` | Parquet | 2,410 | no |
| `wave9/eu_ten00125` | Parquet | 5,302 | no |
| `wave9/eu_ten00126` | Parquet | 6,748 | no |
| `wave9/eu_ten00127` | Parquet | 5,784 | no |
| `wave9/eu_ten00129` | Parquet | 5,772 | no |
| `wave9/eu_ten00135` | Parquet | 3,222 | no |
| `wave9/eu_ten00136` | Parquet | 314 | no |
| `wave9/eu_ten00137` | Parquet | 424 | no |
| `wave9/eu_ten00138` | Parquet | 154 | no |
| `wave9/eu_ten00139` | Parquet | 425 | no |
| `wave9/eu_ten00141` | Parquet | 755 | no |
| `wave9/eu_tran_hv_frmod` | Parquet | 1,840 | no |
| `wave9/eu_tran_hv_frtra` | Parquet | 445 | no |
| `wave9/eu_tran_hv_ms_frmod` | Parquet | 2,205 | no |
| `wave9/eu_tran_hv_ms_frmod6` | Parquet | 2,580 | no |
| `wave9/eu_tran_hv_ms_psmod` | Parquet | 2,250 | no |
| `wave9/eu_tran_hv_psmod` | Parquet | 2,180 | no |
| `wave9/eu_tran_hv_pstra` | Parquet | 535 | no |
| `wave9/wb_ag_lnd_agri_k2` | Parquet | 9,576 | no |
| `wave9/wb_ag_lnd_agri_zs` | Parquet | 9,576 | no |
| `wave9/wb_ag_lnd_arbl_zs` | Parquet | 9,576 | no |
| `wave9/wb_ag_lnd_el5m_ru_k2` | Parquet | 9,576 | no |
| `wave9/wb_ag_lnd_el5m_ru_zs` | Parquet | 9,576 | no |
| `wave9/wb_ag_lnd_el5m_ur_k2` | Parquet | 9,576 | no |
| `wave9/wb_ag_lnd_el5m_ur_zs` | Parquet | 9,576 | no |
| `wave9/wb_ag_lnd_el5m_zs` | Parquet | 9,576 | no |
| `wave9/wb_ag_lnd_frst_k2` | Parquet | 9,576 | no |
| `wave9/wb_ag_lnd_frst_zs` | Parquet | 9,576 | no |
| `wave9/wb_ag_lnd_irig_ag_zs` | Parquet | 9,576 | no |
| `wave9/wb_ag_lnd_prcp_mm` | Parquet | 9,576 | no |
| `wave9/wb_ag_lnd_totl_k2` | Parquet | 9,576 | no |
| `wave9/wb_ag_lnd_totl_ru_k2` | Parquet | 9,576 | no |
| `wave9/wb_ag_lnd_totl_ur_k2` | Parquet | 9,576 | no |
| `wave9/wb_ag_srf_totl_k2` | Parquet | 9,576 | no |
| `wave9/wb_ag_yld_crel_kg` | Parquet | 9,576 | no |
| `wave9/wb_bx_gsr_ccis_cd` | Parquet | 9,576 | no |
| `wave9/wb_bx_gsr_ccis_zs` | Parquet | 9,576 | no |
| `wave9/wb_bx_klt_dinv_wd_gd_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_cft_accs_ru_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_cft_accs_ur_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_cft_accs_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_egy_prim_pp_kd` | Parquet | 9,576 | no |
| `wave9/wb_eg_elc_accs_ru_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_elc_accs_ur_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_elc_accs_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_elc_coal_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_elc_fosl_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_elc_hyro_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_elc_loss_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_elc_ngas_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_elc_nucl_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_elc_petr_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_elc_rnew_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_elc_rnwx_kh` | Parquet | 9,576 | no |
| `wave9/wb_eg_elc_rnwx_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_fec_rnew_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_gdp_puse_ko_pp` | Parquet | 9,576 | no |
| `wave9/wb_eg_gdp_puse_ko_pp_kd` | Parquet | 9,576 | no |
| `wave9/wb_eg_imp_cons_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_use_comm_cl_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_use_comm_fo_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_use_comm_gd_pp_kd` | Parquet | 9,576 | no |
| `wave9/wb_eg_use_crnw_zs` | Parquet | 9,576 | no |
| `wave9/wb_eg_use_elec_kh_pc` | Parquet | 9,576 | no |
| `wave9/wb_eg_use_pcap_kg_oe` | Parquet | 9,576 | no |
| `wave9/wb_en_atm_pm25_mc_m3` | Parquet | 9,576 | no |
| `wave9/wb_en_atm_pm25_mc_t1_zs` | Parquet | 9,576 | no |
| `wave9/wb_en_atm_pm25_mc_t2_zs` | Parquet | 9,576 | no |
| `wave9/wb_en_atm_pm25_mc_t3_zs` | Parquet | 9,576 | no |
| `wave9/wb_en_atm_pm25_mc_zs` | Parquet | 9,576 | no |
| `wave9/wb_en_bir_thrd_no` | Parquet | 9,576 | no |
| `wave9/wb_en_clc_drsk_xq` | Parquet | 9,576 | no |
| `wave9/wb_en_clc_mdat_zs` | Parquet | 9,576 | no |
| `wave9/wb_en_fsh_thrd_no` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_all_lu_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_all_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_all_pc_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_ch4_ag_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_ch4_bu_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_ch4_fe_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_ch4_ic_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_ch4_ip_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_ch4_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_ch4_pi_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_ch4_tr_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_ch4_wa_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_ch4_zg_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_ag_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_bu_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_fe_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_ic_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_ip_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_lu_df_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_lu_fl_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_lu_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_lu_ol_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_lu_os_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_pc_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_pi_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_rt_gdp_kd` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_rt_gdp_pp_kd` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_tr_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_wa_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_co2_zg_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_fgas_ip_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_n2o_ag_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_n2o_bu_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_n2o_fe_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_n2o_ic_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_n2o_ip_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_n2o_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_n2o_pi_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_n2o_tr_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_n2o_wa_mt_ce_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_n2o_zg_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_ghg_tot_zg_ar5` | Parquet | 9,576 | no |
| `wave9/wb_en_hpt_thrd_no` | Parquet | 9,576 | no |
| `wave9/wb_en_mam_thrd_no` | Parquet | 9,576 | no |
| `wave9/wb_en_pop_el5m_ru_zs` | Parquet | 9,576 | no |
| `wave9/wb_en_pop_el5m_ur_zs` | Parquet | 9,576 | no |
| `wave9/wb_en_pop_el5m_zs` | Parquet | 9,576 | no |
| `wave9/wb_en_pop_slum_ur_zs` | Parquet | 9,576 | no |
| `wave9/wb_en_urb_mcty_tl_zs` | Parquet | 9,576 | no |
| `wave9/wb_er_fsh_aqua_mt` | Parquet | 9,576 | no |
| `wave9/wb_er_fsh_capt_mt` | Parquet | 9,576 | no |
| `wave9/wb_er_fsh_prod_mt` | Parquet | 9,576 | no |
| `wave9/wb_er_gdp_fwtl_m3_kd` | Parquet | 9,576 | no |
| `wave9/wb_er_h2o_fwag_zs` | Parquet | 9,576 | no |
| `wave9/wb_er_h2o_fwdm_zs` | Parquet | 9,576 | no |
| `wave9/wb_er_h2o_fwin_zs` | Parquet | 9,576 | no |
| `wave9/wb_er_h2o_fwst_zs` | Parquet | 9,576 | no |
| `wave9/wb_er_h2o_fwtl_k3` | Parquet | 9,576 | no |
| `wave9/wb_er_h2o_fwtl_zs` | Parquet | 9,576 | no |
| `wave9/wb_er_h2o_intr_k3` | Parquet | 9,576 | no |
| `wave9/wb_er_h2o_intr_pc` | Parquet | 9,576 | no |
| `wave9/wb_er_lnd_ptld_zs` | Parquet | 9,576 | no |
| `wave9/wb_er_mrn_ptmr_zs` | Parquet | 9,576 | no |
| `wave9/wb_er_ptd_totl_zs` | Parquet | 9,576 | no |
| `wave9/wb_ic_elc_durs` | Parquet | 9,576 | no |
| `wave9/wb_ic_frm_bnks_zs` | Parquet | 9,576 | no |
| `wave9/wb_ic_frm_outg_zs` | Parquet | 9,576 | no |
| `wave9/wb_ie_ppi_engy_cd` | Parquet | 9,576 | no |
| `wave9/wb_ie_ppi_icti_cd` | Parquet | 9,576 | no |
| `wave9/wb_ie_ppi_tran_cd` | Parquet | 9,576 | no |
| `wave9/wb_ie_ppi_watr_cd` | Parquet | 9,576 | no |
| `wave9/wb_ie_ppn_engy_cd` | Parquet | 9,576 | no |
| `wave9/wb_ie_ppn_icti_cd` | Parquet | 9,576 | no |
| `wave9/wb_ie_ppn_tran_cd` | Parquet | 9,576 | no |
| `wave9/wb_ie_ppn_watr_cd` | Parquet | 9,576 | no |
| `wave9/wb_ip_ids_nrct` | Parquet | 9,576 | no |
| `wave9/wb_ip_ids_rsct` | Parquet | 9,576 | no |
| `wave9/wb_ip_tmk_nrct` | Parquet | 9,576 | no |
| `wave9/wb_ip_tmk_rsct` | Parquet | 9,576 | no |
| `wave9/wb_iq_cpa_pubs_xq` | Parquet | 9,576 | no |
| `wave9/wb_is_air_dprt` | Parquet | 9,576 | no |
| `wave9/wb_is_air_good_mt_k1` | Parquet | 9,576 | no |
| `wave9/wb_is_air_psgr` | Parquet | 9,576 | no |
| `wave9/wb_is_rrs_good_mt_k6` | Parquet | 9,576 | no |
| `wave9/wb_is_rrs_pasg_km` | Parquet | 9,576 | no |
| `wave9/wb_is_rrs_totl_km` | Parquet | 9,576 | no |
| `wave9/wb_is_shp_gcnw_xq` | Parquet | 9,576 | no |
| `wave9/wb_is_shp_good_tu` | Parquet | 9,576 | no |
| `wave9/wb_it_cel_sets` | Parquet | 9,576 | no |
| `wave9/wb_it_cel_sets_p2` | Parquet | 9,576 | no |
| `wave9/wb_it_mlt_main` | Parquet | 9,576 | no |
| `wave9/wb_it_mlt_main_p2` | Parquet | 9,576 | no |
| `wave9/wb_it_net_bbnd` | Parquet | 9,576 | no |
| `wave9/wb_it_net_bbnd_p2` | Parquet | 9,576 | no |
| `wave9/wb_it_net_secr` | Parquet | 9,576 | no |
| `wave9/wb_it_net_secr_p6` | Parquet | 9,576 | no |
| `wave9/wb_it_net_user_fe_zs` | Parquet | 9,576 | no |
| `wave9/wb_it_net_user_ma_zs` | Parquet | 9,576 | no |
| `wave9/wb_it_net_user_zs` | Parquet | 9,576 | no |
| `wave9/wb_nv_agr_totl_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_aedu_cd` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_aedu_gn_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_dco2_cd` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_dco2_gn_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_dfor_cd` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_dfor_gn_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_dkap_cd` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_dkap_gn_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_dmin_cd` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_dmin_gn_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_dngy_cd` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_dngy_gn_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_dpem_cd` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_dpem_gn_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_dres_gn_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_ictr_gn_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_nnat_cd` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_nnat_gn_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_svng_cd` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_svng_gn_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_svnx_cd` | Parquet | 9,576 | no |
| `wave9/wb_ny_adj_svnx_gn_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_gdp_coal_rt_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_gdp_frst_rt_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_gdp_minr_rt_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_gdp_ngas_rt_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_gdp_petr_rt_zs` | Parquet | 9,576 | no |
| `wave9/wb_ny_gdp_totl_rt_zs` | Parquet | 9,576 | no |
| `wave9/wb_se_enr_prsc_fm_zs` | Parquet | 9,576 | no |
| `wave9/wb_se_prm_cmpt_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_dyn_mort` | Parquet | 9,576 | no |
| `wave9/wb_sh_h2o_basw_ru_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_h2o_basw_ur_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_h2o_basw_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_h2o_smdw_ru_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_h2o_smdw_ur_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_h2o_smdw_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_med_cmhw_p3` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_airp_p5` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_bass_ru_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_bass_ur_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_bass_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_hygn_ru_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_hygn_ur_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_hygn_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_maln_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_odfc_ru_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_odfc_ur_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_odfc_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_pois_p5` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_pois_p5_fe` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_pois_p5_ma` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_smss_ru_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_smss_ur_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_smss_zs` | Parquet | 9,576 | no |
| `wave9/wb_sh_sta_wash_p5` | Parquet | 9,576 | no |
| `wave9/wb_si_pov_dday` | Parquet | 9,576 | no |
| `wave9/wb_sp_pop_grow` | Parquet | 9,576 | no |
| `wave9/wb_sp_pop_totl` | Parquet | 9,576 | no |
| `wave9/wb_sp_urb_grow` | Parquet | 9,576 | no |
| `wave9/wb_sp_urb_totl` | Parquet | 9,576 | no |
| `wave9/wb_sp_urb_totl_in_zs` | Parquet | 9,576 | no |
| `wave9/wb_tm_val_fuel_zs_un` | Parquet | 9,576 | no |
| `wave9/wb_tm_val_ictg_zs_un` | Parquet | 9,576 | no |
| `wave9/wb_tm_val_mmtl_zs_un` | Parquet | 9,576 | no |
| `wave9/wb_tx_val_fuel_zs_un` | Parquet | 9,576 | no |
| `wave9/wb_tx_val_ictg_zs_un` | Parquet | 9,576 | no |
| `wave9/wb_tx_val_mmtl_zs_un` | Parquet | 9,576 | no |
<!-- wave10:end -->

## Brief 30 additions (2026-11-05)

| Dataset / table | Built by | What | Size (measured) |
|---|---|---|---|
| `outlines/aliases` | `scripts/build_outlines.py aliases` (wave8 `Oaliases`) | other names of Overture divisions (English and EU languages, official and short forms), with the name index's columns; `alias_norm` sorted with a bloom filter | 634,255 rows, 34.7 MB |
| `outlines/names` (`name_norm` added) | `build_outlines.py names` | the precomputed normal form the backend matches on | 3,397,857 rows, 129.0 MB |
| `rollups/<dataset>__<table>_r<res>` | `scripts/build_rollups.py` (wave8 `U`) | per H3 cell (res 5, 6, 7) and up to three text columns: `n` and sums of capacity-like columns of every positioned table of 1 M rows or more | see the job summary |
| `history/<dataset>__<table>` (partition `snapshot`) | `scripts/snapshot_tables.py` (`history.yml`, weekly) | copies of room-to-connect, queue and register tables, one partition per date, never overwritten | grows weekly |
| `rasters/wave9/<id>.tif` | `scripts/wave9.py` kind `raster` | COGs of the wave rasters (fire danger, sea level rise, bathymetry, vessel density, climate projections...), measures in `agent/rasters_waves.yaml` | see `data/wave9_built/` |

Per-table metadata (`TableInfo.meta` in `scripts/lake.py`, in each Parquet file's KV metadata and
in `lake/_catalog.json`): `as_of` (the source's own date: stated in the registry, or the
file's Last-Modified) with `as_of_basis`, and `refresh` (scripts/freshness.py).
