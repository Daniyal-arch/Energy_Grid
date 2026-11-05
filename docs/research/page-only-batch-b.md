# Batch B: page-only sources, probe notes (2026-11-04/05)

All probes ran from the cloud sandbox through its proxy with the honest User-Agent
`InfraAtlas/0.7`. No refusal was bypassed. No download went over 82 MB. Decisions: 12 build,
5 blocked, 7 not_published, 2 left_out.

## it_terna_province: blocked (licence)
- dati.terna.it download centre: `POST /api/sitecore/dati/downloadcenter/recordsv2` with a JSON body. With `filterDataset=ElectricalEnergy, filterYear=2024, orderByColumn="Consumo (GWh)", db=dati` it answered HTTP 200 with 428 rows. Columns: `Anno, Regione, Provincia, Settore, Consumo (GWh)`. Years 2000-2024. First row `[2024,"Lombardia","Brescia","Industria",8322.370384]`. A multi-year filter and the GET `records?f=xlsx` export both answer HTTP 500.
- Licence: none stated. The portal's "Note legali" link goes to https://developer.terna.it/API_Terms_of_Use, which says: "Il portale dovrà essere utilizzato esclusivamente per la fruizione dei servizi messi a disposizione da Terna sotto forma di API. Ogni altro uso non sarà ritenuto lecito." terna.it/en/legal-notes renders no text without JavaScript.
- If Terna grants a licence, this source needs a new POST-JSON kind (one request per year).

## ee_grid: build (geojson, WFS)
- The data.europa.eu entry "INSPIRE (SU) Estonian Statistical Grid (WFS)" leads to https://inspire.geoportaal.ee/geoserver/SU_ruutkaart/wfs, layer `SU_ruutkaart:SU.StatisticalGridCell`. resultType=hits gives numberMatched=45636. The full GeoJSON with `propertyName=code,geom` is 16,013,400 bytes and holds 45,636 features, coordinates in lon,lat order. Fields: `gml_id, code` (`EE_CRS_3035-RES_1000m-N3925000E5032000`). The cells carry no population ("unpopulated" void reasons).
- Licence: the metadata record a88e8751-... says "tingimusi ei rakendata" (no conditions apply) and "avaliku juurdepääsu piirangud puuduvad" (no public-access limits). The capabilities give Fees and AccessConstraints as "puudub" (none).

## us_fema_nfhl: build (arcgis, read in place)
- MapServer/28 "Flood Hazard Zones" answered HTTP 200. Polygons, source CRS 4269, maxRecordCount 2000, pagination supported, formats JSON/geoJSON/PBF. count=5,825,816. Fields: `GFID, OBJECTID, DFIRM_ID, FLD_AR_ID, STUDY_TYP, FLD_ZONE, ZONE_SUBTY, SFHA_TF, STATIC_BFE, DEPTH, ...`. Filtering by area works (`DFIRM_ID='06001C'` gives 2,451).
- Licence: US federal work (17 U.S.C. 105). www.fema.gov answered HTTP 403 to the probe, so no FEMA page was quoted.
- wave9.py needs an "in place / no lake copy" option. Without it, the `arcgis` kind would page all 5.8 M features.

## gb_nsta_pipelines: left_out (non-commercial)
- The hub search API answers 401. The ArcGIS Online search finds owner NSTA_GIS. Layer `UKCS_offshore_infrastructure_pipeline_linear_(WGS84)/FeatureServer/1` answered: polyline, count 9,025. Fields: `FEATURE_ID, NSTAPIPNO, PIPE_NAME, INF_TYPE, FLUID, STATUS, DIAMETERMM, LENGTH_M, ...`.
- Licence: the item says "NSTA Open User Licence", which links to the NSTA User Agreement June 2023 (PDF). Its terms: "You are free to: copy, publish, distribute and transmit the Information; adapt the Information; exploit the Information non-commercially." The NSTA terms page links the same PDF as "NSTA Open User Licence". It is not OGL.

## us_natcarb: build (shp_zip)
- https://edx.netl.doe.gov/dataset/natcarb-sink redirects to /user/login. However, the EDX CKAN `package_search?q=natcarb` answers without a login and lists 30+ packages, and the storage URLs download without one.
- `saline10k_1502.zip`: HTTP 200, 7,964,208 bytes, unzips to 99 MB. 186,675 cells. Fields: `COL_ROW, PARTNERSHI, RESOURCE_N, BASIN_NAME, RSC_AREA_C, VOL_LOW, VOL_MED, VOL_HIGH, DEPTH_FT, THICKNESS_, ...`. The .prj is "Lambert Azimuthal Equal-area" (lat0 45, lon0 -100, WGS84) with no EPSG code, so the entry gives a PROJ string.
- The 2022 update zip (25 MB) unzips to a 1.45 GB .dbf. It was rejected and deleted.
- Licence: the EDX record has license_id None. NETL is a DOE laboratory, so the data are treated as a US federal work. The metadata only says "See access and use constraints information".

## us_epa_class_vi: not_published
- The EPA page (HTTP 200) links only the PDF `class-vi-permit-tracker_9-25-26.pdf` (340,959 bytes, application/pdf). The permit table page has no `<tr>` table and no xlsx/csv. On ArcGIS Online, only a third party (NWF) has a "Class VI Wells" layer.

## de_wind_areas: not_published
- The BNetzA Wind an Land page answers HTTP 404. data.europa.eu "Windenergiegebiete" returns 26 hits, all Land-level or foreign. No federal dataset exists.
- NRW publishes `Windenergiebereiche-Regionalplanung-NRW_EPSG25832_Geodatabase.zip` (HTTP 200, 1,208,859 bytes) under dl-de/zero-2-0 (GovData DCAT). It is a candidate for its own NRW entry and would need a gdb_zip kind.

## us_doe_nietc: not_published
- The GDO and OE NIETC pages (HTTP 200) link no zip, kmz, shp or service, only FAQs, the four-phase document and a mailto. All 20 NIETC layers on ArcGIS Online have third-party owners (Audubon, Urban Observatory, and others).

## gb_scotland_npf4: not_published
- Spatial Hub CSW `AnyText='NPF4'` returns numberOfRecordsMatched=1 ("Historic Environment Records - Scotland"). Searches for "National Planning Framework" return superseded wind spatial frameworks (SPP 2014, local plans) and no NPF4 layer.

## us_gnatsgo_farmland: left_out (size, raster)
- The NRCS page sent an empty reply (curl 52) and an HTTP/2 INTERNAL_ERROR. Planetary Computer `gnatsgo-rasters` (licence "CC0-1.0") has 502 STAC items, each a 16384x16384 COG mukey tile at 10 m. `gnatsgo-tables/mapunit` is a parquet file that holds `farmlndcl`. A SAS token endpoint answers without an account.
- Mapping the farmland class means mosaicking the mukey raster and joining the table. That is far above the 200 MB limit, and wave9.py has no raster kind for it.

## us_epa_repowering: build (xlsx)
- The mapper page links `re-powering-screening-dataset-2022 Updated.xlsx`: HTTP 200, 81,715,268 bytes (82 MB, over the 50 MB notice threshold). The download was deleted after the sample.
- Sheets: Attributes, Screening Criteria, RE-Powering Sites (190,977 rows including the header, 50 columns), Sheet2.
- Columns: `Cross-Reference Number, EPA Region, State, Program, Site ID, Site Name, ..., Estimated PV Capacity (MW), ..., Distance to Nearest Substation (miles), ..., Latitude, Longitude`.
- A geodatabase zip is also published (44,642,271 bytes).
- Licence quote (EPA disclaimers): "Unless otherwise specified, geospatial data produced by the EPA is by default in the public domain and is not subject to domestic copyright protection under 17 U.S.C. § 105."

## us_epa_frs_cleanups: build (arcgis, two layers)
- The FRS national files are too big: `national_combined.zip` is 1,374,821,998 bytes and `national_single.zip` is 356,921,646 bytes.
- The geopub EMEF/efpoints MapServer offers layer 0 Superfund (count 1,322) and layer 5 Brownfields (count 44,602). maxRecordCount 10000, pagination supported. Fields: `registry_id, site_id, primary_name, location_address, city_name, county_name, state_code, epa_region, postal_code, latitude, longitude, pgm_sys_acrnm, pgm_sys_id, fips_code, facility_url`.
- RCRA corrective action is not a separate layer.
- Licence: as for us_epa_repowering.

## us_nass_land_values: blocked (key; bulk file denied)
- The Quick Stats API needs a key. On https://www.nass.usda.gov/datasets, `qs.economics_20260926.txt.gz` answers HEAD 403 and GET 404 with an empty body and the header `x-nass-file-access: denied`. Readme.txt also answers 404.

## gb_pins_dco: build (csv)
- `/api/projects` answers 404. The project search page links `/api/applications-download`: HTTP 200, text/csv, `applications.csv`, 226,349 bytes, 295 rows.
- Columns: `Project reference, Project name, Applicant name, Application type, Region, Location, Grid reference - Easting, Grid reference - Northing:, GPS co-ordinates, Stage, Description, ..., Date of decision, Date withdrawn`.
- Licence quote (terms page): "Most content on National Infrastructure Projects is subject to Crown copyright protection and is published under the Open Government License (OGL)."

## de_netzausbau: blocked (licence)
- The registry URL answers 404. The netzausbau.de map (`Vorhaben/uebersicht/karte/karte.html`) reads these layers:
  - `services-eu1.arcgis.com/TJm8oSvOdJUQvQT5/.../Monitoring_gdb/FeatureServer/0` (Vorhaben_BBPlG, polyline, 157) and `/1` (Vorhaben_EnLAG, 26). Fields: `Vorhaben, Typ, Vorhabenst, Vorhabennu, Link, Technik, Spannung, Zuständigk, ...`.
  - `Vorhabenpunkte` (205) and `Anbindungsleitungen` (5).
- Licence quote (Impressum): "Alle Inhalte dieser Website ... sind urheberrechtlich geschützt. Das Urheberrecht liegt ... bei der Bundesnetzagentur. Bitte kontaktieren Sie uns, falls Sie die Inhalte dieses Internetangebots verwenden wollen." The ArcGIS items carry no licence. The "Merkblatt Geodaten" is about data the TSOs supply to BNetzA and is not a reuse licence.

## gb_neso_etys: build (shp_zip)
- NESO CKAN `q=etys` finds one package, etys-gb-transmission-system-boundaries. Its zip `etys-boundary-gis-data-mar25.zip` answered HTTP 200 (87,714 bytes). It holds a shapefile of 34 lines with fields `Boundary_n, ID`. The .prj is WGS 84 Web Mercator, so `crs: EPSG:3857` is set explicitly.
- Licence quote (NESO Open Data Licence): "exploit the Information commercially and non-commercially ... You must ... Acknowledge NESO as the source".
- No ETYS circuit or reinforcement tables are on the portal.

## eu_entsoe_tariffs: not_published
- `/data/transmission-tariffs/` answers 404. The news item of 2026-10-08 links only two PDFs under `mc-documents/transmission-tariffs/`: `l_260404_entso-e_TTO_2024_02.pdf` and `l_260405_entso-e_TTO_2025_03.pdf`.

## gb_ssen_opendata: build (ckan)
- The current registry entry (already updated to kind ckan) is confirmed.
- `package_show?id=embedded_capacity_register` answered HTTP 200, licence CC-BY-4.0. The "SSEN ECR Part 1 - 1MW October 2026 CSV" is 1,278,228 bytes and redirects to R2, then HTTP 200, 1,317 rows. Columns include `Customer Name, ..., Location (X-coordinate): Eastings (where data is held), Location (y-coordinate): Northings ..., Grid Supply Point, Bulk Supply Point, Primary, ..., Energy Source 1, ...`.

## se_svk_reserves: build (csv, SVK Data Service)
- Mimer `PrimaryRegulation/DownloadText?...` answered HTTP 200 with a CSV (`;`-separated, decimal comma, trailing "Summa" row). Mimer itself states no licence.
- SVK Data Service (https://data.svk.se, CKAN, "Ingen API-token krävs") has 10 packages, each with licence CC-BY-4.0 and license_url creativecommons by/4.0.
- `datastore/dump/6093d167-...?format=csv` (fcr_capacity_market_aggregated) answered HTTP 200 as an attachment CSV. The server gave no length. datastore_search reports total 439,314 rows.
- Columns: `_id, start_time_sweden, start_time_utc, reserve_product, reserve_direction, auction_round, price, price_unit, volume, volume_unit, soda_hashbyte, soda_identity`.

## eu_entsoe_balancing: build (ENTSO-E API, custom)
- No key in the sandbox. `web-api.tp.entsoe.eu/api` answered an Acknowledgement_MarketDocument without a key, so the endpoint is live.
- Parameters, per controlArea_Domain:

  | documentType | Content | Other parameters |
  |---|---|---|
  | A81 | Contracted reserves | businessType B95; processType A52 FCR / A51 aFRR / A47 mFRR; Type_MarketAgreement.Type A01 |
  | A82 | Accepted aggregated offers | processType A16 |
  | A83 | Activated balancing energy | processType A16 |
  | A84 | Prices of activated energy | processType A16 |
  | A85 | Imbalance prices | already built by scripts/build_lake_entsoe.py |
  | A86 | Imbalance volumes | |
  | A87 | Financial expenses/income | |
  | A88 | Cross-border balancing | |
  | A89 | Contracted reserve prices | |

- Licence as in the registry. The lic_url given is ENTSO-E's terms page and was not fetched in this probe.
- Needs a new kind, or an extension of build_lake_entsoe.py: XML zip parsing per area and window.

## us_iso_as_prices: build (csv_zip, CAISO OASIS)
- `SingleZip?queryname=PRC_AS&market_run_id=DAM&...&resultformat=6` returns application/x-zip-compressed. One day is 3,748 bytes. October 2026 is a 104,541-byte zip holding a 2,123,591-byte CSV.
- Columns: `INTERVALSTARTTIME_GMT, INTERVALENDTIME_GMT, OPR_DT, OPR_HR, OPR_INTERVAL, OPR_TYPE, ANC_TYPE, ANC_REGION, MARKET_RUN_ID, XML_DATA_ITEM, MW, GROUP`. No key needed.
- Licence quote (caiso.com/privacy-terms-of-use): "Materials and information that are freely available for public use consistent with the general policies of the Public Records Act ... may be used by you provided that you keep intact all copyright, trademark and other proprietary notices and that you credit the California ISO".
- No commercial restriction is stated. Other ISOs were not probed.

## gb_emr_cm_register: build (ckan, NESO)
- emrdeliverybody.com answers HTTP 403 (`/SitePages/Home.aspx`) and 404 (`/CM/Registers.aspx`).
- NESO package capacity-market-register (NESO Open Data Licence) has 8 CSV resources. "Components" is `component_20261104.csv`: a range request gave Content-Range total 8,331,296 bytes (HEAD answers 403, GET works).
- Columns: `Auction Name, Application ID, CMU ID, Delivery Year, Component ID, Type, Generating Technology Class, ..., De Rated Capacity, ..., Location and Post Code, OS Grid Reference, Number of Components`.

## us_pjm_rpm: blocked (terms unreadable)
- The RPM page (HTTP 200) links 262 xls/xlsx files. `rpm-auctions-resource-clearing-price-summary.xlsx` answered HTTP 200 (26,293 bytes). Its sheet RCP (201x21) has rows like `['BRA','*',40.8,...]` under "DY 07/08" headers, by LDA.
- `api.pjm.com` answers 401 (Data Miner 2 needs a key).
- No terms could be read: legal.aspx renders only navigation without JavaScript, and the terms and copyright URLs redirect to /not-found.

## it_terna_capacity: not_published
- The mercato-capacità page (HTTP 200) links 46 download.terna.it files. The results are PDFs, for example `Rendiconto-Esiti-Asta-Madre_2027_...pdf` (2,562,369 bytes, application/pdf). The only .xls files are upload templates.

## eu_aib_go: not_published
- The registry URL answers 404. `/facts/eecs-go-statistics` contains only `<div class="db-dashboard" data-id="01f05e83...">`, which the site's JS fills from `/api/dashboard` (a Databricks dashboard). No file is offered.

## gb_ofgem_rego: blocked (unreachable)
- `renewablesandchp.ofgem.gov.uk` failed twice with "CONNECT tunnel failed, response 502".
- ofgem.gov.uk "Public reports and data: REGO" (HTTP 200) says: "Details of generating stations accredited under the REGO scheme are published in the public reports section of the Renewable Electricity Register". It links no file.
- Re-probe from GitHub Actions.
