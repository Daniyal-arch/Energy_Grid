# Wave 9 page-only sources, batch C (probed 2026-11-04/05)

Replacement entries: `batch_c.yaml` (same folder). Probes ran with curl and Python from the sandbox, with the
User-Agent `InfraAtlas data probe (github.com/Daniyal-arch/Energy_Grid)`. No keys were used or printed.

| Decision | Count | Ids |
|---|---|---|
| build | 26 | nl_rdw_vehicles, de_kba_districts, us_afdc_registrations, fr_ore_solar_commune, nl_cbs_solar, gb_desnz_subregional_fit, fr_ademe_dpe*, ie_seai_ber (via CSO), us_cpc_degree_days, eu_egdi_minerals, us_epa_agstar, eu_salt_caverns*, us_usaspending_doe, us_ira_energy_communities, gb_ons_income_msoa, us_nrel_sharing_sun, eu_broadband_coverage, eu_eea_wei, us_usgs_nwis_sites, eu_tent_network, gb_srn, us_fhwa_afc, eu_eea_aq_stats*, gb_defra_aurn*, fr_enedis_interruptions, us_eia861_reliability |
| blocked | 5 | gb_mcs_heat_pumps, us_clean_investment_monitor, eu_glofas (raster), world_iaea_pris, world_black_marble (raster) |
| not_published | 8 | eu_eba_biomethane, eu_eib_projects, us_doe_lpo, eu_jtf_territories, eu_rescoop, gb_ea_abstraction, us_epa_cwns, gb_ofgem_interruptions |
| left_out | 2 | gb_ea_abstraction_licences, world_overture_rail |

\* needs a change in `scripts/wave9.py`: new kinds `datafair_agg` (fr_ademe_dpe), `parquet` (eu_salt_caverns),
`aqviewer` (eu_eea_aq_stats), and a nested lon/lat option for the `json` kind (gb_defra_aurn). `raster` is a
record-only kind for eu_glofas and world_black_marble.

---

## nl_rdw_vehicles: build (json)
- The vehicle register `m9d7-ebf2` has 16,884,127 rows and no owner municipality, so the municipality level does not exist. The level is now `country`.
- The fuel table `8ys7-d773` grouped by the Socrata API: `$select=brandstof_omschrijving,count(*)&$group=...` answered HTTP 200 with 9 rows, e.g. Benzine 11,309,160; Elektriciteit 2,964,183; Diesel 2,602,652. A vehicle with two fuels is counted once per fuel.
- Licence: the metadata API gives `"license" : "Public Domain"` and `"Licentie" : "Creative Commons 0 (CC0)"`. Commercial use is allowed.

## de_kba_districts: build (xlsx, pandas, sheet FZ1.2)
- The page links to `fz1_2024.xlsx`. The probe found `fz1_2026.xlsx` (HTTP 200, 291,477 B, 1 January 2026, published 22 April 2026).
- Sheet FZ 1.2: passenger cars per Zulassungsbezirk. Columns: Insgesamt, Benzin, Diesel, Gas, Hybrid insgesamt, darunter Plug-in-Hybrid, Elektro (BEV), sonstige, Euro 1...
- The header has two rows. The pandas reader takes row 8, so the first five columns come out as col_0..col_4 (blank, Land, Regierungsbezirk, "08111 STUTTGART,STADT", Insgesamt).
- Licence: the Impressum sheet says "Nutzungsbedingungen: © Kraftfahrt-Bundesamt, Flensburg, Datenlizenz Deutschland - Namensnennung - Version 2.0". Commercial use is allowed.

## us_afdc_registrations: build (xlsx, range B3:C54)
- File: `10962-ev-registration-counts-by-state_9-06-24.xlsx` (HTTP 200, 30,283 B), 2023 counts per state, e.g. Alabama 13,047; California 1,256,646.
- Sheet notes: "Vehicle registration counts derived by the National Renewable Energy Laboratory with data from Experian Information Solutions." "Only all-electric vehicles are included", and "Registration counts are approximate."
- Row 55 is a `=SUM` formula, so the range leaves it out. The file needs no NREL_API_KEY.
- Licence: none is stated. The AFDC disclaimer covers accuracy only. This is a U.S. DOE publication of Experian-derived counts, so the licence is recorded as found.

## gb_mcs_heat_pumps: blocked
- `datadashboard.mcscertified.com` is a Blazor WebAssembly shell (6.3 kB HTML). It has no file or API.
- mcscertified.com/about-the-mcs-data-dashboard says "Image and data exports are also available for download from each visualisation" and "Unique ID and timestamps are added to downloads". These exports run only in the browser, and no licence is stated.
- Request: MCS, installations per local authority and month as an open file.

## fr_ore_solar_commune: build (csv_gz, sep ;)
- ORE left Opendatasoft. The old explore API answers HTTP 410: "Cette couche de compatibilité ... ne supporte pas cette requête".
- The data-fair catalogue lists "Registre national ... (au 31/05/2026)", id `3f6et1q09oarxn7afaj0reop`, 141,589 rows.
- `/raw` answers 200 with `application/gzip`, 6,764,682 B, file name `registre-national-installation-production-stockage-electricite-agrege.csv.gz`.
- First columns: nominstallation; codeeicresourceobject; codeiris; codeinseecommune; commune; ... filiere; puismaxinstallee; nbinstallations.
- Licence: "Licence Ouverte / Open Licence version 2.0" (etalab.gouv.fr). Commercial use is allowed.

## nl_cbs_solar: build (odata, v4 Observations)
- The v1 ODataApi `TypedDataSet` now answers 200 (28,476 rows), but `$skip` returns HTTP 500 ("only available on the ODataFeed endpoint").
- ODataFeed returns Atom XML unless the query has `$format=json`, and the odata kind's params replace the query string.
- The v4 `datasets.cbs.nl/odata/v1/CBS/85005NED/Observations` returns JSON and pages: `$top=10000&$skip=70000` gave 8,944 rows, so there are 78,944 in all.
- Measures: M002460 Installaties (aantal), M002461 panel capacity (kWp), M008184 inverter capacity (kW), M007785 production (mln kWh).
- Licence: Properties `License: https://creativecommons.org/licenses/by/4.0/`. The CBS copyright page says the content "is subject to Creative Commons Attribution (CC BY 4.0)".

## gb_desnz_subregional_fit: build (govuk)
- `statistics/solar-photovoltaics-deployment` now redirects to Energy Trends section 6.
- `statistics/regional-renewable-statistics` holds the attachment "Renewable electricity by local authority, 2014 to 2025" (xlsx, 3,446,115 B), with sheets "LA - Capacity, 2025" ... "LA - Capacity, 2014".
- The header is on row 3: Local Authority Code, Name, Region, Country, Estimated number of households, Onshore Wind, ..., Solar PV, ... Total.
- Licence: OGL v3 (gov.uk statistics). Commercial use is allowed.

## fr_ademe_dpe: build (new kind datafair_agg)
- `dpe03existant` holds 15,893,454 certificates with 230 columns, far over 200 MB, so it is not downloaded whole.
- `values_agg?field=code_departement_ban;etiquette_dpe&agg_size=120;8&size=0` answers 200 with 104 départements, each split by label. Example: dept 75 has 859,073 certificates (D 265,636, E 233,499, C 192,192, ...).
- The answer is nested JSON, so the counts need a small flattening kind.
- Licence: "Licence Ouverte / Open Licence version 2.0". Commercial use is allowed.

## ie_seai_ber: build via CSO (jsonstat EBQ03)
- The SEAI BER research tool's terms (TnC.pdf) say access needs "an automated email registration with SEAI" and "The Database may be used for personal, research or education purposes". That is registration-only and non-commercial, so it is not used.
- CSO PxStat table EBQ03 ("Domestic Building Energy Ratings", updated 2026-10-23) answers 200 (29.3 MB). Dimensions: BER rating × dwelling type × main heating fuel × county/Dublin postal district (53) × renewable installation × quarter.
- The table has 5,698,560 cells, of which 1,617,964 are filled. The CSV endpoint answers 403. `jsonstat_rows` should skip empty cells.
- Licence: CSO, CC BY 4.0, the same as ie_cso_saps_heating.

## us_cpc_degree_days: build (csv, sep |, skip 3)
- The legacy statewide folder is empty. `daily_data/2025/StatesCONUS.Heating.txt` answers 200 (46,969 B).
- Format: 3 header lines (Product, Regions, Weights: Population), then `Region|20250101|...`, with rows AL..WY (48 states plus DC and others; 52 lines).
- The cooling file sits next to it.
- Licence: weather.gov/disclaimer says "NWS Web pages are in the public domain ... may be used without charge for any lawful purpose".

## us_clean_investment_monitor: blocked
- The database page links no file. The about page says the data are on ClimateDeck.
- ClimateDeck: "Create a free, secure account to browse and download data." Its licence is CC BY ("permits adaptation and reuse (including commercially)"), but an account is required.

## eu_egdi_minerals: build (geojson via WFS with filter)
- `data.geus.dk/egdi` redirects to maps.europe-geology.eu. The data.geus.dk WFS answered HTTP 513: "msPostGISLayerOpen(): Query error. Database connection failed".
- `maps.europe-geology.eu/wfs/` serves `ms:egdi_mineraloccurr_critical_raw_materials_2023` with 28,500 features. The full GeoJSON is 26,571,308 B.
- Fields: inspireid, name, country, deposit_type, inspire_commodity, crm_2023, mine_status, reserves, resources, longitude, latitude...
- Licence: the EGDI metadata record (572a0113) gives CC BY 4.0, but "The Polish Data uses CC BY-NC-ND 4.0". Poland has 278 rows, so an fes FILTER `country != Poland` leaves 28,204.
- The metadata page timed out from the sandbox. The quote is from its indexed text, which the build agent should re-check.

## us_epa_agstar: build (xlsx)
- `agstar-livestock-ad-database.xlsx` answers 200 (98,977 B), "based on data available through June 2024".
- Sheet "Operational and Construction" has 473 rows: Project Name, Project Type, City, County, State, Digester Type, Status, Year Operational, Animal/Farm Type(s), Cattle, Dairy, ..., Biogas End Use(s).
- There are no coordinates, so the level is now county.
- Licence: EPA disclaimers say data are "by default in the public domain".

## eu_eba_biomethane: not_published
- The EBA page redirects to the 2020 publication page, which links PDF posters only.
- GIE lists the 2025 map as a PDF. The GIE footer reads "Copyright © 2025-2026 GIE All Rights Reserved".

## eu_salt_caverns: build (new kind parquet)
- Zenodo record 18153129 (Modelblocks, CC BY 4.0) holds `h2_salt_cavern_storage.parquet` (237,805 B).
- Contents: 119 polygons in WGS 84 with columns kwh_per_m3, gwh_per_km2, storage_type. They were "recreated for the PyPSA-Eur model" from Caglayan et al. 2020.
- The record states CC-BY 4.0 for the file.

## eu_eib_projects: not_published
- The EIB loans page has no export link.
- The IATI registry lists `eib-act` → `eib.org/en/about/partners/cso/iati/activity.xml` (200, 6.1 MB, generated 2025-05-16, licence id `other-at`). It covers non-EU lending only (top recipients UA, TR, RS, MA, EG) and is XML.

## us_usaspending_doe: build (csv_zip)
- The S3 listing `files.usaspending.gov/award_data_archive/?prefix=FY2025` holds `FY2025_089_Assistance_Full_20261006.zip` (5,329,764 B, 200).
- The zip holds one CSV (28 MB, 65,487 lines). First columns: assistance_transaction_unique_key, assistance_award_unique_key, award_id_fain, ..., federal_action_obligation, total_obligated_amount.
- The file is renamed monthly.
- Licence: U.S. federal spending data. The about page is a JavaScript app (3 kB), so no licence quote was captured.

## us_doe_lpo: not_published
- `energy.gov/lpo/portfolio-projects` redirects to `/edf/edf-projects` ("EDF Projects", last updated October 28, 2026).
- The list is an H5P iframe sourced from `lpoapps.loanprograms.energy.gov`. curl failed TLS verification there ("unable to get local issuer certificate"), and this was not bypassed. No file is linked.

## us_ira_energy_communities: build (arcgis)
- EDX package `ira-energy-community-data-layers` has zips of 68.7 MB (MSA) and 77.1 MB (coal closure), both open (206).
- The lighter ArcGIS layer `Hosted/2024_MSAs_NonMSAs_that_are_Energy_Communities/FeatureServer/0` has 901 polygons with fields geoid_cty_2020, county_name_2020, state_name, msa_area_name, ffe_ind_qual, ec_ind_qual, ec_qual_status...
- Licence (item licenseInfo): "License: Creative Commons Attribution. This allows for the re-distribution and re-use of this work on the condition that this content is appropriately credited."

## eu_jtf_territories: not_published
- A cohesiondata Socrata catalogue search for JTF, territories and NUTS returns JTF budgets, payments and indicators, but no territory list.
- Web search found no official CSV of JTF NUTS 3 territories.

## gb_ons_income_msoa: build (xlsx, pandas, sheet "Total annual income")
- The FYE 2023 `datasetfinal.xlsx` answers 200 (1,863,497 B). The header is on row 3: MSOA code, MSOA name, Local authority code/name, Region code/name, Total annual income (£), Upper/Lower confidence limit (£), Confidence interval (£). 7,264 rows.
- Licence (Terms sheet): "© Crown copyright 2025 ... You may re-use this information (not including logos) free of charge in any format or medium, under the terms of the Open Government Licence".

## us_nrel_sharing_sun: build (xlsx, sheet "Project List")
- `data.nrel.gov` is refused by the sandbox proxy (CONNECT 502). The lab is renamed and `data.nlr.gov/submissions/244` answers 200.
- The September 2026 xlsx is 1,408,536 B with 4,810 projects. Columns: Utility ID, Project Name, City, State, Utility, Utility Type, ..., System Size (MW-AC), ..., Year of Interconnection.
- Licence (`/node/244/license`): "The user is granted the right, without any fee or cost, to use or copy the Data, provided that this entire notice appears in all copies ... credit DOE/NLR/ALLIANCE". The names may not be used for endorsement. Commercial use is allowed.

## eu_rescoop: not_published
- `/members` answers 404. `/network` (200) shows a map of HTML cards with no export or API. The footer reads "© 2026 REScoop.eu".

## eu_broadband_coverage: build (csv, Eurostat isoc_cbs)
- The digital-strategy page now returns "Page not found".
- data.europa.eu points to Eurostat `isoc_cbs` (broadband coverage by speed). SDMX-CSV answers 200 (109,570 B, 1,404 rows). Columns: freq, unit (PC_HH), inet_spd (MBPS_GT2/30/100, GBPS_GT1, GBPS_GT1_UD), terrtypo, geo, TIME_PERIOD, OBS_VALUE.
- Licence: Eurostat CC BY 4.0.

## eu_eea_wei: build (xlsx)
- The old datahub item answers 404. The SDI record b16bd284 "WEI+ at sub unit level, 2023" points to a Nextcloud share. A WebDAV PROPFIND lists `WEI_2000_2023_SDI_SubunitScale.xlsx` (1,749,149 B) and `WEIplus-subunit-level-SHP.zip` (105,075,023 B, over 50 MB and not downloaded).
- The xlsx sheet "Seasonal wei_subunit_scale" has 21,006 rows: countryCode, spatialUnitIdentifier (AT1001 ...), year, quarter, totalWaterAbstraction, totalWaterReturn, netWaterConsumption, changeReservoirStorage...
- Licence: "License CC-BY 4.0 ... Copyright holder: European Environment Agency (EEA)."

## gb_ea_abstraction: not_published
- The old environment.data.gov.uk id returns an empty 5 kB page.
- data.gov.uk has only EA abstraction statistics (Defra S3 CSVs per charge region, 2000-2015, OGL). Open per-licence data exist only for Northern Ireland (DAERA FeatureServer, OGL) and Wales (NRW).
- Web search confirmed that the EA does not publish licence points.

## gb_ea_abstraction_licences: left_out
- The xlsx (79,779 B, v1.4 January 2022) is the EA's register of data-licence abstracts: 122 datasets with their licence (EA Conditional Licence or OGL), conditions and attribution text. It holds no water abstraction data.

## us_epa_cwns: not_published
- The 2022 data sit only in the APEX app `sdwis.epa.gov/ords/sfdw_pub/r/sfdw/cwns_pub/data-download`.
- The download buttons for "Nationwide 2022 CWNS Dataset" open a dialog, "Help us learn more about who uses our data", whose URLs carry a session id and checksum (`cs=`). There is no stable link.

## us_usgs_nwis_sites: build (csv, urls per state)
- The legacy waterservices RDB still answers, but it needs a state per call.
- The new OGC API `api.waterdata.usgs.gov/ogcapi/v1/collections/monitoring-locations/items?f=csv` returns 200. Limits: "Limit of 50000 exceeded" (400) and "offset parameter must be less than or equal to 40000".
- Nationwide USGS stream sites exceed 50,000, so the entry uses one call per state: CA 6,734 rows (2.76 MB), TX 3,045, RI 351.
- Columns: x, y, id, agency_code, monitoring_location_number, monitoring_location_name, state_code, county_name, site_type_code, hydrologic_unit_code, drainage_area...
- Licence: "USGS-authored or produced data and information are considered to be in the U.S. public domain".

## eu_glofas: blocked (raster)
- The EWDS catalogue API answers 200: daily data 1979-01-01 to 2026-11-01, global bbox 0-360 E, 70 S-70 N.
- The process inputs are system_version (4_0, 5_0), product_type, variable (average_river_discharge_in_the_last_24_hours ...), data_format (grib2, netcdf) and area.
- Retrieval needs a (free) ECMWF account and `CDSAPI_KEY`, which is unset. Grid resolution, CRS and file size could not be read without a request and are not stated.
- Licence (CEMS-floods PDF): "users are granted free access ... for the following purposes: (a) reproduction; (b) distribution; (c) communication to the public; (d) adaptation, modification and combination". There is no non-commercial clause.

## eu_tent_network: build (arcgis)
- The TENtec portal URL answers 404. webgate `TENTEA/tentec_public_corridors_GL2024` (the 2024 regulation) answers 499 "Token Required", so it was not used.
- The public `TENTec/tentec_public_services_ext/MapServer` has layer 8 "Railways" (Comprehensive Network) with 4,767 sections and fields COUNTRY_CODE, CORE_NETWORK, CORRIDORS, TYPE, RAILWAYS_ACTIVITY. Roads are layer 7 (3,488). GeoJSON queries answer 200.
- Copyright text: "© European Commission - DG MOVE". The Commission legal notice says EU-owned content "is licensed under the Creative Commons Attribution 4.0 International (CC BY 4.0) licence".

## gb_srn: build (arcgis)
- The old data.gov.uk id answers 404. The data.gov.uk search finds only a 2016 Data Mill North shapefile.
- ArcGIS Online item 4b64217e "Network Model (Public)" (NationalHighways_Spatial, "updated daily") has Link layer 1 with 43,040 polylines and fields linkid, linkref, numberoflanes, smartmotorway, roadname, srn, startdate, enddate...
- Licence (item): "Contains public sector information licensed under the Open Government Licence v3.0."

## us_fhwa_afc: build (arcgis)
- The FHWA_HEPGIS FeatureServer `AltFuels_rounds1_8/0` has 2,275 polylines. Fields: AFC_NUMBER, ROADTYPE, STATE, EV_ROUND, EV, CNG..., HY, Len_miles, NOT_NHS. Snippet: "Updated 8/27/2024 with CA updates".
- Licence: U.S. DOT federal data (public domain). The item has no licence text.

## world_overture_rail: left_out
- Release `2026-10-21.0` has 128 segment parquet files, 72.47 GB in all.
- A DuckDB read of part-00000 over HTTPS found rail segments (1,404). The only `rail_flags` values were is_abandoned, is_bridge, is_disused, is_tunnel, is_covered and is_passenger, and the class is gauge only.
- There is no electrification attribute, so the dataset cannot serve the family. Eurostat `eu_rail_electrified` already covers it.

## world_iaea_pris: blocked
- `pris.iaea.org` redirects to `pris-stats.iaea.org`, an Angular single-page app ("PRIS Analytics") with no file.
- `www.iaea.org/about/terms-of-use` answers HTTP 403 to the honest client. No licence could be read.

## eu_eea_aq_stats: build (new kind aqviewer)
- The AQViewer `init?fqn=Airquality_Dissem.b2g.AirQualityStatistics` reports 6,565,203 rows and MaxDownloadSize 100,000.
- A POST to `download?fqn=...&f=csv` with `RequestFilter {Country: Malta, ReportingYear: 2024}` answered 200 with `DataExtract.csv.zip` (718 lines).
- Columns: Country, Air Quality Network, Station EoI Code, Station Name, Sampling Point Id, Air Pollutant, Data Aggregation Process, Year, Air Pollution Level, Unit, Data Coverage, Verification, Station Type, Station Area, Longitude, Latitude, Altitude...
- Filters on CountryCode or YearOfStatistics fail with "InvalidFieldException" because those fields are not queryable.
- Licence (EEA legal notice): material "may be re-used without prior permission, free of charge, for commercial or non-commercial purposes, provided that the EEA is always acknowledged".

## gb_defra_aurn: build (json; nested lon/lat needed)
- The network-info page has no CSV. The UK-AIR SOS `sos-ukair/api/v1/stations?expanded=false` answers 200 (451,205 B, 2,448 features).
- Each feature has `{properties: {id, label: "Aberdeen Erroll Park-Nitrogen dioxide (air)"}, geometry: {coordinates: [57.1574, -2.0948, "NaN"]}}`, with latitude first.
- Licence (uk-air site footer): "Open Government Licence v3.0, except where otherwise stated."

## fr_enedis_interruptions: build (csv via data-fair lines)
- data.enedis.fr redirects to opendata.enedis.fr (data-fair), and the old dataset is gone.
- The only per-département dataset is "Indicateur réglementaire continuité d'alimentation" (94 rows): the % of HTA and LV customers beyond the regulatory thresholds, with columns 2009 to 2024. `lines?format=csv` answers 200.
- The minutes indicators ("Durée moyenne de coupure par client BT/HTA", 18 rows) are national only.
- Licence: "Licence Ouverte / Open Licence version 2.0".

## us_eia861_reliability: build (xls, member Reliability_2025)
- `f8612025.zip` answers 200 (4,756,816 B) and contains `Reliability_2025.xlsx` (204,957 B). It supersedes `us_eia861_reliability_xlsx` (2024).
- Licence: EIA, public domain (copyrights_reuse page, as in the registry).

## gb_ofgem_interruptions: not_published
- The data portal page "energy-network-indicators" (200) shows "Customer interruptions and minutes lost: Electricity distribution (RIIO-ED1)" as a Highcharts chart (`/sites/default/files/highcharts/XEOWFmq0o.png`).
- The page links no CSV or xlsx, and `.../XEOWFmq0o.json` answers 404.

## world_black_marble: blocked (raster)
- The LADS listing is open: VNP46A4 has years 2012-2025. 2025/001 holds 540 HDF5 tiles, 53.08 GB in all (e.g. h00v01 180 MB, h00v03 77.6 MB).
- Each file answers HTTP 303 to `/profiles/licenses/...` (Earthdata login), and `NASA_EARTHDATA_TOKEN` is unset. CRS, resolution, band and unit were not read from a file.
- Licence (Earthdata data use guidance): "While there are no restrictions on the use of these data, data users are very strongly urged to cite the data used".
