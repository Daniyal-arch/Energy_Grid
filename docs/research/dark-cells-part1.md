# Dark cells, pass 1: consumption, heating, heat pumps, EV registrations

Brief 30 Track 2.3, checked 2026-11-05 and 2026-11-06 from the cloud sandbox. Entries are in
`sources.yaml`, and the evidence for each cell is in `cells.yaml`.

## Consumption per small area (19 dark cells, 9 checked)
- **SI is solved.** SURS 1817609S gives electricity per občina by households and business,
  2020-2025, under CC BY 4.0 (`si_surs_electricity_municipality`).
- **DE, IT, AT, CZ, FI, LV, LT: nothing usable.** Only city sets, regional sets, modelled sets
  (Energie-Atlas Bayern) or national aggregates (Fingrid Datahub) were found. IT Terna stays
  blocked on its licence, and DE Destatis 43531 stays behind the GENESIS login.
- **PL could not be checked.** dane.gov.pl and the GUS BDL API timed out from the sandbox. Retry
  from Actions.
- **Not re-checked this pass:** BG, HR, CY, EE, GR, HU, LU, MT, RO, SK. Their earlier notes
  stand.

## Heating fuel per small area (22 dark cells, 17 checked)
- **New sources, verified:**
  - CZ: `cz_csu_sldb_heating_energy` and `cz_csu_sldb_heating_mode`, Census 2021 per obec.
    These include heat-pump counts.
  - FI: `fi_statfin_heating_fuel_municipality`, buildings by heating fuel per kunta.
  - SI: `si_surs_heating_settlement`, heating method per naselje and občina.
  - PT: `pt_ine_heating_freguesia`, Census 2021 heating type per freguesia.
  - EE: `ee_stat_heating_2011`, census 2011 heating method, under CC BY-SA 4.0.
  - LV: `lv_csp_central_heating`, central heating yes/no only, under CC0.
  - RO: `ro_ins_rpl2021_heating_county`, per county only. Its licence must be confirmed before
    publishing.
- **Several are heating method, not fuel** (SI, LV, EE, PT). The UI label must say so.
- **Wave9 needs new kinds:**
  - **`pxweb`** (SI, FI, EE, LV): POST a query that selects every variable and ask for
    json-stat2. Any variable left out of the query is summed away by the server.
  - **A small custom reader for INE PT**: it must flatten `[0].Dados["2021"]`.
- **Blocked or not published:**
  - HU: the database is a JavaScript app and the results page answers 403.
  - LT: tables are national only.
  - AT: only Vienna publishes, and its links are dead.
  - IT, ES: the 2021 censuses have no heating variable.
  - PL: CEEB detail goes to authorised bodies only.
  - SK, BE: the hosts were unreachable from the sandbox.
  - LU, HR: nothing found.
- **Not re-checked:** BG, CY, GR, MT, and US (the US needs only a Census API key).

## Heat pumps (2 dark cells, 2 checked)
- **GB:** `gb_bus_heat_pumps_la` covers Boiler Upgrade Scheme redemptions per local authority,
  England and Wales, under OGL v3. These are grant-funded installs only. The publication path
  changes monthly, so it needs a collection lookup.
- **US:** `us_eia_recs_heat_pumps_state` gives the RECS 2020 central heat pump share per state.
  These are survey estimates and are public domain.

## EV registrations per area
- No dark cells: all 29 places are built.
