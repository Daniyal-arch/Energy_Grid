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
| Belgium, Wallonia | Plan de secteur | to find (geoportail.wallonie.be) | |
| Portugal | PDM land classification (SNIT, DGT) | to find (dados.gov.pt, SNIT) | PDMs revised by 31 December 2024 for the new land classification rules. |
| Czechia | Územní plány (plochy s rozdílným způsobem využití), ÚAP | to find (per kraj geoportals) | |
| US, Massachusetts | MassGIS ZONING_POLY (all communities, about 2007, not maintained); city layers (Cambridge 2026, Worcester) | ArcGIS, shapefile | Statewide layer for regional analysis only, per MassGIS. |
| US, Connecticut | Connecticut Zoning Atlas (2,620 districts); city layers (Hartford GeoJSON) | to find export | Part of the National Zoning Atlas. |
| Italy | Regional only: Friuli Venezia Giulia PRG homogeneous zones (shapefile, 2001), Sicily SITR (shapefile + PDF by directive), Emilia-Romagna PRG database (2004); Torino zones restricted | shapefile | No national layer; Lombardy PGT per comune, to find. |
| Sweden | Lantmäteriet National Geodata Platform (NGP), Detaljplan | GeoPackage via NGP | Coverage growing (municipal agreements); PDF-only plans are outside the digital requirement. |
| Finland | City WFS: Helsinki `kartta.hel.fi/ws/geoserver/avoindata/wfs` (Kaavahakemisto_kaava_voimassa), Espoo, Vantaa | WFS, EPSG:3879 | Plan index with links to plan documents; Espoo stale (2016). |
| UK, England (more) | planning.data.gov.uk: 100+ datasets (brownfield land, conservation areas, article 4, tree preservation, ...) | CSV and GeoJSON per dataset; bulk download recommended | Check each dataset's coverage (providers). |
| US | City and county open-data zoning layers (NYC, SCAG Southern California parcels, Wisconsin statewide) | ArcGIS REST, shapefile | No free national layer; Regrid / LightBox zoning is commercial (out). |
| EU | Renewables acceleration areas (RED III) | per member state | No consolidated download; Oeko-Institut 2025 follow-up covers 10 member states' progress. |

## Still to research
Spanish regional planning portals, Italy (regional PRG / PUC geoportals), Belgium
(Flanders Ruimtelijke uitvoeringsplannen, Wallonia plan de secteur), Czechia (ÚAP, územní plány),
Portugal (SNIT, PDM), Northern Ireland (Department for Infrastructure area plans),
Sweden, Finland, the Baltics, the rest; US states with statewide zoning layers (Massachusetts,
Connecticut, Wisconsin), and the largest cities' zoning portals.
