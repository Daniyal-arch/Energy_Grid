# Batch A: page-only sources (cat 4, 6, 12), probed 2026-11-04/05

Registry entries: `batch_a.yaml` (same folder). Decisions: 20 build (10 raster, 10 table or vector),
2 blocked, 1 left_out, 1 not_published.

Probes ran from the sandbox through the proxy with curl and Python, using HEAD, ranged reads for
files over 50 MB and DuckDB `read_csv` for the CSVs. Nothing over 200 MB was downloaded. The largest
download was 59 MB (USGS NSHM).

Three things wave9.py does not do yet:
- `member` for csv_zip: eu_jrc_coastal_flood needs it, and the landslide point file would too.
- A zip-in-zip reader for us_smu_heat_flow.
- A raster kind.

## Cat 4: physical risk

### eu_eshm20 (build, csv)
- **What I found:** the EFEHR hazard web service (`efehrappsrvr.ethz.ch/share/map`) has a "values within a rectangle" call that returns a whole map as text. The settings used:
  - ESHM20 is model id 81.
  - PGA, rock with Vs30 800 m/s, arithmetic mean.
  - Annual exceedance probability 0.002103, the 475-year return period (WMS layer hmap1846).
- **Probe:**
  - HTTP 200, 3,249,745 bytes, about 4 s.
  - Header `# longitude; latitude; PGA`, first row `8.8821339; 52.1; 0.0030882678`.
  - DuckDB reads 100,636 rows on a 0.1° grid.
  - The WCS returns only RGB-rendered TIFFs. WFS has no feature types.
- **Licence:** the repository LICENSE (https://gitlab.seismo.ethz.ch/efehr/eshm20/-/raw/master/LICENSE) says "Licence: creativecommons cc-by 4.0" and "The use of any of these files without proper citation violates the CC-BY 4.0 license". The README's DC.license meta tag says "CC BY-SA 4.0", but its DCTERMS URI points to by/4.0. Either way, commercial use is allowed.

### us_usgs_nshm (build, sciencebase to shp_zip)
- **What I found:** the registry item 648b570e… answers 404 ("Item not found"). The 2023 NSHM ground-motion maps are in item 64ff886dd34ed30c2057b4d9.
- **The file:** `US_PGA_2Pct_5Pct_10Pct_50Yrs_BC.zip` (59,162,562 bytes). It holds polygon and arc contour shapefiles for 2 %, 5 % and 10 % in 50 years, in WGS 84.
  - The largest .shp is `US_PGA_2Pct50Yrs_BC_poly`, with 4,072 polygons in the 10 % layer.
  - Fields: `low_cont`, `high_cont`, `range_cont` (g), `valley`.
- **Gridded values:** the CSVs of the revised R2 release (item 691dfb9a…) are in 1.9 GB zips per site class, too big to fetch.
- **Licence:** the FGDC use constraint (file HazardMapsAndGISdata_2023.xml) says "The data are not to be used for areas outside the United States. Acknowledgment of the U.S. Geological Survey … would be appreciated". The distribution liability says the product is "for the most part, … in the public domain". The parent item 67f8202a… says "marked with the Creative Commons Zero v1.0 Universal (CC0-1.0)".
- **Level:** I changed it from raster to polygon, because the file is contour polygons.

### world_nex_gddp (raster)
- **What I found:** the anonymous S3 listing works. There are 35 model folders.
- **Sample file:** `tasmax_day_ACCESS-CM2_ssp245_r1i1p1f1_gn_2015_v2.0.nc`, 247,692,873 bytes. I read only its header, by ranged requests:
  - NetCDF4 with dimensions time 365 × lat 600 × lon 1440, float32, in K.
  - lat runs -59.875..89.875, lon 0.125..359.875, at 0.25°.
- **Licence:** the AWS Open Data Registry entry (https://raw.githubusercontent.com/awslabs/open-data-registry/main/datasets/nex-gddp-cmip6.yaml) says "As of September 2022, all NEX-GDDP-CMIP6 outputs are made available under a blanket Creative Commons Zero license (CC0) license." The file attribute `cmip6_license` still reads CC-BY-SA 4.0. Both allow commercial use.

### eu_cds_indicators (blocked)
- **Probe:** the process description is public (HTTP 200). `POST /api/retrieve/v1/processes/sis-heat-and-cold-spells/execution` answers 401 `{"title":"permission denied","detail":"authentication required"}`.
- **Licence:** the catalogue link is "CC-BY licence https://spdx.org/licenses/CC-BY-4.0".
- **What it needs:** a CDSAPI_KEY from a free ECMWF account.

### eu_edo_cdi (raster)
- **What I found:** a public directory at `drought.emergency.copernicus.eu/data/Drought_Observatories_datasets/EDO_Combined_Drought_Indicator/ver4-1-1/`. It has one NetCDF and one GeoTIFF zip per year.
- **Probe of the 2026 files:**
  - NetCDF: 3,000,257 bytes, variable `cdinx` uint8, (29, 1, 1200, 1824).
  - EPSG:4326 at 0.041667°, extent -25..51 E, 22..72 N.
  - Legend: 0 no drought, 1 watch, 2 warning, 3 alert, 4 recovery, 5 and 6 temporary recovery, 7 and 8 no data.
  - The zip (2,761,286 bytes) holds 31 dekadal GeoTIFFs.
- **Licence:** copyright.txt says "Any copyright and/or sui generis right on the dataset is licensed under the Creative Commons Attribution 4.0 International (CC BY 4.0) licence … Reuse is allowed provided appropriate credit is given".
- **Conflict:** the NetCDF `10_CITATION_STATEMENT` attribute says "Reproduction for non-commercial purposes is authorised, provided the source is acknowledged". This contradicts copyright.txt, the `09_LICENSE` attribute ("Creative Commons Attribution v4") and the JRC catalogue page (CC BY 4.0, "even commercially"). I kept it as build on CC BY 4.0 and flagged it.

### us_usfs_whp (raster)
- **What I found:** the RDS catalog page links `RDS-2015-0047-4_Data.zip`, 368,424,961 bytes (accept-ranges: bytes).
- **Zip contents,** listed by ranged reads:
  - `Data/whp2023_GeoTIF/whp2023_cnt_conus.tif` (143 MB, continuous index).
  - `whp2023_cls_conus.tif` (23 MB, classes 1-7).
  - AK and HI files.
  - The .tfw gives 270 m cells, origin (-2362500, 3267540).
- **CRS:** projected metres. I did not read the exact projection, because the GeoTIFF IFD sits at the end of a deflated member.
- **Licence:** the RDS use constraint (https://www.fs.usda.gov/rds/archive/products/RDS-2015-0047-4/_metadata_RDS-2015-0047-4.html) says "These data were collected using funding from the U.S. Government and can be used without additional permissions or fees."

### us_usfs_whp_service (raster)
- **Probe:** the ImageServer `?f=json` answers 200:
  - pixelSizeX 270, S32, 1 band, min 0, max 144153.
  - EPSG:3857, capabilities Image, Metadata, Catalog, Mensuration.
- `identify` at -120.5, 38.5 returned value 5854.
- `exportImage` with tiff/S32 returned a 200 × 200 GeoTIFF of 263 KB.
- **Licence:** the same as the RDS terms. The old "CC BY 4.0 (USFS)" in the registry is not supported: the service's copyrightText is only a funding credit.

### eu_effis_danger (raster)
- **What I found:** WMS GetMap on `maps.effis.emergency.copernicus.eu/gwis` with `LAYERS=ecmwf.fwi&FORMAT=image/tiff&TIME=2026-08-01` returns real values:
  - 200 image/tiff, 1,081,318 bytes.
  - float32, max 154.6, EPSG:4326, at 0.1° as requested.
  - TIME runs from 2018-01-01.
- The `effis` endpoint named in the download instructions (layer ecmwf007.fwi) answers "LayerNotDefined".
- **Licence:** https://forest-fire.emergency.copernicus.eu/about-effis/data-license says "content owned by the EU on this website is licensed under the Creative Commons Attribution 4.0 International (CC BY 4.0) licence. This means that reuse is allowed".

### eu_jrc_coastal_flood (build, csv_zip with a new `member` option)
- **What I found:** the JRC catalogue links `jeodpp…/LISCOAST/10012/LATEST/`. It holds `globalESLprojections.zip` (13,351,354 bytes) with 21 CSVs, plus NetCDFs of 2-17 MB.
- **Probe:** `ESL_100RP_Baseline.csv` has the header `latitude,longitude,valueMedian,value5th,value95th`. DuckDB reads 20,865 global coastal points. The NetCDF units are m.
- **Option needed:** csv_zip currently takes the largest CSV, so it needs a `member` option.
- **Licence:** copyright.txt carries the same CC BY 4.0 text as EDO.
- **Level:** I changed it from raster to point.

### us_noaa_slr (raster)
- **What I found:** `coast.noaa.gov/slrdata/` lists depth rasters per state as COGs, with URL lists.
- **Probe of `DE_slr_depth_3ft.tif`** (400,959,766 bytes; I read only the IFD):
  - BigTIFF, float32, 51,766 × 29,940, tiles of 128.
  - NAD83 (EPSG:4269), pixel 2.695e-5°, nodata -3.4028e38.
  - Depth in m above ground.
- **Other files:** vectors come as FileGDB zips per state (DE 31.8 MB, the 0.5-ft version 99 MB). The `dc_slr/slr_3ft` MapServer has a "Low-lying Areas" polygon layer (54 features) and a raster depth layer.
- **Licence:** no licence statement was found. InPort item 48106 gives only use constraints: "These data should be used only as a screening-level tool… The dataset is provided 'as is'". It is a US federal work.

### us_usgs_landslides (build, sciencebase to csv_zip)
- **What I found:** a newer version, v3 (item 671eef1f…, February 2025). Its files:
  - `US_Landslide_v3_csv.zip` (24,398,680 bytes).
  - A GeoPackage of 1.39 GB and shapefiles of 639 MB.
- **CSV zip contents:** `us_ls_v3_poly.csv` (295 MB, 680,497 rows of polygon centroids) and `us_ls_v3_point.csv` (119 MB). The columns are `fid,USGS_ID,Date_Min,Date_Max,Fatalities,Confidence,LS_Type,Inventory,Inv_URL,Info_Source,Notes,Lat_N,Lon_W`.
- The README says "These data are in projection WGS 1984".
- **Licence:** "This work is marked with Creative Commons Zero v1.0 Universal".

### us_usgs_geoelectric (build, sciencebase to csv)
- **What I found:** the registry item 5d0a0e6c… answers 404. The current USGS geoelectric product on ScienceBase is item 68781e6d…, "Estimated peak geoelectric field strengths during a Carrington-class magnetic storm". Its file `E-max-Carrington.csv` is 286,079 bytes, with 1,616 sites.
- **Columns:** `name1, rlong1, rlat1, p value, a, b, sig, Eh, Eh-, Eh+`. The values are space-padded text, and TRY_CAST to DOUBLE works.
- **Unit:** the FGDC metadata gives Eh's unit as "V/km". The sample values are in the hundreds to thousands; that is shown as published.
- **Licence:** "marked with the Creative Commons Zero v1.0 Universal (CC0-1.0) public domain dedication".

## Cat 6: offshore and marine

### world_gebco (raster)
- **What I found:** GEBCO_2026 links on CEDA. The GeoTIFF zip is 4,241,629,269 bytes (HEAD), 15 arc-seconds, elevation in m, EPSG:4326 in 8 tiles. The TID grid is 92 MB.
- **Licence:** https://www.gebco.net/data-products/gridded-bathymetry-data says "The GEBCO Grid is placed in the public domain and may be used free of charge."

### eu_emodnet_bathy (raster)
- **What I found:** WCS 2.0.1 at `ows.emodnet-bathymetry.eu/wcs` with coverages `emodnet__mean` and 2016-2022.
- **Probe:** a 1° tile from GetCoverage was 200 image/tiff, 4,194,720 bytes:
  - 960 × 960 float32 in EPSG:4326, -71.8..-5.1 m.
  - DescribeCoverage gives the full grid as 108,960 × 75,840.
- **Licence:** data.europa.eu "Digital Terrain Model 2018" lists the licence https://creativecommons.org/licenses/by/4.0/. The WCS says AccessConstraints NONE.

### eu_emodnet_vessel_density (raster)
- **What I found:** WCS `ows.emodnet-humanactivities.eu/wcs` with coverage `emodnet__vesseldensity_allavg`, time 2017-2024, EPSG:3857.
- **Probe:** with X/Y subsets, GetCoverage returned 200 image/tiff (137 × 137 float32, median 1.43). Axis labels E/N are refused with "InvalidAxisLabel", and unencoded quotes cause an HTTP 400.
- **Units:** "hours per square kilometre per month", on a 1 km grid.
- **Licence:** the ISO record 0f2f3ff1… says "No limitations on public access" and "Creative Commons CC-BY 4.0 https://creativecommons.org/licenses/by/4.0/".

### us_marinecadastre_ais (raster)
- **What I found:** marinecadastre.gov/downloads answers 404. The ArcGIS item af6d042a… links the direct GeoTIFF `ais-transit-count-2024.tif`.
- **Probe:** 465,949,438 bytes. I read the IFD only:
  - uint32, 126,318 × 51,893, 100 m pixels.
  - WGS 84 Web Mercator auxiliary sphere, nodata 0.
- The yearly MapServers for 2019-2025 answer identify with a pixel value (7 near New York).
- **Licence:** the item licenseInfo says "The information on government web pages is in the public domain" (17 U.S.C. 403 notice).

### gb_tce_offshore_wind (left_out)
- **What I found:** the hub search API lists FeatureServers. `WindSite_EngWalNI_TheCrownEstate` layer 0 has 72 features, with fields Name_Prop, Name_Ten, Wind_Round, Lease_Stat, Inf_Status and km2.
- **Licence:** The Crown Estate Open Data Licence (GIS) v1.1 (item 22a1be6f…) restricts reuse. The licensee must:
  - "do not copy, use or reproduce the Open Data … on or in connection with a website or portal that is concerned with the provision of the same or similar services" (4.3 d);
  - "use the Open Data only in the ordinary course of your business" (4.3 e);
  - "do not resell the Open Data … or make any commercial gain directly from the provision of the Open Data to a third party" (4.3 f).
  - The licence is also "revocable".
- The Round 4/5/6 layers use the Public Data Licence instead. The owner needs to decide.

### us_usseabed (build, shp_zip with urls)
- **What I found:** the "extracted" (EXT) point shapefiles in three zips:
  - Atlantic DS 118: `atl_ext.zip`, 3,286,042 bytes.
  - Gulf of Mexico DS 146: `gmx_ext.zip`, 2,571,768 bytes, 51,289 points.
  - Pacific DS 182: `pac_ext.zip`, 1,087,605 bytes.
- **Fields:** LATITUDE, LONGITUDE, WATERDEPTH, GRAVEL, SAND, MUD, CLAY, GRAINSIZE, SORTING, SEABEDCLS, FOLKCODE, CARBONATE, ORGCARBON, POROSITY and more.
- **CRS:** the .prj is NAD27 geographic.
- **Access note:** pubs.usgs.gov answers 403 to Python-urllib's default user agent, but 206 to the project UA (`InfraAtlas (github.com/…)`).
- **Licence:** gmx_cmpmeta.txt says "Public domain data from the U.S. Government are freely redistributable with the proper metadata and source attribution."

### us_noaa_mpa (build, arcgis)
- **What I found:** the inventory page links ArcGIS item eb2b36ae…, which points to FeatureServer `NOAA_MPA_Inventory_2023`, layer 0.
- **Probe:** 981 polygons, maxRecordCount 2000. A sample row is Walrus Islands State Game Sanctuary, with IUCNcat IV and AreaKm 755.65.
- **Other files:** the xlsx/zip links return a 301 to a blob store.
- **Licence:** the item licenseInfo has only a disclaimer ("Data are not to be used for navigation…"). It is a US government work, so public domain.

## Cat 12: heat and storage

### world_ihfc_heat_flow (build, csv_zip)
- **What I found:** the old panmetaworks URL and dataservices.gfz-potsdam.de reset the connection. DataCite points to https://dataservices.gfz.de/10.5880/fidgeo.2024.014. The files are listed at `datapub.gfz.de/download/10.5880.FIDGEO.2024.014-VEueRf/`.
- **The file:** `GHFBD-R2024_v.2026-03.zip` (18,510,789 bytes). It holds a tab-separated .txt (39 MB) and an .xlsx.
- **Probe:** the column names are on line 13 (7 comment lines, then 5 metadata rows). With skip 12, tab and cp1252 decoding, DuckDB reads 91,182 rows: q (mW/m²), q_uncertainty, name, lat_NS, long_EW and more.
- **Licence:** in the file header: "# Licence: Creative Commons Attribution 4.0 International". DataCite has the same.

### us_smu_geothermal (not_published)
- The SMU lab's Data and Maps pages (HTTP 200) have no data files. The data were moved to GDR submission 1704 (see us_smu_heat_flow).

### us_smu_heat_flow (build, needs a zip-in-zip reader)
- **What I found:** `Download Data Files.zip` is 377,962,305 bytes (accept-ranges: bytes). It contains `Combined Sources into Each Data Type/core.template_heatflow_materialized.zip` (19 MB). I extracted that inner zip with ranged reads.
- **Probe:** it holds `core.template_heatflow_materialized.csv` (75 MB). Its columns include ObservationURI, WellName, State, LatDegreeWGS84, LongDegreeWGS84, SiteHeatFlow, HeatFlowUnits, BHT, BHTCorrectedValue and Interval…HeatFlow.
- **Licence:** the submission JSON-LD gives `"license": "https://creativecommons.org/licenses/by/4.0/"`.

### world_anu_phes (blocked)
- **Probe:** re100.eng.anu.edu.au/global answers 200, but the data download is the Shortlisting Tool at https://re100.anu.edu.au/shortlisting/, which needs Register/Login ("Accounts are also used to manage user permissions within the tool"). The map layers are rendered WMS only.
- **Licence:** the only statement is "please acknowledge the RE100 Group, Australian National University". There is no reuse licence.

### dk_district_heating (build, geojson)
- **What I found:**
  - The ENS English GIS page answers 404.
  - The Danish `…/download-gis-filer` pages answer 403 with "Adgang nægtet" (Drupal access denied; robots.txt allows the site).
  - data.europa.eu lists Plandata.dk's "Forsyningsområde - PlanDK" under CC BY 4.0 (dataset 29~~2).
- **Probe:** the WFS layer `pdk:theme_pdk_forsyningomraade_vedtaget_v` reports numberMatched 6,263. A full GeoJSON GetFeature returned 30,053,133 bytes and 6,263 features in 3 s.
- **Fields:**
  - `vaerdi1203`: Fjernvarme, Individuel naturgasforsyning, Anden, or Fremtidigt uspecificeret forsyningsområde.
  - `navn1203`.
  - `forsytekst`, the supplier.
  - `komnr`.
- **Licence:** data.europa.eu gives "Creative Commons Attribution 4.0 International" for both distributions. The WFS says AccessConstraints NONE.
