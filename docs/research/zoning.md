# Zoning datasets: EU, UK, US (research log, started 2026-11-08)

Owner request (2026-11-08): find zoning datasets for every EU country, the UK and the USA, in
any form (web services, shapefiles, GML, spreadsheets, PDFs), convert them to geometry in the
lake, and keep plan texts and PDFs (or at least their metadata) where the agent can read them.

"Zoning" here covers two families:

1. **Land-use zoning**: legally binding local plans that assign each parcel a use class
   (France PLU `zone-urba`, German Bebauungsplan and Flächennutzungsplan, Dutch
   bestemmingsplan, Polish MPZP, Danish lokalplan and kommuneplanramme, US municipal zoning
   districts, UK local plan allocations and designations). INSPIRE theme "Planned Land Use"
   (PLU) is the EU-wide schema many of these are published in.
2. **Energy zoning**: areas designated for energy infrastructure: renewables acceleration areas
   (RED III Art. 15c, designation due 21 February 2026), German wind energy areas
   (Windenergiegebiete, WindBG § 6a, BauGB § 249c), maritime spatial plans (offshore wind
   zones; the lake already holds `wave9.eu_emodnet_msp_zoning`).

Plan: one source table per family and country where a national or regional service exists; a
unified `zoning.zones` table (geometry, country, authority, plan id, zone code, the source's
own zone label, a harmonised class, status, adopted date, document links, source, licence);
plan documents (PDF) stored privately on R2 with their text extracted into
`zoning.documents` (plan id, page, text) for the agent's full-text search. No values invented:
the harmonised class is a documented lookup from each source's own codes, and unmapped codes
stay `other` with the source label kept.

## Leads found (to probe before building)

| Country / area | Source | Form | Notes |
|---|---|---|---|
| France | Géoportail de l'Urbanisme, API Carto module GPU, resource `zone-urba` | REST, GeoJSON WGS84 | National, open licence; 5,000 features a request, so page by commune or tile. Regulation PDFs linked per document. |
| Germany | XPlanung / INSPIRE PLU WFS per state and city (Berlin, Hamburg, Hessen regional plans, Brandenburg, BW PlanAtlas) | WFS (GML) | No national service; state geoportals. Wind energy areas: Energieatlas NRW (gdb, WFS), MV LUNG shapefiles, Thüringen regional plans (shapefile). Licence mostly dl-de/by-2-0. |
| Austria | Vienna Flächenwidmung, INSPIRE PLU WFS | WFS | City; other Länder to check. |
| Netherlands | PDOK `kadaster/plu` (INSPIRE PLU, WMS) and `ruimtelijke-plannen` (Atom download) | Atom / WFS | CC0. Ruimtelijkeplannen.nl services are being phased out for the DSO (Omgevingswet); transition to 2032. |
| Denmark | Plandata.dk GeoServer `geoserver.plandata.dk/geoserver/wfs` (lokalplaner, kommuneplanrammer) | WFS, EPSG:25832 | National register (municipalities must report); terms to check. |
| Poland | MPZP per gmina (APP register, WFS `mpzp`, `mpzp_zasiegi`), e.g. Gliwice | WFS, SHP, CSV | No national aggregate found yet; check gov.pl APP / geoportal integration. |
| UK, England | planning.data.gov.uk: green belt, article 4 direction areas, conservation areas, local plan boundaries, ... | JSON / GeoJSON / CSV (files.planning.data.gov.uk) | OGL; incomplete coverage, flagged per dataset. England has no zoning in the legal sense; designations are the zoning equivalent. |
| UK, Scotland | Spatial Hub, Local Development Plans | WFS, downloads | Free account needed; national compilation "Other (Not Open)", many councils OGL. Edinburgh and North Lanarkshire missing. |
| Ireland | MyPlan (Department of Housing): Development Plan (Land Use) Zoning, Local Area Plan zoning, Generalised Zoning Types (GZT), expired plans | shapefile, CSV, KML, GeoJSON, GeoPackage; ArcGIS REST `maps.housing.gov.ie/arcgis/rest/services/MyPlan/...` | **National, CC BY 4.0**: every local authority's statutory zoning plus a harmonised scheme (GZT). Updated 2024-09 (expired-plan layer newer). |
| Spain | Sistema de Información Urbana (SIU, Ministry of Housing): land class, development areas | datos.gob.es `e05233601-siu-datos-graficos` | National; users report the download link failing; coverage incomplete. Regional portals as fallback. |
| UK, Wales | No national allocations layer found; Welsh Government development-plan coverage map; councils' LDP proposals maps (often PDF) | PDF, council GIS | Candidates for PDF georeferencing. |
| UK, Northern Ireland | OpenDataNI Settlement Boundaries (from the area plans) | shapefile | Last updated 2016; area plan zonings mostly PDF maps. |
| US | National Zoning Atlas state datasets (Mercatus compilation; state teams such as New Hampshire) | GeoJSON, CSV | Covers about 10 states by mid-2025. Cite Bronin et al. (2025), doi 10.4079/zoning-atlas. |
| Belgium, Flanders | Gewestplan (raster GeoTIFF, WMS); provincial RUPs as vector (`grondvlak` plan elements, DSI catalogue) | GeoTIFF, vector download | Gewestplan as vector to find; municipal RUPs per plan. |
| Belgium, Wallonia | Plan de secteur en vigueur (INSPIRE record 37502a64-868e-4e3d-bf66-31ff65a24a5a): `LU_PlannedLandUse_PDS.gml.zip` direct download; ArcGIS `geoservices.wallonie.be/arcgis/rest/services/AMENAGEMENT_TERRITOIRE/PDS/MapServer`; OGC API Features | GML (ETRS89-LAEA), GPKG, WMS | Regional, complete (digitised 1:10,000, 1994-2001). Indicative, no legal value per the portal. |
| Portugal | PDM land classification (SNIT, DGT); municipal open data such as Cascais `dadosabertos.cascais.pt/dataset/pdm-classificacao-do-solo`, dados.gov.pt `pdm-planta-de-classificacao-do-solo-ordenamento` | per municipality (GeoJSON, SHP) | No national WFS found; DGT SNIT holds the PDM documents (PDF). PDMs revised by 31 December 2024 for the new land classification rules. |
| Czechia | Územní plány in the single standard (vyhláška 360/2021, standard 2023: vector layer of `plochy s rozdílným způsobem využití` with national codes) | per kraj and municipality; national download not found | The standard gives one code list for every new plan, so a harmonised class is a direct lookup. |
| US, Massachusetts | MassGIS ZONING_POLY (all communities, about 2007, not maintained); city layers (Cambridge 2026, Worcester) | ArcGIS, shapefile | Statewide layer for regional analysis only, per MassGIS. |
| US, Connecticut | Connecticut Zoning Atlas (2,620 districts); city layers (Hartford GeoJSON) | to find export | Part of the National Zoning Atlas. |
| Italy | Regional only: Friuli Venezia Giulia PRG homogeneous zones (shapefile, 2001), Sicily SITR (shapefile + PDF by directive), Emilia-Romagna PRG database (2004); Torino zones restricted | shapefile | No national layer; Lombardy PGT per comune, to find. |
| Sweden | Lantmäteriet National Geodata Platform (NGP), Detaljplan | GeoPackage via NGP | Coverage growing (municipal agreements); PDF-only plans are outside the digital requirement. |
| Finland | City WFS: Helsinki `kartta.hel.fi/ws/geoserver/avoindata/wfs` (Kaavahakemisto_kaava_voimassa), Espoo, Vantaa | WFS, EPSG:3879 | Plan index with links to plan documents; Espoo stale (2016). |
| UK, England (more) | planning.data.gov.uk: 100+ datasets (brownfield land, conservation areas, article 4, tree preservation, ...) | CSV and GeoJSON per dataset; bulk download recommended | Check each dataset's coverage (providers). |
| US | City and county open-data zoning layers (NYC, SCAG Southern California parcels, Wisconsin statewide) | ArcGIS REST, shapefile | No free national layer; Regrid / LightBox zoning is commercial (out). |
| Spain, Catalonia | Mapa Urbanístic de Catalunya (MUC), Generalitat Territori; ArcGIS `gissrv.diba.cat/arcgis/rest/services/CARTOBASE/MUC/MapServer` | shapefile (updated 2023-01) | Region-wide classification and qualification of land; codes per Orden TES/195/2019. |
| Italy, Lombardy | PGT "Tavola delle previsioni" (all comuni, SIT integrato), Geoportale della Lombardia | WMS / WFS; GeoPackage download to check | Municipalities upload to one regional schema. |
| Estonia | Maa-amet "Digital layers of plans" (planeeringud), public detailed plans | WMS (WFS to check) | National register; Latvia (TAPIS) and Lithuania (TPDRIS) to probe. |
| Latvia | TAPIS (`tapis.gov.lv`): functional zoning (`funkcionālais zonējums`) structured nationally by regulation 392 | WMS/WFS planned per the ministry; to probe | National schema for every municipal plan. |
| US (bulk) | National Zoning Atlas: Mercatus downloads (Colorado Denver 2025, Hawaii, Massachusetts, Montana, New Hampshire 2023, Long Island CSV, Middle Tennessee, Texas DFW 2024, Hampton Roads, Northern Virginia); data dictionary (Mercatus 2024) | ZIP (GeoJSON), CSV | **Blocked**: the S3 bucket `statezoningatlasdata` no longer exists (NoSuchBucket, 2026-11-08); mercatus.org answers HTTP 403 to scripted downloads. Needs a manual download by the owner into R2, or the teams' own files. |
| US, California | California Statewide Zoning, Office of Land Use and Climate Innovation: ArcGIS `services8.arcgis.com/Xr1lDrwMv89PhjD9/.../California_Statewide_Zoning_South/FeatureServer/0` (304,324 zones) and `..._North/FeatureServer/1` (264,417); GeoPackage and shapefile via `gis.data.ca.gov/api/download/v1/items/<id>/geoPackage` | FeatureServer, GPKG | 535 of 539 jurisdictions; local code and description plus a harmonised class (`ucd_number`, `ucd_description`, `New_Class`); PDF maps were georeferenced by the publisher. No licence stated (public access, informational): owner question. |
| Germany, NRW | Windenergiebereiche der Regionalplanung NRW (LANUK, `ckan.open.nrw.de` dataset de7e9cff-...) | shapefile / WFS | Regional plans in force (Arnsberg, Detmold, Düsseldorf, Köln, Münster); 1:50,000, generalised. |
| Austria, Upper Austria | Flächenwidmung (DORIS), shapefile ZIP at `e-gov.ooe.gv.at`, WFS and WMS | shapefile, WFS | Open government data. |
| Austria, Styria | Flächenwidmungspläne, `data.steiermark.at` (Geographie und Planung) | shapefile | CC BY 4.0 AT; legal plan only at the municipality. Lower Austria: NÖ Atlas view only (to probe); Salzburg INSPIRE download (to probe). |
| Poland (national view) | KIMPZP, the national integration of MPZP (WMS via geoportal.gov.pl, EPSG:2180); APP datasets per gmina | WMS GetFeatureInfo; GML per gmina | Vector only per gmina (APP); city open data such as Kielce. |
| EU | Renewables acceleration areas (RED III) | per member state | No consolidated download; Oeko-Institut 2025 follow-up covers 10 member states' progress. |

## Still to research
Spanish regional planning portals, Italy (regional PRG / PUC geoportals), Belgium
(Flanders Ruimtelijke uitvoeringsplannen, Wallonia plan de secteur), Czechia (ÚAP, územní plány),
Portugal (SNIT, PDM), Northern Ireland (Department for Infrastructure area plans),
Sweden, Finland, the Baltics, the rest; US states with statewide zoning layers (Massachusetts,
Connecticut, Wisconsin), and the largest cities' zoning portals.

## Probe results (2026-11-08, `scripts/probe_zoning.py`)

| Source | Answer | Size | What a zone carries |
|---|---|---|---|
| France GPU `zone-urba` | 200 | Paris PLU 1,153 zones | `libelle` (code), `libelong` (label), `typezone` (U, AU, A, N), `idurba`, `datappro`, `urlfic` (regulation file), `destdomi` |
| Denmark plandata `theme_pdk_kommuneplanramme_vedtaget_v` | 200 | 50,608 frames (adopted) | general and specific use (`anvgen`, `anvspec1..10`), building percentage, heights; 211 feature types incl. lokalplaner |
| Helsinki `avoindata` WFS | 200 | 303 feature types | `Kaavahakemisto_alue_kaava_voimassa` (plans in force), underground plans, pending |
| England planning.data.gov.uk bulk CSV | 206 | green belt 33 MB, conservation area 50 MB, article 4 24 MB, brownfield 22 MB | WKT `geometry`, `reference`, `organisation`, `document-url`, dates |
| California statewide zoning | 200 | 304,324 + 264,417 zones | local code, description, harmonised class |
| National Zoning Atlas | 404 / 403 | | blocked (above) |
| Ireland MyPlan GZT (`services.arcgis.com/NzlPQPKn5QF9v2US/.../GZT_Current_Plan`, `GZT_Expired_Plan`) | 200 | 86,686 current zones | `ZONE_ORIG` (the plan's own code), `ZONE_DESC`, `ZONE_LINK` (plan document), `ZONE_GZT` and `GZT_DESC` (national harmonised type), `PLAN_NAME`, `PLAN_FROM`/`PLAN_TO`, `LA_NAME`; same owner also publishes Solar Safeguarding Zones (43, CC BY) and the Residential Zoned Land Tax maps 2023-2027. `maps.housing.gov.ie` does not answer from this container. |
| France, national WFS (Géoplateforme `data.geopf.fr/wfs/ows`) | 200 | `wfs_du:zone_urba` 1,345,010 zones; `wfs_du:doc_urba` 23,390 plan records; `wfs_du:document` 12,903 documents; `wfs_du:prescription_surf` 4,352,651 prescriptions; SUP and SCoT layers | Plan files listed per document at `geoportail-urbanisme.gouv.fr/api/document/<gpu_doc_id>/files` and served from `data.geopf.fr/annexes/gpu/documents/<partition>/<id>/<file>` (PDF, no key). Document details give legal status and `EN_VIGUEUR`. |

## Discovery method

1. **Known national services first** (above), probed with `scripts/probe_zoning.py`.
2. **The EU open-data portal** (`data.europa.eu`, which harvests every national and INSPIRE
   catalogue): `scripts/zoning_discover.py` searches each country for its own legal plan
   names (Bebauungsplan, bestemmingsplan, MPZP, územní plán, asemakaava, ...), keeps a hit only
   when its title in a publisher language contains the term as a whole word and it offers a
   geodata distribution or a PDF, and writes one row per dataset plus a count per publisher.
   The INSPIRE geoportal itself serves an expired TLS certificate (2026-11-08), so its
   harvest through data.europa.eu is used instead.
3. **ArcGIS Hub** (`hub.arcgis.com` search API): most US counties and cities and many UK
   councils publish zoning on ArcGIS Online, not in a national catalogue.
   `zoning_discover.py --hub` sweeps the US, UK and EU in 2-degree tiles and keeps services
   whose title names zoning, land-use plans, local plans, green belt or allocations.
4. **PDF-only plans** (Wales, Northern Ireland, many Italian and Portuguese municipalities):
   the plan documents are stored with their text, and their maps are only georeferenced where
   the publisher has not done so; a georeferenced PDF map without a vector source is an owner
   question (manual control points are an estimate of position).
