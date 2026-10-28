# Room to connect: every operator, what it publishes (brief 26)

The reference for the owner: for each country of the EU-27, the EU's neighbours, the UK
(Northern Ireland included) and the US, each grid operator (the TSO and the largest DSOs; in the
US each ISO/RTO, transmission provider and the main utilities), what it publishes about free grid
capacity, and whether the atlas has it. Checked 2026-10-27 (registry) and 2026-10-28 (this
session). Evidence: `docs/research/probe_connect_h26.txt` (output of
`scripts/probe_connect_h26.py`, one line per candidate; cited below by its code) and the earlier
probes (`scripts/probe_connect_gaps.py`, `scripts/probe_connect_us_heatmaps.py`, the registry
`data/coverage.yaml`).

**Status:** *built* (rows in `connect/harmonised.json`; "PR 23" = before this brief, "new" = this
brief) · *not harmonised* (published, but not as figures the schema can hold without guessing:
said why) · *browser check* (a Cloudflare JavaScript check answers scripts; brief rule 2 allows
`scripts/browser_fetch.py` in Actions; not run in this session, the data URL behind the check is
unknown until a browser passes it) · *refused* (HTTP 451, a block page or a refusal: data
request) · *login* / *key* (an account: data request or a key) · *interactive* (a map or Power BI
report that computes per click, no table or service: data request) · *not published* (the
operator's pages hold no capacity map, file or service).

**Legal basis:** EU TSOs, Regulation (EU) 2019/943 Art. 50(4a) (from Regulation (EU) 2024/1747);
EU DSOs, Directive (EU) 2019/944 Art. 31(3) (from Directive (EU) 2024/1711); national rules where
named. US transmission providers, FERC Order No. 2023/2023-A (heatmap); US distribution, the
state hosting-capacity rules named.

## Before and after

| | Before (PR 23) | After (this brief) |
|---|---:|---:|
| Countries or US codes with rows | 25 (+3 US utilities) | 29 (+8 US codes) |
| Operators | 39 | 53 |
| Rows | 19,266 | 24,758 |

Placed rows and MW published per operator are in `docs/DATA_SOURCES.md` (section "Room to
connect, brief 26") and in the pull request.

## EU-27

| Country | Operator | Level | Publishes | URL | Format | Licence | Legal basis | Status | Checked | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| AT | APG | T | available connection capacity per substation | https://markt.apg.at/netz/netzanschluss/netzanschlusskapazitaeten/ | HTML table | public notice | Art. 50(4a) | built (PR 23) | 10-27 | registry |
| AT | Energienetze Steiermark | D | free feed-in capacity (FEK) per substation, booked and available MW, "Stand 01.07.2026" | https://www.e-netze.at/Service/FEK/Default.aspx | HTML table (53 rows) | operator website | Art. 31(3) | **built (new)**, positions by OSM name | 10-28 | AT-ENETZE 200 |
| AT | Netz Niederösterreich | D | transformer map for feeders (Trafokarte); capacities of substations as pages | https://netz-noe.at/strom/versorgungsgebiete-und-kapazitaeten/trafokarte-fuer-einspeiser | QGIS WMS (`webgis.evn.at`, GetFeatureInfo per click) | operator website | Art. 31(3) | interactive (no table; the WMS certificate chain fails for scripts) | 10-28 | AT-NETZNOE 200, AT-NETZNOE-WMS SSL error |
| AT | Wiener Netze, Netz Oberösterreich, Kärnten Netz | D | no capacity map or file found | wienernetze.at, netzooe.at, kaerntennetz.at | | | Art. 31(3) | not published | 10-28 | AT-WIENERNETZE, AT-NETZOOE, AT-KNG 200 |
| BE | Elia | T | hosting capacity map 2026 and 2031; Wallonia remaining capacity per substation | https://www.elia.be/en/customers/connection/grid-hosting-capacity | behind the check | | Art. 50(4a) | browser check | 10-28 | BE-ELIA 403 Cloudflare |
| BE | Fluvius | D | connection pages only | https://www.fluvius.be/nl/aansluitingen | | | Art. 31(3) | not published (no capacity map found) | 10-28 | BE-FLUVIUS 200 |
| BE | ORES, Sibelga, RESA | D | ORES no capacity page found; Sibelga behind the check; RESA resets the connection | ores.be, sibelga.be, resa.be | | | Art. 31(3) | not published / browser check / refused | 10-28 | BE-ORES 200, BE-SIBELGA 403, BE-RESA reset |
| BG | ESO | T | free capacity map | https://webapps.eso.bg/capacity/ | JSON | public notice | Art. 50(4a) | built (PR 23) | 10-19 | registry |
| BG | ERP Sever (Energo-Pro), ERM Zapad, EVN Bulgaria | D | capacity check pages (form or document lists, no table) | erpsever.bg, ermzapad.bg | HTML, PDF forms | | Art. 31(3) | interactive (ERP, ERMZ); EVN 502 through the proxy | 10-28 | BG-ERP, BG-ERMZ 200, BG-EVN 502 |
| HR | HOPS | T | connection possibility per substation (categories) | https://www.hops.hr/informacije-o-mogucnosti-prikljucenja | PDF table | operator website | Art. 50(4a) | built (PR 23) | 10-27 | registry |
| HR | HEP ODS | D | free capacity for RES, pending and contracted users per substation (488), data date 2026-10-01 | https://kapaciteti.hep.hr | JSON behind the map (`/api/substations/with-data`) | public web map (no licence stated) | Art. 31(3) | **built (new)** | 10-28 | HR-HEPODS 488 records |
| CY | TSO Cyprus | T | | https://www.tsoc.org.cy/ | | | Art. 50(4a) | browser check | 10-28 | CY-TSO 403 Cloudflare |
| CY | EAC (DSO) | D | hosting capacity page | eac.com.cy hosting-capacity | | | Art. 31(3) | refused (connection reset) | 10-28 | CY-EAC reset |
| CZ | ČEPS | T | available capacity per substation (2031, 2036) | https://www.ceps.cz/cs/mapa-dostupne-kapacity-pro-pripojeni-k-ps | JSON | public notice | Art. 50(4a) | built (PR 23) | 10-19 | registry |
| CZ | PREdistribuce | D | free capacity for generators per 110 kV area (133 pieces, 25 areas), requests received/approved/refused, LV feeders (5,134) | ArcGIS `Mapa_Pripojitelnosti_PREdistribuce` | ArcGIS FeatureServer | public web map | Art. 31(3) | **built (new)**: class only, the layer states no unit | 10-28 | CZ-PRE layers and counts |
| CZ | ČEZ Distribuce | D | capacity map announced (article "Kapacita distribuční sítě v mapě") | cezdistribuce.cz | map app | | Art. 31(3) | interactive (no data service found from the article) | 10-28 | CZ-CEZ 200 |
| CZ | EG.D | D | | egd.cz | | | Art. 31(3) | refused (403 maintenance page) | 10-28 | CZ-EGD 403 |
| DK | Energinet and the DSOs | T, D | kapacitetskort.dk, free MW per TSO and DSO station | http://www.kapacitetskort.dk | ArcGIS | public | Art. 50(4a), 31(3) | built (PR 23) | 10-19 | registry |
| DK | Radius Elnet | D | status of transmission capacity (text), Green Power Denmark's Kapacitetskort Samlet (6,489 DSO-area records, history) | radiuselnet.dk | HTML, ArcGIS | | Art. 31(3) | covered by kapacitetskort.dk (the GPD layer repeats it with dates) | 10-28 | DK-RADIUS 200 |
| EE | Elering | T | e-Gridmap, expandable or not | https://vla.elering.ee/ | JSON | public | Art. 50(4a) | built (PR 23) | 10-19 | registry |
| EE | Elektrilevi | D | | elektrilevi.ee | | | Art. 31(3) | browser check | 10-28 | EE-ELEKTRILEVI Cloudflare |
| FI | Fingrid | T | Verkkokiikari (Grid Scope) map | https://www.fingrid.fi/kantaverkko/liitynta-kantaverkkoon/verkkokiikari/ | map app, no download | | Art. 50(4a) | interactive | 10-28 | FI-FINGRID 200 |
| FI | Elenia | D | production and consumption MW per main transformer; storage capacity (169) | elenia.fi | ArcGIS | public web map | Art. 31(3) | built (PR 23); storage layer not added (a third side the schema has no field for) | 10-28 | FI-ELENIA-STORAGE n=169 |
| FI | Helen Sähköverkko | D | free MV capacity per primary substation area (MVA, data 05/2025) | ArcGIS `KJ_vapaa_kapasiteetti` | ArcGIS | public web map | Art. 31(3) | **built (new)** | 10-28 | FI-HELEN n=25 |
| FI | K-Sat, Nivos, Naantalin Energia, Lehtimäki (Rejlers-hosted maps) | D | free connection capacity as MVA bands ("1-3 MVA") per area, no side stated | ArcGIS `*_kapasiteetti_2026_WFL1` | ArcGIS | public web map | Art. 31(3) | not harmonised (bands and no side) | 10-28 | FI-KSAT, FI-NIVOS, FI-NAANTALI |
| FI | Caruna | D | no capacity map found | caruna.fi | | | Art. 31(3) | not published | 10-28 | FI-CARUNA 200 |
| FR | RTE and the DSOs (Capareseau) | T, D | S3REnR capacity per substation | https://www.capareseau.fr | JSON, CSV | reuse with source | Art. 50(4a); S3REnR | built (PR 21/23) | 10-27 | registry |
| FR | Enedis | D | connection portal (login); capacity through Capareseau | enedis.fr | | | Art. 31(3) | covered by Capareseau | 10-28 | FR-ENEDIS 200 |
| DE | 50Hertz, Amprion, TransnetBW | T | grid-capacity map, potential connection points, connection map | registry | JSON, PDF, map | | Art. 50(4a); §14e EnWG | built (PR 23) | 10-27 | registry |
| DE | TenneT DE | T | | tennet.eu/de | | | Art. 50(4a) | browser check | 10-28 | DE-TENNET 403 |
| DE | Westnetz, Bayernwerk, E.DIS, Avacon, SH Netz (E.ON) | D | | westnetz.de, bayernwerk-netz.de, e-dis-netz.de, avacon-netz.de, sh-netz.com | | | Art. 31(3); §14e EnWG | browser check (all five) | 10-28 | DE-WESTNETZ … DE-SHNETZ 403 |
| DE | Netze BW | D | "Mittelspannungsauskunft" (a request per site) | netze-bw.de | form | | Art. 31(3) | interactive | 10-28 | DE-NETZEBW 200 |
| DE | MITNETZ Strom, Stromnetz Berlin, EWE Netz, LEW Verteilnetz, RheinNetz | D | reservation and feed-in pages; RheinNetz "Netzauslastung" text; LEW network pre-enquiry form | as probed | HTML | | Art. 31(3) | not published (no capacity file) | 10-28 | DE-MITNETZ, DE-STROMNETZBERLIN, DE-EWE, DE-LEW, DE-RHEINNETZ 200 |
| DE | Stromnetz Hamburg | D | | stromnetz-hamburg.de | | | Art. 31(3) | refused ("The URL you requested has been blocked", 500) | 10-28 | DE-STROMNETZHH 500 |
| GR | IPTO (ADMIE) | T | interconnection capacity notices only | admie.gr | | | Art. 50(4a) | not published | 10-28 | GR-ADMIE 200 |
| GR | HEDNO | D | RES hosting margins per HV/MV transformer | https://apps.deddie.gr/WebAPE/main.html | JSON | public web app | Art. 31(3) | built (PR 23) | 10-27 | registry |
| HU | MAVIR (with the DSOs' stations) | T | station list, spare bays, injection MVA | mavir.hu | xlsx | disclaimer | Art. 50(4a) | built (PR 23) | 10-27 | registry |
| HU | MVM Démász, MVM Émász | D | free capacity for load per substation | mvmhalozat.hu | PDF | | Art. 31(3) | built (PR 23) | 10-27 | registry |
| HU | OPUS TITÁSZ, E.ON Hungary | D | OPUS PDF without a side; E.ON no file | opusttitasz.hu, eon.hu | PDF | | Art. 31(3) | not harmonised (OPUS) / not published (E.ON); OPUS 502 through the proxy today | 10-28 | HU-OPUS 502, HU-EON 200 |
| IE | EirGrid | T | no node table found | eirgrid.ie | | | Art. 50(4a) | not published | 10-27 | registry |
| IE | ESB Networks | D | available capacity heatmap download | esbnetworks.ie | xlsx | website terms | Art. 31(3) | built (PR 23) | 10-27 | IE-ESBN 200 |
| IT | Terna | T | Econnextion: requests per region | dati.terna.it | xlsx | terms not found | Art. 50(4a) | built (PR 23, queue per region) | 10-27 | IT-TERNA 200 |
| IT | e-distribuzione, Areti, Unareti | D | connection guides and a connection simulator; no capacity file | as probed | HTML | | Art. 31(3) | not published | 10-28 | IT-EDIS, IT-ARETI, IT-UNARETI 200 |
| LV | AST | T | | ast.lv | | | Art. 50(4a) | browser check | 10-28 | LV-AST 403 |
| LV | Sadales tīkls | D | free capacity map `karte.sadalestikls.lv/lv/briva-jauda` | | map | | Art. 31(3) | refused (HTTP 451 to a named client; reset today): data request | 10-28 | LV-ST reset; registry 451 |
| LT | Litgrid | T | generation capacity map | ArcGIS experience | ArcGIS | public | Art. 50(4a) | built (PR 23) | 10-19 | registry |
| LT | ESO | D | | eso.lt | | | Art. 31(3) | browser check | 10-28 | LT-ESO 403 |
| LU | Creos | T, D | grid hosting capacity map | creos-net.lu | ArcGIS | public | Art. 50(4a) | built (PR 23) | 10-19 | registry |
| MT | Enemalta | D | available capacity map | enemalta.com.mt | JSON | public notice | Art. 31(3) | built (PR 23) | 10-19 | registry |
| NL | TenneT NL | T | | tennet.eu/nl | | | Art. 50(4a) | browser check; its capacity is in the national map below | 10-28 | NL-TENNET 403 |
| NL | Netbeheer Nederland (Liander, Stedin, Enexis, …) | T, D | landelijke capaciteitskaart | capaciteitskaart.netbeheernederland.nl | ArcGIS (Esri NL) | Esri NL terms | Art. 31(3) | built (PR 23) | 10-27 | registry |
| PL | PSE | T | Art. 7(8l) list; switchgears without free bays | pse.pl | xlsx | public information | Energy Law Art. 7(8l) | built (PR 23) | 10-27 | registry |
| PL | Enea Operator | D | connected and available RES capacity, available load capacity | https://www.operator.enea.pl/przylaczone-i-dostepne-moce-oze | Power BI reports (five) | | Art. 7(8l) | interactive (Power BI, no export): data request | 10-28 | PL-ENEA [Power BI] |
| PL | Energa-Operator | D | "Mocne Strefy" investment zones platform | https://mocnestrefy.pl/ | JS app | | Art. 7(8l) | interactive | 10-28 | PL-ENERGA 200 |
| PL | Tauron Dystrybucja | D | available capacity portal (dostepnemoce), lists of applicants and planned objects | dostepnemoce.tauron-dystrybucja.pl | JS app behind Turnstile and a nonce | | Art. 7(8l) | refused (bot challenge on the data calls): data request | 10-28 | PL-TAURON 200; earlier session |
| PL | PGE Dystrybucja, Stoen | D | PGE certificate chain fails for scripts; Stoen connection page only | pgedystrybucja.pl, stoen.pl | | | Art. 7(8l) | not published (Stoen); PGE unreachable | 10-28 | PL-PGE SSL, PL-STOEN 200 |
| PT | REN | T | reception capacity indicators page (moved, 404) | ren.pt | | | Art. 50(4a) | not published | 10-28 | PT-REN 200 |
| PT | E-REDES | D | reception capacity (CC BY 4.0) | e-redes.opendatasoft.com | Opendatasoft | CC BY 4.0 | Art. 31(3) | built (PR 23) | 10-27 | registry |
| RO | Transelectrica | T | capacity allocation procedure (June 2026), auction notices | transelectrica.ro | PDF procedure | | Art. 50(4a); ANRE | browser check (challenge on some pages); no capacity table found | 10-28 | RO-TEL [Cloudflare] |
| RO | Delgaz Grid, E-Distribuție | D | | delgaz.ro, e-distributie.com | | | ANRE (110 kV, weekly) | browser check | 10-28 | RO-DELGAZ, RO-EDIS 403 |
| RO | Distribuție Energie Electrică, Rețele Electrice | D | DEER home only; Rețele 403 | distributie-energie.ro, reteleelectrice.ro | | | ANRE | not published / refused | 10-28 | RO-DEER 200, RO-RETELE 403 |
| SK | SEPS | T | Power BI report | sepsas.sk | Power BI | | Art. 50(4a) | interactive | 10-27 | registry |
| SK | ZSD, VSD | D | connectability map CSVs | zsdis.sk | CSV, JSON | operator website | Art. 31(3) | built (PR 23) | 10-27 | registry |
| SK | SSD | D | connection pages | ssd.sk | | | Art. 31(3) | not published | 10-28 | SK-SSD 200 |
| SI | ELES | T | hosting capacity per substation | eles.si | ArcGIS | public web map | Art. 50(4a) | built (PR 23) | 10-27 | registry |
| SI | Elektro Ljubljana and the other DSOs | D | MV layer with upper bounds only ("< 10.000 kW") | ELES ArcGIS | ArcGIS | | Art. 31(3) | not harmonised (bounds) | 10-27 | registry |
| ES | REE | T | access capacity of demand per node | ree.es | PDF/xlsx | REE terms | Art. 50(4a); CNMC Circular 1/2024 | built (PR 23) | 10-27 | registry |
| ES | e-distribución, Viesgo, E-Redes España, Begasa | D | CNMC-format access capacity | edistribucion.com, redes-spain.opendatasoft.com | CSV, Opendatasoft | CC BY 4.0 / reuse | Circular 1/2024 | built (PR 23) | 10-27 | registry |
| ES | i-DE, UFD | D | | i-de.es, ufd.es | | | Circular 1/2024 | refused (503 / 403 to scripts) | 10-28 | ES-IDE 503, ES-UFD 403 |
| SE | Svenska kraftnät | T | capacity per county | karta.svk.se | ArcGIS | public | Art. 50(4a) | built (PR 23) | 10-19 | registry |
| SE | Vattenfall Eldistribution | D | capacity maps: regional network stations (1,233 records = stations × horizon) and local network areas (282), MW per technology (solar, wind, storage, three load types) and years to connection | https://www.vattenfalleldistribution.se/kapacitetskarta | ArcGIS (`Kategori_regionnät_260702`, `Kategori_Lokalnät_260527`) | public web map | Art. 31(3) | **built (new)** | 10-28 | SE-VATTENFALL layers and counts |
| SE | Ellevio, E.ON Energidistribution | D | Ellevio no capacity map; E.ON behind the check | ellevio.se, eon.se | | | Art. 31(3) | not published / browser check | 10-28 | SE-ELLEVIO 200, SE-EON 403 |

## The UK (Northern Ireland included)

| Country | Operator | Level | Publishes | URL | Format | Licence | Legal basis | Status | Checked | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| GB | NESO | T | TEC register | neso.energy | CSV | NESO Open Data | licence | built (PR 23) | 10-27 | registry |
| GB | NGED, SSEN, Northern Powergrid | D | headroom per substation | as registry | JSON, CSV | open data licences | Ofgem LTDS / licence | built (PR 23) | 10-27 | registry |
| GB | ENWL, SPEN, UKPN | D | Opendatasoft exports, empty without a key | | Opendatasoft | | licence | key (`ENWL_API_KEY`, `SPEN_API_KEY`, `UKPN_API_KEY`) | 10-27 | registry |
| GB (NI) | NIE Networks | D | capacity map: demand, generation and fault-level headroom (MVA) per bulk supply point and primary, 241 markers (265 rows: dual primaries per transformation) | https://www.nienetworks.co.uk/connections/capacity-map | JSON behind the map (`/Connections/Capacity-Map?markers=1`); a spreadsheet link that serves the page | "subject to terms & conditions" (on the map) | licence (Utility Regulator) | **built (new)** | 10-28 | NI-NIE 241 records |
| GB (NI) | SONI | T | no transmission capacity map found | soni.ltd.uk | | | licence | not published | 10-28 | NI-SONI 200 |

## The EU's neighbours

| Country | Operator | Level | Publishes | URL | Format | Licence | Legal basis | Status | Checked | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| NO | Statnett | T | statistics of connection requests and reservations per station | https://www.statnett.no/nettkapasitet-til-produksjon-og-forbruk/foresporsler-og-reservasjon-i-nettet/ | Power BI reports (five, no export) | | Energiloven, local allocation since 2018 | interactive: data request | 10-28 | NO-STATNETT [Power BI] |
| NO | Elvia, NVE | D, regulator | no capacity map or file found | elvia.no, nve.no | | | | not published | 10-28 | NO-ELVIA, NO-NVE 200 |
| NO | a DSO via Sweco (8 secondary substations, kW text) | D | `nettstasjoner_med_ledig_kapasitet` | ArcGIS (Sweco Norge) | ArcGIS | | | not harmonised (operator not named, eight records) | 10-28 | earlier session |
| CH | Swissgrid | T | connection capacity maps: additional generation and load per 220/380 kV substation, 2026/2030/2035/2040, base and 10 %/20 % flexibility, MVA capped at 300 (151 substations) | https://www.swissgrid.ch/en/home/customers/topics/grid-connection.html | PDF tables + methodology PDF | public PDF | StromVG | **built (new)**: 2026 base case, positions by OSM name | 10-28 | CH-SWISSGRID PDF 2 pages |
| CH | EKZ, BKW (and CKW, Groupe E, Romande Energie, IWB), ElCom | D, regulator | no capacity file found | ekz.ch, bkw.ch, elcom.admin.ch | | | | not published | 10-28 | CH-EKZ, CH-BKW, CH-ELCOM 200 |
| IS | Landsnet, RARIK | T, D | no capacity map or file found | landsnet.is, rarik.is | | | | not published | 10-28 | IS-LANDSNET, IS-RARIK 200 |
| RS | EMS | T | cross-border capacity only | https://ems.rs/opis-i-kapaciteti/ | | | Energy Community | not published | 10-28 | RS-EMS 200 |
| RS | Elektrodistribucija Srbije | D | no capacity file | elektrodistribucija.rs | | | | not published | 10-28 | RS-EDS 200 |
| BA | NOS BiH, Elektroprenos BiH | T | NOS BiH timed out; Elektroprenos no capacity file | nosbih.ba, elprenos.ba | | | Energy Community | not published (NOS BiH unreachable) | 10-28 | BA-NOSBIH timeout, BA-ELPRENOS 200 |
| ME | CGES, CEDIS | T, D | connection procedure pages | cges.me, cedis.me | | | Energy Community | not published | 10-28 | ME-CGES, ME-CEDIS 200 |
| MK | MEPSO, Elektrodistribucija (EVN) | T, D | connection procedure pages | mepso.com.mk, elektrodistribucija.mk | | | Energy Community | not published | 10-28 | MK-MEPSO, MK-EVN 200 |
| AL | OST, OSHEE | T, D | OST behind the check; OSHEE new-connection pages | ost.al, oshee.al | | | Energy Community | browser check (OST) / not published (OSHEE) | 10-28 | AL-OST 403, AL-OSHEE 200 |
| XK | KOSTT, KEDS | T, D | KOSTT's certificate chain fails for scripts; KEDS no capacity file | kostt.com, keds-energy.com | | | Energy Community | not published (KOSTT unreachable) | 10-28 | XK-KOSTT SSL, XK-KEDS 200 |
| MD | Moldelectrica, Premier Energy Distribution | T, D | both behind the check | moldelectrica.md, premierenergy.md | | | Energy Community | browser check | 10-28 | MD-MOLDELECTRICA 403, MD-PREMIER Cloudflare |
| UA | Ukrenergo, NEURC | T, regulator | Ukrenergo behind the check; NEURC connection rules | ua.energy, nerc.gov.ua | | | Energy Community | browser check (Ukrenergo) / not published | 10-28 | UA-UKRENERGO 403, UA-NEURC 200 |
| TR | TEİAŞ | T (distribution-level allocation per TM) | remaining unlicensed solar and wind capacity allocatable from the distribution level per transformer centre, busbar and EDAŞ/OSB, 01.10.2026 (1,132 rows); a transmission-level map ("Kalan" PDF) as an image | https://www.teias.gov.tr/duyurular/2026-yili-agustos-ayi-lisanssiz-kapasite-tahsisleri-hakkinda | PDF tables (19 pages) | public announcement | EPDK decision 14353 (26.02.2026) | **built (new)**, positions by OSM name | 10-28 | TR-TEIAS PDF 19 pages |
| TR | EPDK, the 21 EDAŞ | regulator, D | no capacity files found | epdk.gov.tr | | | | not published | 10-28 | TR-EPDK 200 |

## The United States

### ISOs/RTOs and transmission providers (FERC Order 2023 heatmaps)

| Area | Operator | Publishes | URL | Format | Licence | Status | Checked | Evidence |
|---|---|---|---|---|---|---|---|---|
| CAISO | CAISO | POI heatmap: three studies (`C15_Reassessment` 406 buses, `2025_TPD` 833, `Cluster15` 747), `trlim` MW per bus | https://www.caiso.com/poi-heatmap/ | JSON, Brotli, 37.5 MB | public | **built (new)**: `2025_TPD`; the bus coordinates are encoded on purpose: not decoded, buses placed by OSM name in California only | 10-28 | US-CAISO wcResults=3 |
| MISO | MISO | CartoVista POI analysis map: 19,223 POIs with positions, MW computed per request | https://cloud.cartovista.com/miso/ | CartoVista API | | interactive: data request for a bulk table | 10-28 | US-MISO 4 maps |
| NYISO | NYISO | heatmap in a CartoVista app | https://www.nyiso.com/interconnections | CartoVista | | interactive | 10-28 | US-NYISO [CartoVista] |
| SPP | SPP | Hosting Capacity Tool, Power BI reports | https://www.spp.org/engineering/generator-interconnection/ | Power BI | | interactive | 10-28 | US-SPP [Power BI] |
| PJM | PJM | Queue Scope (POI headroom) | https://www.pjm.com/planning/service-requests | app with an account | | login | 10-28 | US-PJM [login] |
| ISO-NE | ISO-NE | interconnection heatmap (announced) | iso-ne.com | | | not published at the known URL (404) | 10-28 | US-ISONE 404 |
| ERCOT | ERCOT | no Order 2023 heatmap (not FERC-jurisdictional) | ercot.com | | | not published | 10-28 | US-ERCOT 200 |
| BPA | Bonneville Power Administration | ArcGIS app, interconnection queue xlsx | bpa.gov | ArcGIS app, xlsx | | not harmonised (queue, no MW available per bus found) | 10-28 | US-BPA [ArcGIS app] |
| PGE (OR) | Portland General Electric | available capacity per POI (226) and the full contingency list (36,960) | ArcGIS `TransmissionCapacity_PointsOfInterconnection` | ArcGIS | terms on the item | **built (new)** | 10-28 | US-PGE-OR n=226 |
| IPC | Idaho Power | maximum injection per substation (216), injection lines (603,733) | ArcGIS `InterconnectCapacity` | ArcGIS | | **built (new)** | 10-28 | US-IPC n=216 |
| LGEKU | LG&E and KU | transfer limit per bus, year and season (2,234), full calculation (1.5 M) | ArcGIS `LGE_KU_FERC_Interconnection_HeatMap_MW` | ArcGIS | | **built (new)**: newest year, lowest season | 10-28 | US-LGEKU n=2234 |
| AVA | Avista | MW available per bus at injection steps 20-300 MW (19,764) | ArcGIS `HeatMap_MW_Impact_PRD` | ArcGIS | | **built (new)**: largest step without an overload | 10-28 | US-AVA n=19764 |
| NVE | NV Energy | interconnection queue layers (executed, suspended, in study), no MW available | ArcGIS `NV_Energy_Interconnection_Queue` | ArcGIS | | not harmonised (queue covered by LBNL) | 10-28 | US-NVE layers |
| PNM, SOCO | PNM, Southern Company | CartoVista heatmaps (Southern's API answers 401) | cloud.cartovista.com | CartoVista | | interactive / login | 10-28 | US-PNM 5 maps, US-SOCO 401 |
| VELCO | Vermont Electric Power Co. | POI interactive map | velco.com | | | refused (403) | 10-28 | US-VELCO 403 |
| TVA, PacifiCorp, APS, Xcel (PSCo), Duke | OASIS document folders | oasis.oati.com | | | not published as data (the OASIS certificate chain fails for scripts) | 10-28 | US-TVA … US-DUKE SSL |

### Distribution hosting capacity (state rules, DOE atlas)

| State | Utility | Publishes | URL | Format | Status | Checked | Evidence |
|---|---|---|---|---|---|---|---|
| CA | SCE, PG&E, SDG&E | ICA / DRP (CPUC) | registry | ArcGIS | built (PR 23, substations); line sections not drawn | 10-27 | registry |
| NY | National Grid | feeder hosting capacity for PV (1,913 feeders, lines, MW `feeder_max_hc`), substation bank fields, primary line sections (452,342) | `systemdataportal.nationalgrid.com/.../NYSDP/Hosting_Capacity_Data/MapServer` | ArcGIS lines | not harmonised yet: feeder lines (needs the `line` kind and PMTiles) | 10-28 | US-NG-NY counts |
| MA, NH | Eversource | hosting capacity per circuit (MVA; MA 38, NH 100) | ArcGIS `MA_HostingCapacity`, `NH_Hosting_Capacity` | ArcGIS lines | not harmonised yet (lines) | 10-28 | US-EVERSOURCE-MA, -NH |
| NY | Orange & Rockland | IEDR layer (EV chargers, cost-sharing projects) | ArcGIS `IEDR_ORU` | ArcGIS | not capacity | 10-28 | US-ORU layers |
| NY | IEDR (NYSERDA) | statewide platform | iedr.nyserda.ny.gov | app | not probed further (no public API found) | 10-28 | US-IEDR 200 |
| US | DOE U.S. Atlas | links to 58 utilities' maps | energy.gov | ArcGIS app | index only | 10-28 | US-DOE-ATLAS [ArcGIS app] |
| US | ORNL OpenEnergyHub | DTE, Xcel, Central Hudson, UI hosting capacity | openenergyhub.ornl.gov | Opendatasoft | unreachable today (reset) | 10-28 | US-ORNL-OEH reset |

ConEd, Xcel, Duke and Dominion publish per feeder line or grid cell only (registry, 2026-10-27).

## Data requests (ready to send)

Each: who, which dataset, the licence question. Files received go to
`r2://infraatlas-raw/sources/<name>/manual/` and are built from there.

1. **CAISO** (regionaltransmission@caiso.com): "The POI heatmap file `WClusterTrLimSumJson.json`
   holds bus positions in a transformed form. May the Europe InfraAtlas (a public, non-commercial,
   source-backed map) show the buses at their published heatmap positions, and if so, in which
   coordinate system are they? Otherwise we keep placing them by substation name."
2. **Sadales tīkls** (Latvia): "Your free-capacity map (karte.sadalestikls.lv/lv/briva-jauda)
   answers HTTP 451 to our named client. May we receive the free capacity per substation
   (name, voltage, MW for generation and load, date) as a file, and under which terms may we
   show it with your name as the source? (Directive (EU) 2019/944 Art. 31(3).)"
3. **PJM**: "Is the Order 2023 heatmap (POI headroom, MW) available without a Queue Scope account,
   as a public table we may show with PJM named as the source?"
4. **MISO**: "The DPP POI analysis map computes `mwAvailable` per request. Do you publish a table
   of `mwAvailable` per POI for the latest DPP study, and may we show it with MISO named?"
5. **NYISO, SPP, PNM, Southern Company**: the same question for their heatmaps (a table of the
   available injection MW per bus or POI).
6. **Statnett** and **Enea Operator**: "Your connection statistics / available RES capacity are
   published as Power BI reports without an export. May we receive the underlying table (station,
   MW available or reserved, date) and show it with your name as the source?"
7. **Tauron Dystrybucja**: "dostepnemoce.tauron-dystrybucja.pl loads its data behind a bot check.
   May we receive the available capacity per GPZ (Energy Law Art. 7(8l)) as a file?"
8. **PREdistribuce**: "In `Mapa_Pripojitelnosti_PREdistribuce` the field `KAPACITA` (Volná
   kapacita) has no unit. Is it MW? May we show it with your name as the source?"
9. **Elia, Sibelga, TenneT (DE, NL), the E.ON DSOs (Westnetz, Bayernwerk, E.DIS, Avacon, SH Netz),
   AST, ESO (LT), Elektrilevi, TSO Cyprus, Delgaz Grid, E-Distribuție, OST, Moldelectrica, Premier
   Energy Distribution, Ukrenergo, E.ON Energidistribution**: first the browser fetch in Actions
   (brief rule 2) to find the data URL behind the check; where that fails, "May we receive your
   published capacity map's data as a file?".
10. **i-DE, UFD, Stromnetz Hamburg, EG.D, Rețele Electrice, VELCO, EAC**: these refuse or block
    scripts (503, 403, block pages, resets): "May we receive the capacity data you publish under
    (the operator's obligation) as a file, and under which terms?"

## Next steps

- Feeder lines (National Grid NY, Eversource, PG&E and SCE line sections, ConEd): a `line` kind
  and PMTiles built in Actions (brief 26, "Schema and map").
- The browser fetch in Actions for the Cloudflare-checked operators listed above.
- Swissgrid 2030-2040 and the flexibility cases; Vattenfall's other technologies; Elenia's
  storage layer: fields the schema does not hold yet.
