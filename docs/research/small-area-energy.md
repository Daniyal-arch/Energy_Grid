# Small-area outlines and energy per small area: what each country publishes

Research for brief 27 (docs/tasks/27-any-area-wave8.md, Part B "Consistency"), checked
2026-10-29 unless a row says otherwise. One section per place (the 27 member states, the
United Kingdom, the United States). For each: the smallest **outline** level published openly,
the smallest level of **electricity / gas consumption** published openly, **heating fuel** per
small area, the licence, the link, and what the atlas loaded (lake tables `outlines/*` and
`small_area_energy/*`, see docs/DATA_LAKE.md). "Verified" means the file or API answered during
this session (probe output in the pull request); "lead" means a page found but not opened by a
script, to be confirmed. The registry cells (data/coverage.yaml, families `outlines`,
`consumption`, `heating`, `energy_poverty`) carry the same status.

Everywhere in the EU, the same two layers exist whatever the country publishes: Overture Maps
divisions (ODbL; regions, counties, municipalities and, where mapped in OpenStreetMap,
neighbourhoods) and Eurostat's Census 2021 population grid at 1 km (GEOSTAT, `outlines/
geostat_grid`, 1,901,599 populated cells). Eurostat's LAU 2024 outlines are **not** used: GISCO
grants their use "on condition that the data will not be used for commercial purposes".

Rule kept in every row: consumption is shown at the level published, named ("2023, per
municipality"); a coarser level is never split into finer areas, and averages per dwelling are
never multiplied into totals.

## Summary

| Place | Small-area outlines (open) | Consumption, finest open level | Heating fuel, small area | Atlas |
|---|---|---|---|---|
| AT | Zählsprengel (Statistik Austria, CC BY 4.0) — lead | none found (state level only) | none found | outlines via Overture + GEOSTAT; consumption not published |
| BE | statistical sectors (Statbel, open licence) — verified in Actions | Flanders: Fluvius per municipality (lead); Brussels: Sibelga per municipality (lead); Wallonia: ORES MV per sector (lead) | none found | sectors loaded where the download passes; consumption: partial, leads listed |
| BG | none found below municipality | none found (NSI national) | none found | not published |
| CY | none found | none found (national and sector only) | none found | not published |
| CZ | basic settlement units (RÚIAN, ČÚZK, CC BY 4.0) — lead | region and distribution area (ERÚ) | none found | consumption per region only (not loaded) |
| DE | none national (Gemeinden: BKG VG250, dl-de/by-2-0) | industry per Kreis (Destatis 43531, dl-de/by-2-0) — lead; Länder energy atlases (Bavaria municipal estimates: modelled, not used) | Zensus 2022 heating type per 100 m grid and municipality (dl-de/by-2-0) — lead | partial |
| DK | parishes and municipalities (DAGI, Dataforsyningen, open) — lead | households per municipality and heating category, monthly (Energi Data Service, CC BY 4.0) — verified, loaded | electricity by heating category (same dataset) | built (municipality) |
| EE | settlement units (Maa- ja Ruumiamet, CC BY 4.0) — lead | postal-code consumption sold by Elering (not open) | none found | not published (open) |
| ES | census sections (INE, reuse with attribution) — lead | Catalonia: per municipality and sector (ICAEN, open) — verified, loaded; rest: none national open | none found | partial (Catalonia) |
| FI | postal-code areas (Paavo, Statistics Finland, CC BY 4.0) — lead | none per municipality found (Fingrid Datahub national aggregates) | none found | not published |
| FR | IRIS and communes (IGN/INSEE, Licence Ouverte 2.0) — verified | electricity and gas per IRIS and commune by sector (Agence ORE, Licence Ouverte 2.0) — verified | share of dwellings heated by electricity per IRIS (Agence ORE, from INSEE) | built (IRIS) |
| GR | none found | none found (HEDNO publishes no regional consumption) | none found | not published |
| HR | none found open | none found (city reports only) | none found | not published |
| HU | none found below settlement | county household figures in KSH reports (PDF); no open table | none found | not published |
| IE | Small Areas 2022 (CSO / Tailte Éireann, CC BY 4.0) — verified, loaded | electricity per county and Dublin postal district (CSO MEC03, CC BY 4.0) — verified, loaded | census small-area heating (CSO SAPS, CC BY 4.0) — lead | built (county) |
| IT | census sections (ISTAT, CC BY 4.0) — lead | consumption per province and sector (Terna yearly statistics) — lead, no open table found | none found | partial (lead) |
| LT | elderships (lead); 1 km grid (Statistics Lithuania) | ESO consumption on grids (Statistics Lithuania catalogue) — lead | none found | not published (open table) |
| LU | none below commune | none found | none found | not published |
| LV | parishes (VZD, open) — lead | none found (Sadales tīkls sample only) | none found | not published |
| MT | localities (NSO) — lead | non-residential consumption per district (NSO, 2024) — lead | none found | partial (lead) |
| NL | gemeenten, wijken, buurten (CBS, CC BY 4.0) — verified, loaded | average electricity and gas per dwelling per buurt (CBS, CC BY 4.0) — verified, loaded; totals per postcode range (Liander CC BY 4.0; Stedin, Enexis: licence not stated) | district heating, gas-free and electric heating shares per buurt (CBS) — loaded | built (buurt, averages) |
| PL | statistical regions (GUS) — lead; gminy (PRG, open) | none per gmina (GUS BDL dropped municipal electricity) | none found | not published |
| PT | BGRI subsections (INE) — lead | electricity per municipality and parish, monthly (E-REDES, CC BY 4.0) — verified | none found | built (municipality) |
| RO | none found | none found (INS national; ANRE generic) | none found | not published |
| SE | DeSO 2025 (SCB, CC0) — verified, loaded | final energy use per kommun by sector and fuel (SCB/Energimyndigheten TAB3654, CC0) — verified, loaded | fuel per kommun (same table) | built (kommun) |
| SI | settlements (GURS, CC BY 4.0) — lead | none found | none found | not published |
| SK | basic settlement units (lead) | none found (ÚRSO national) | none found | not published |
| GB | ITL 1-3, LAD, MSOA, LSOA (ONS, OGL v3); data zones (Scotland), super data zones (NI) — verified | electricity and gas per LSOA (domestic), MSOA, local authority (DESNZ, OGL v3) — verified | central heating per LSOA (ONS Census 2021 TS046, OGL v3) — verified | built (LSOA) |
| US | tracts, places, county subdivisions (Census TIGER, public domain) — verified, loaded | utilities (EIA-861, have); energy burden and bills per tract (DOE LEAD 2022, modelled by DOE) | heating fuel per tract (ACS B25040, public domain) | built (tract) |

## Notes per place

### Austria (AT)
Statistik Austria publishes municipalities and census tracts (Zählsprengel) as open data
(data.statistik.gv.at, CC BY 4.0; lead). No municipal electricity or gas consumption was found:
Statistik Austria's energy balances stop at the Bundesland; municipal energy reports (e.g.
Sulz, Vorarlberg) use the grid operator's customer data, not a published table. Data request:
"Statistik Austria / E-Control: please publish annual electricity and gas consumption per
municipality (Gemeinde), by sector, as open data."

### Belgium (BE)
Statbel's statistical sectors 2024 (open data) are the small areas. Consumption leads: Fluvius
open data portal (opendata.fluvius.be; dataset "1_23" per municipality and sector, and a
street-level set mirrored on CKAN); Sibelga "yearly consumption and injection" per municipality
and statistical sector (sibelga.be/en/partnerzone/open-data); ORES medium-voltage consumption by
sector (odwb.be). None was opened by a script this session; a City of Brussels dataset found
first holds the city's own buildings, not the area's consumption, and was left out.

### Bulgaria (BG), Cyprus (CY), Greece (GR), Croatia (HR), Hungary (HU), Luxembourg (LU),
### Romania (RO), Slovenia (SI), Slovakia (SK), Latvia (LV), Estonia (EE), Finland (FI),
### Poland (PL)
No open table of electricity or gas consumption below the region was found (searches of the
statistics office, the regulator, the distribution operators and the national portal; sources
in the pull request). Estonia: Elering sells postal-code aggregates (2018 notice: one euro per
postal code-year, about 4,000 euros for a year). Lithuania: ESO electricity per grid cell is
catalogued by Statistics Lithuania (coverage varies by municipality); not opened. Finland:
Fingrid's Datahub open data gives national aggregates by customer type. Poland: GUS BDL no
longer carries municipal electricity use. Hungary: KSH "Statisztikai tükör" reports give county
household figures in PDF. Data request text, the same for each: "Please publish annual
electricity and gas consumption per municipality, by sector (households, services, industry),
as open data under an open licence."

### Czechia (CZ)
ERÚ yearbooks give consumption per region and per regional distribution system; ČSÚ regional
yearbooks per region. No municipal table. RÚIAN basic settlement units are the small areas.

### Germany (DE)
No national small-area consumption. Destatis survey 43531 (energy use of manufacturing per
Kreis) is open under dl-de/by-2-0 through GENESIS/Regionalstatistik (lead). Zensus 2022 publishes
heating type and energy source per municipality and per 100 m grid cell (dl-de/by-2-0; lead).
The Länder energy atlases (e.g. Energie-Atlas Bayern) show municipal estimates: modelled, not
used.

### Denmark (DK)
Energi Data Service `PrivateConsumptionHeatingMonth` (Energinet, CC BY 4.0): household
electricity per municipality, housing and heating category, monthly; loaded as whole years
(sum of the 12 months, MWh). Business consumption is published per region only
(`ConsumptionDK10IndustryYear`).

### Spain (ES)
No national open small-area consumption (Datadis serves account holders). Catalonia's ICAEN
publishes electricity per municipality and sector (`8idm-becu`, transparenciacatalunya.cat):
loaded (44,512 rows). Barcelona publishes per postcode (lead).

### France (FR)
Agence ORE: annual electricity and gas consumption per IRIS and per commune by sector, 2011-2024
(Licence Ouverte 2.0; the IRIS file 1.54 GB). Since 2022 the IRIS method changed (published
note); cells under the confidentiality rule are left out by the source, so sums over IRIS are
"sums of the published rows". IRIS outlines: IGN Contours IRIS 2025 GeoParquet (133 MB).

### Ireland (IE)
CSO MEC03: metered electricity per county and Dublin postal district, residential and
non-residential (CC BY 4.0, PxStat API): loaded. Small Areas 2022 (18,919, CC BY 4.0) loaded.

### Italy (IT)
Terna publishes consumption per province and sector in its yearly statistics (lead; no open
machine-readable table found). ISTAT census sections (CC BY 4.0) are the small areas.

### Malta (MT)
NSO publishes non-residential electricity per district (LAU 1) for 2024 (lead).

### Netherlands (NL)
CBS Kerncijfers wijken en buurten 2024 (85984NED, CC BY 4.0): average electricity (kWh) and gas
(m³) per dwelling, district-heating, gas-free and electric-heating shares, per gemeente, wijk
and buurt (34,510 consumption values loaded). Averages stay averages. Liander publishes
small-consumer data per postcode range under CC BY 4.0; Stedin publishes the same kind of file
(licence not stated on the page); Enexis' open-data page answered 404: listed, not loaded.

### Portugal (PT)
E-REDES open data (Opendatasoft, CC BY 4.0): billed consumption per municipality, monthly, last
10 years (`3-consumos-faturados-por-municipio-ultimos-10-anos`); also per parish and postcode.

### Sweden (SE)
SCB/Energimyndigheten TAB3654: final use (MWh) per kommun, consumer category and fuel, 2009-2024
(CC0), 369,663 values loaded. DeSO 2025 outlines (SCB geodata, CC0) loaded.

### United Kingdom (GB)
DESNZ: electricity and gas per LSOA (domestic), MSOA (domestic and non-domestic) and local
authority, 2010-2024 (OGL v3); renewable electricity by local authority (sites, MW, MWh);
sub-regional fuel poverty per LSOA, 2023 (modelled by DESNZ, official statistics in development).
ONS Census 2021 TS046 central heating per LSOA. England and Wales only for LSOA/MSOA
consumption; Scotland and Northern Ireland at local authority.

### United States (US)
EIA-861 per utility (have). DOE LEAD 2022 (ACS 2018-2022 PUMS, modelled by DOE) per tract:
energy burden computed as the sum of the cohorts' energy expenditure over the sum of their
income. ACS 2019-2023 B25040 house heating fuel per tract (public domain). NREL SLOPE: the
platform's terms page did not answer (proxy 502); left out until its terms are read.
