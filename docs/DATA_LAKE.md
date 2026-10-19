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
| ENTSO-E transmission outages A78 (`entsoe/transmission_outages`) | API | Parquet, partition fetched day | ~0.001 GB a day |
| Global Renewables Watch v1.0 (`grw/solar`, `grw/wind`) | GitHub release, 453 MB GeoPackages | GeoParquet (+ `grid/grw.pmtiles` public) | see the catalogue |
| Eurostat nrg_bal_c, EIA SEDS, EIA STEO | APIs | API | 0 |
| EDGAR 2025 booklet (`edgar/ghg_by_sector`) | xlsx | Parquet | 261,365 rows, 0.002 GB |
| JEPX spot (`jepx/spot`) | CSV per year | Parquet, partition year | 9,696 rows a year, 0.0005 GB |
| CENACE PML (`cenace/pml`) | web service | Parquet, partition date | 62,640 rows a day, 0.0003 GB |
| GHSL population 2025 (`ghsl/population`) | 484 MB zip | Parquet (+ `grid/population-0.1deg.i32` public, 26 MB) | 4,569 rows |
| Energy Institute review (`ei_review/series`) | xlsx via a browser (`browser-fetch.yml`), raw file in `sources/ei/` | Parquet, long | 277,731 rows, 0.0015 GB |

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
