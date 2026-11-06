# Wave 9: the 12 failed builds, probed and fixed (2026-11-04)

Each source of `scripts/wave9_sources.yaml` whose build failed in the last Actions run was probed
from a cloud sandbox with the project's honest User-Agent (`InfraAtlas (github.com/...)`). "Local
build" means `scripts/wave9.py build --id <id> --lake <temp dir>` with no upload, and no
tippecanoe on hand, so tiles were skipped. The Actions build is the one that counts.

Changes to `scripts/wave9.py`:

- `read_json` for the `json`, `socrata` and `odata` kinds samples every record
  (`sample_size = -1`), so a key that first appears late in the file is part of the schema.
- `ckan`: when the API returns a list (`package_list` gives names only), the build stops with a
  clear message instead of an AttributeError.
- `shp_zip` / `gpkg_zip` / `geojson_zip` take `all_files: true`, which reads every layer file
  of the zip and stacks them. `src_file` names the file each row comes from.
- `arcgis` takes `fields`, the ArcGIS `outFields`. The default is `*`.

## fr_georisques_ssp (cat 1): fixed

- Error: `download failed: https://files.georisques.fr/SSP/ssp_casias_instruction.zip`.
- Probe: that file answers HTTP 404 (and `files.georisques.fr/` answers 403). The download page
  `sites-et-sols-pollues-ou-potentiellement-pollues` reads its links from
  `webappReport/ws/telechargement/basol`, whose national entry is
  `webappReport/ws/infosols/export/shapefile?national=true`. That URL serves a 9.6 MB zip
  (`Export_complet_instructions_National_20261104.zip`) holding two shapefiles: 8,289 polygon
  instructions and 4,142 point instructions, with no `cd_metier` in both. The licence is
  Licence Ouverte (linked from the page).
- Change: `kind: shp_zip`, the new URL, `all_files: true`, `level: polygon`.
- Local build: 12,431 rows (8,289 + 4,142). A few source records carry bad coordinates, for
  example `SSP000906901` in Reims at -133.6, -88.3. They are kept as published.

## world_port_index (cat 6): blocked

- Error: `download failed` for the MSI CSV.
- Probe: the CSV, `api/publications/world-port-index?output=csv` and `/Publications/WPI` all
  answer HTTP 503 with "MSI IS CURRENTLY UNDER MAINTENANCE". This is an outage, not a refusal.
- Change: `status: blocked`, with a `why` (HTTP 503, 2026-11-04) and a `request`. Set the status
  back to `build` when MSI is back up.

## eu_emodnet_msp_zoning (cat 6): fixed

- Error: `Failed to read GeoJSON data`.
- Probe: WFS 2.0.0 reports `numberMatched="4257"`. One page of 500 features as GeoJSON is
  60 MB, so the whole layer is very large. A WFS 2.0.0 SHAPE-ZIP comes with the axes in
  lat/lon order (x range 24.6 to 65.8). WFS 1.0.0 SHAPE-ZIP is 80 MB with lon/lat order
  (x -21.5 to 28.0, y 24.6 to 65.8). Its DBF is ISO-8859-1, which DuckDB rejected ("Invalid
  unicode"), so the URL asks for `format_options=CHARSET:UTF-8`.
- Change: `kind: shp_zip`, the WFS 1.0.0 SHAPE-ZIP URL with UTF-8.
- Local build: 4,257 rows. The shapefile format cuts field names to 10 characters, so
  `drawpriority` becomes `drawpriori`.

## eu_emodnet_substrate (cat 6): fixed

- Error: `Could not open GDAL dataset ... src.geojson`.
- Probe: `EMODnetGeology:seabed_substrate_1m` is now an unknown feature type, so the server
  answered with an XML exception. The layer moved to `gtk:seabed_substrate_1m` on
  `drive.emodnet-geology.eu/geoserver/wfs` (67,254 features, native EPSG:3857). The WFS 1.0.0
  SHAPE-ZIP with `srsName=EPSG:4326` and UTF-8 is 151 MB.
- Change: `kind: shp_zip`, the new layer and URL. Field names are cut to 10 characters
  (for example `original_s`, `folk_16cl_`).
- Local build: 67,254 rows.

## nl_cbs_solar (cat 5): fixed

- Error: `.../85005NED/TypedDataSet: HTTP 500`.
- Probe: the v1 TypedDataSet answers 200 to `$top=9999` but 500 to any `$skip` (it has 28,476
  rows). The OData v4 `datasets.cbs.nl/odata/v1/CBS/85005NED/Observations` pages with
  `$top=10000&$skip=10000` (HTTP 200) and has `$count` 78,944. It is long format: one row per
  measure code, region and period.
- Change: `kind: odata` and the v4 Observations URL.
- Local build: 78,944 rows.

## us_nyc_ll84 (cat 5): fixed in wave9.py, needs the Actions build

- Error: `JSON transform error ... record 30486 ... unknown key "eligible_for_certification_for_report_ped_y_n_"`.
- Probe: Socrata leaves null keys out of each record, so the key set changes from row to row.
  `$select=count(*)` gives 103,259 rows. The JSON is about 10 MB per 1,000 rows, so the whole
  dataset is about 1 GB. That is too large to build here.
- Change: `sample_size = -1` in the `socrata` (and `json`, `odata`) `read_json`. A synthetic test
  (30,000 rows, then one with a new key): without the setting the key is missing; with it, it is
  read.

## pt_ine_bgri (cat 0): blocked

- Error: `BadZipFile: File is not a zip file`.
- Probe: `mapas.ine.pt/download/...` and the download index answer 302 to
  `autenticacao.ine.pt/manutencao.html` ("Site em manutenção", 2026-11-04), so the build saved
  an HTML page. dados.gov.pt has no national BGRI 2021 copy (`q=BGRI 2021`: 0 results).
- Change: `status: blocked`, with a `why` and a `request`. Rebuild when INE is back. The
  licence is still `check`.

## cz_zsj (cat 0): fixed

- Error: `Could not open GDAL dataset ... Zakladni_sidelni_jednotky_20260701.gpkg`.
- Probe: the 63 MB `gpkg.zip` holds a shapefile (23,605 records) and an empty 100 kB GeoPackage
  stub.
- Change: `kind: shp_zip`.
- Local build: 23,605 rows, bbox 12.09, 48.55, 18.86, 51.06.

## at_zaehlsprengel (cat 0): fixed

- Error: 0 features were read from the 213 MB INSPIRE zip (a single GML), so tippecanoe found no
  geometry.
- Probe: the OGD catalogue entry `OGDEXT_ZSP_1` (CC BY 4.0) links the open WFS
  `gs-open/GEODATA/ows ... typeName=GEODATA:STATISTIK_AUSTRIA_ZSP_20260101&outputFormat=SHAPE-ZIP&format_options=CHARSET:UTF-8`.
  It is a 43 MB zip with a shapefile (the URL redirects from statistik.gv.at to statistik.at).
- Change: the new URL and `lic_url`.
- Local build: 8,842 rows, bbox 9.53, 46.37, 17.16, 49.02.

## gb_ssen_opendata (cat 2): fixed

- Error: `'list' object has no attribute 'get'`. The registry pointed at CKAN `package_list`.
- Probe: `package_show?id=embedded_capacity_register` lists the licence CC-BY-4.0 and monthly
  CSV and XLSX resources. "SSEN ECR Part 1 - 1MW October 2026 CSV" has 1,317 rows. The 50 kW CSV
  is a separate file (1,486 rows) that DuckDB cannot sniff.
- Change: `kind: ckan`, `package_show`, `fmt: csv`, `match: 'Part 1 - 1MW'`, eastings and
  northings in EPSG:27700, and the title "SSEN embedded capacity register".
- Local build: 1,317 rows, 1,245 of them with a position.

## gb_hnpd (cat 12): fixed

- Error: `StopIteration` in the header search.
- Probe: the workbook has the sheets `Definition Sheet` (108 x 5, at most 2 cells filled per
  row) and `HNPD` (1,506 x 56). The build picked the first sheet.
- Change: `sheet: HNPD`.
- Local build: 1,505 rows, 1,495 of them with a position.

## us_blm_solar_dla (cat 1): fixed

- Error: `404 Not Found` from `gis.blm.gov/.../lands/BLM_Natl_Solar_Energy_Zones/MapServer/0`.
- Probe: that service answers "Service not found", and the `lands` folder no longer lists it.
  BLM EGIS publishes the "BLM Solar Energy Zone" layer as
  `services1.arcgis.com/KbxwQRRfWyEYLgp4/.../Energy_Designations/FeatureServer/10` (153
  features, item terms: provided "as is", cite BLM). Its field `ogc_fid` clashes with GDAL's own
  (`duplicate column name "ogc_fid"`).
- Change: the new URL, `fields: 'zone_name,stateoffice,status,comments,Shape__Area,Shape__Length'`
  and the title "BLM solar energy zones".
- Local build: 153 rows.
