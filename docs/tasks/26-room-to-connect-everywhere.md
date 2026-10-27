# 26. Room to connect everywhere: EU-27, the EU's neighbours, the UK and the US

## Goal

Room to connect (free grid capacity, hosting capacity, injection capacity, connection queues) is
one of the atlas's most important datasets: it answers "where can a new solar farm, battery,
data centre or factory connect, and how much is free?". Today it covers 39 operators in 25
countries in one schema (`frontend/public/data/eu/connect/harmonised.json`, brief 23) plus the US
queues. This session makes it as complete as published sources allow for **every EU-27 country,
the EU's neighbours (Norway, Switzerland, Iceland, the UK including Northern Ireland, the Western
Balkans, Moldova, Ukraine, Turkey) and the United States**, transmission and distribution, with
one schema and one symbology, and documents every country and operator that publishes nothing.

It is a research task first. Search thoroughly (official sites, regulators, legal obligations,
open-data portals, ArcGIS Hub, map applications' own data requests, academic datasets), probe
every candidate, then build. The earlier session's findings are below so you do not repeat them.

## Read first

- `vault/index.md`, `vault/data/coverage-and-gaps.md`, `vault/rules.md`.
- `docs/tasks/23-grid-capacity-harmonised.md` (the schema, the class mapping rule, the summable
  rule), `scripts/build_connect_harmonised.py`, `scripts/build_connect_h23.py` (how an operator
  becomes rows, name matching to OpenStreetMap substations), `frontend/src/lib/connectH.ts`.
- `scripts/browser_fetch.py` and `.github/workflows/browser-fetch.yml` (files behind a JavaScript
  browser check, fetched with Chromium in Actions).
- The `connect` cells of `data/coverage.yaml` and `scripts/coverage.py` (the registry).
- Probes already written: `scripts/probe_connect_*.py`, `scripts/probe_connect_gaps.py`,
  `scripts/probe_connect_us_heatmaps.py`.

## How to work

- Chat in the caveman style (`.claude/skills/caveman`); docs, code, commits and the PR in normal
  English. Update the vault at the end (`.claude/skills/atlas-vault`).
- One commit per country group or source family; tests and ruff green each time.
- **Probe before building** and put each probe's output in the PR.
- Heavy downloads (feeder-level hosting capacity, large ArcGIS layers) run in GitHub Actions and
  land in R2 (`lake/` for Parquet, PMTiles for geometry), not in the repository.

## Access rules (non-negotiable)

1. Name the client honestly (`Europe-InfraAtlas/<version> (contact)`); never disguise it.
2. A JavaScript browser check that any visitor passes (Cloudflare "Just a moment...") may be passed
   with the real browser of `scripts/browser_fetch.py` in Actions; record that it was used.
3. **Never bypass an explicit refusal:** HTTP 451, a `robots.txt` disallow for the path, terms
   that forbid automated access, a login or account, or data the publisher deliberately encodes
   or hides (see CAISO below). For those, write a short data request (who, which dataset, the
   licence question) for the owner to send, and use the manual upload path
   (`r2://infraatlas-raw/sources/<name>/manual/`).
4. Respect Critical Energy Infrastructure Information: publish only what the operator itself
   publishes openly; no bus-level coordinates the operator does not publish (place nodes by the
   documented OpenStreetMap name match instead).
5. Never estimate a capacity. Values as published; classes mapped one to one; a computed figure
   says how it was computed.

## The legal hooks to cite and search by

- **EU, transmission:** Regulation (EU) 2019/943 Art. 50(4a) (added by Regulation (EU) 2024/1747):
  TSOs publish the capacity available for new connections in their areas, with high spatial
  granularity, updated at least quarterly. **EU, distribution:** Directive (EU) 2019/944 Art. 31(3)
  as amended by Directive (EU) 2024/1711: DSOs publish the same for their areas. Every EU operator
  should therefore publish something; a country without data is a finding to document (with the
  operator's page and date), not a dead end.
- **UK:** Ofgem's distribution licence and DNO heatmap/Long Term Development Statement duties;
  NESO's Transmission Entry Capacity register and connections reform; Northern Ireland: NIE
  Networks and SONI.
- **Energy Community** (Western Balkans, Moldova, Ukraine, Georgia): the Third Package and the
  2024 adoption of the Electricity Integration Package; check each TSO's connection rules.
- **Turkey:** TEİAŞ publishes connectable capacity per transformer substation/region for new
  renewable plants (YEKA and capacity allocation announcements); EPDK decisions.
- **US, transmission:** FERC Order No. 2023 / 2023-A: every jurisdictional transmission provider
  publishes an interactive **heatmap** of estimated incremental injection capacity (MW) per bus or
  point of interconnection under N-1, updated within 30 days of each cluster study, with a table
  of metrics. **US, distribution:** state hosting-capacity mandates (CA ICA, NY, MN, NV, IL, MA,
  NJ, MD, CO, CT, Ohio from 31 May 2026 under ORC 4928.83) and voluntary maps; DOE's U.S. Atlas.

## What the previous session found (2026-10-27)

### Europe: countries with no rows yet

Probe from a laptop (`scripts/probe_connect_gaps.py`) plus the registry notes:

| Country | Finding | Next route |
|---|---|---|
| BE | Elia (hosting capacity map 2026 and 2031; Wallonia: remaining capacity per substation feeding a DSO, a published table) and Sibelga answer a Cloudflare challenge (403); Fluvius and ORES pages 404; Elia open-data portal has no hosting-capacity set | browser fetch; find the map's data request; search Fluvius/ORES/Sibelga capacity maps under their current URLs (EU 2024/1711 obligation) |
| LV | AST: Cloudflare (403). Sadales tīkls' free-capacity map `karte.sadalestikls.lv/lv/briva-jauda` answered 200 once from a laptop, then timed out; it answers HTTP 451 to a script that names itself | AST by browser fetch; **do not bypass the 451**: data request to Sadales tīkls |
| RO | Transelectrica's capacity pages 404 (it published an interactive capacity map in Dec 2021; its 2026 capacity allocation procedure is on its site); Delgaz Grid and E-Distribuție behind Cloudflare; Distribuție Energie Oltenia "Blocked"; Rețele Electrice 403. ANRE requires the DSOs to publish available capacity at 110 kV (weekly since Oct 2022) | find the DSOs' 110 kV publications and Transelectrica's current map; browser fetch |
| CY | TSO Cyprus behind Cloudflare; EAC's hosting-capacity page resets the connection | browser fetch |
| NO | Statnett's and Elvia's capacity pages 404 (moved); allocation is local since 2018 (the grid company reserves capacity); Statnett has published area plans and reservation pauses | find Statnett's current capacity pages and the large grid companies' maps (Elvia, BKK/Eviny, Glitre, Tensio, Lede, Norgesnett); NVE |
| CH | Swissgrid publishes connection forms only | large DSOs (EKZ, BKW, CKW, Groupe E, Romande Energie, IWB); ElCom |
| RS, BA, ME, MK, AL, XK | EMS, CGES, MEPSO sites reachable, nothing found; NOS BiH timed out; OST behind Cloudflare | connection rules, development-plan annexes, regulators (AERS, DERK, REGAGEN, ERC, ERE, ERO) |
| MD, UA | Moldelectrica and Ukrenergo behind Cloudflare | browser fetch; Ukrenergo's connection capacity publications |
| TR, IS | not probed | TEİAŞ capacity tables; Landsnet |

### Europe: operators missing inside covered countries (registry notes)

DE: TenneT DE and the E.ON DSOs (Westnetz, E.DIS, Bayernwerk, Avacon) behind Cloudflare; Netze BW
and VNBdigital publish no capacity file. ES: i-DE (503) and UFD (403). FI: Fingrid Grid Scope (no
download, resets) and Caruna (404). GR: IPTO (403/404). AT: the DSOs (ebutilities.at script-only
page). SK: SEPS (Power BI only), SSD (resets). SI: the DSOs' MV layer gives only upper bounds.
HU: OPUS TITÁSZ (side not stated), E.ON (no file). GB: ENWL, SPEN and UKPN wait for their keys
(`ENWL_API_KEY`, `SPEN_API_KEY`, `UKPN_API_KEY`). Also check every other DSO of each EU country
(the EU obligation applies to all).

### US: transmission heatmaps (FERC Order 2023)

`scripts/probe_connect_us_heatmaps.py` and follow-ups found:

- **CAISO** Points of Interconnection Heatmap (launched 2024-09-20, `https://www.caiso.com/poi-heatmap/`).
  Its data file `https://www.caiso.com/poi-heatmap/WClusterTrLimSumJson.json` (37.5 MB,
  Brotli-encoded: use a client that decodes `br`, e.g. curl `--compressed`) holds `wcResults`:
  three scenarios (`C15_Reassessment` 406 buses, `2025_TPD` 833, `Cluster15` 747), each with
  `buses` (`busnum`, `busname` with kV, `busvolt`, `region`, `pto`, `busarea`, `trlim` = available
  capacity MW, negative = over the limit), `flowgates`, `StressGens`, cost data. **The bus
  coordinates are deliberately encoded** (the app transforms them before display): do not decode
  them (rule 3/4); place buses by the OpenStreetMap name match or ask CAISO
  (regionaltransmission@caiso.com) whether positions may be reused. Last-Modified 2026-06-11.
- **MISO** POI analysis map on CartoVista, public API: `https://cloud.cartovista.com/miso/api/v2/maps/maps`
  lists four public maps (DPP 2023 POI Analysis Map `59878415-54b3-4502-9429-bfd90c7ce3c5`,
  Generation Interconnection Queue, Futures siting maps); `/api/v2/maps/{id}/details` lists layers;
  layer `MISO_POIs_2025-11-11` has 19,223 POIs (`BUS_ID`, `BUS_NAME`, `KV`, `KV_CLASS`, `LATITUDE`,
  `LONGITUDE`, `AREA CODE`, `AREA NAME`) published by MISO; vector tiles at
  `/api/v2/Layer/{id}/mvt/{x}/{y}/{z}.pbf`. The app settings
  (`/api/v2/custom-application/ferc/settings`, study DPP2025) show the per-POI results
  (`mwAvailable`, `constraint`, `dfaxPercent`, `mwImpact`, loading before/after) are computed per
  request: find whether a bulk table of `mwAvailable` per POI is published (MISO's DPP study
  reports, the queue pages); do not hammer the analysis endpoint with 19k requests.
- **ISO-NE**: a heatmap and a queue map went live on iso-ne.com (announced "Oct. 2"); find the
  URL and its data service.
- **SPP**: Hosting Capacity Tool (FAQ `https://www.spp.org/media/2579/hosting-capacity-tool-faq.pdf`;
  Power BI reports on `https://www.spp.org/engineering/generator-interconnection/`;
  `opsportal.spp.org` timed out from the laptop). A Power BI report alone is not a data source:
  look for the tool's own data or a published table.
- **PJM**: Queue Scope (6,000+ POI buses, MW headroom) needs registration: not usable. Find PJM's
  Order 2023 public heatmap if it published one separately.
- **NYISO**: its site did not resolve from the laptop; probe from the cloud.
- **Others with public heatmaps**: VELCO (Vermont POI interactive map, 2025), Southern Company and
  PNM (CartoVista customers). Find the rest: Duke, Dominion (PJM), TVA and BPA (not FERC
  jurisdictional, check voluntary), PacifiCorp, NV Energy, APS, SRP, Xcel (PSCo), Tri-State,
  Evergy, Entergy, FPL, Georgia Power (Southern), Ameren, Avista, Idaho Power, PSE, PGE.
- **ERCOT** (PUCT, no Order 2023 heatmap): only commercial tools found (Enverus, Transect): not
  usable. Look for ERCOT planning publications that state injection capability per bus; else
  document.

### US: distribution hosting capacity

- **DOE U.S. Atlas of Electric Distribution System Hosting Capacity Maps**
  (`https://www.energy.gov/eere/us-atlas-electric-distribution-system-hosting-capacity-maps`,
  updated July 2025): 58 utilities and agencies in 26 states, DC and Puerto Rico, generation (DG),
  load and EV maps. Accounts are required for PG&E, SDG&E, Georgia Power, NV Energy and PSEG Long
  Island (rule 3: skip unless a public layer exists). Main candidates: Con Edison (REST API on its
  map, CSV export), Orange & Rockland, Central Hudson, National Grid (NY, MA), NYSEG/RG&E,
  Eversource (CT, MA, NH), United Illuminating, Unitil, CMP, Versant, Green Mountain, Burlington,
  Rhode Island Energy, the Exelon utilities (ComEd, PECO, BGE, Pepco, Delmarva, Atlantic City
  Electric: shared ArcGIS), PSE&G, JCP&L and Potomac Edison (FirstEnergy), Xcel (MN, CO), DTE,
  Consumers, Ameren, Dominion (VA, NC), Duke (NC, SC), Hawaiian Electric, LUMA, Avista, Idaho
  Power, Pacific Power, PGE, PSE, SCE (DRPEP, already in), LADWP.
- **New York IEDR** (NYSERDA, `iedr.nyserda.ny.gov`): statewide platform normalising the NY
  utilities' circuits and hosting capacity; check its public API.
- **Northeast harmonised dataset**: Scientific Data 2025, "Harmonized geospatial data to evaluate
  the Electric Distribution Networks in the US Northeast" (`https://www.nature.com/articles/s41597-025-06465-9`,
  data on Harvard Dataverse) lists each utility's ArcGIS REST endpoint: use its endpoint table and
  its licence.
- **ORNL OpenEnergyHub** (OpenDataSoft API, `https://openenergyhub.ornl.gov/api/explore/v2.1/catalog/datasets`):
  `dte-hosting-capacity`, `xcel-energy-hosting-capacity`, `central-hudson-maps-copy`,
  `ui_ev_hc_underground_prod`, `ui_ev_hc_phase3_prod`, `ui_ev_hc_non3phase_prod`,
  `mainline-3-phase-lateral`, `integrated-energy-data-resource-iedr`.

## Schema and map

- **Nodes** (transmission heatmaps, substations, POIs): the existing rows; injection capacity is
  the generation side (`mw_gen`); a negative published value means none (class `none`), the value
  kept as published in the tooltip.
- **Distribution feeders and line sections** (US hosting capacity): add a `line` kind (geometry,
  MW for DG and for load) or a separate file built the same way; at country scale these are many
  millions of segments, so build PMTiles in Actions (like the world grid tiles) and keep the
  harmonised JSON for nodes and areas. Summaries per substation or feeder head where the utility
  publishes them.
- Keep `level` (transmission / distribution), `side`, `as_of`, `licence`, `source`, `mapping` per
  operator. The map draws all of it with the same four classes; the key's share bar, the gap layer
  and the Room to connect card read the same file.
- **Registry:** extend `scripts/coverage.py` and `data/coverage.yaml` with a group for the
  neighbours (NO, CH, IS, RS, BA, ME, MK, AL, XK, MD, UA, TR) and Northern Ireland, and US rows
  per ISO/RTO or transmission provider, so the map's dark-country reasons and the coverage
  panel cover them. Every cell: status, source, url, note, checked.

## Deliverables

1. `docs/research/room-to-connect.md`: one table per region: country, operator (TSO and every
   DSO / US transmission provider and utility), level, what it publishes (map, file, API), URL,
   format, licence, legal basis, status (built / browser fetch / refused / not published / login /
   key), date checked, evidence (probe output line). This is the reference for the owner.
2. New harmonised rows for every operator that can be built, with browser-fetch entries where
   needed and lake tables for the full detail.
3. Data requests for refused or login-only sources, ready to send.
4. Registry, `docs/DATA_SOURCES.md`, `docs/DATA_LAKE.md`, vault notes and log updated.

## Done-check

- The research table covers every EU-27 country, every neighbour listed and every US ISO/RTO,
  with at least the TSO and the largest DSOs/utilities per country or state.
- A before/after table in the PR: countries with rows, operators, rows, placed, MW published.
- The map shows the new rows; no country is dark without a registry reason.
- `uv run ruff check . && uv run ruff format .`, `uv run pytest`, `cd frontend && npm run build`.

## Out of scope

Capacity estimates where nothing is published; sources behind a login; new symbology.
