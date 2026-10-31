---
title: Coverage and gaps
tags: [data, coverage]
updated: 2026-10-31
paths: [data/coverage.yaml, docs/COVERAGE.md, frontend/public/data/eu/coverage.json, docs/tasks/, docs/research/room-to-connect.md]
---

# Coverage and gaps

What each dataset family covers per country (EU-27, UK, US) is in `data/coverage.yaml`
(rendered in `docs/COVERAGE.md`, read by the app as `coverage.json`). A family with
`regions: [neighbours]` (room to connect) also has a cell for each EU neighbour (NO, CH, IS, RS,
BA, ME, MK, AL, XK, MD, UA, TR); the app's copy lists only those families for a neighbour. Open work is in the briefs
of `docs/tasks/`.

## Known gaps (2026-10-27)
- **Emitters with a position**: EU ETS 2,234 of 9,668 installations placed (Germany 78 of
  1,818); UK ETS 747 installations, none placed. Brief 24 (`docs/tasks/24-emitter-positions.md`).
  Until then the Maps view offers Climate TRACE's modelled emissions where none is placed.
- **Room to connect** (brief 26, 2026-10-28): 53 operators, 24,696 rows in
  `connect/harmonised.json`; brief 26 added HEP ODS, Vattenfall Eldistribution (regional and
  local), NIE Networks, TEİAŞ, Energienetze Steiermark, PREdistribuce, Helen, Swissgrid and the
  Order 2023 heatmaps of CAISO, Portland General, Idaho Power, LG&E-KU and Avista
  (`scripts/build_connect_h26.py`). Every operator checked, with status and evidence:
  `docs/research/room-to-connect.md` (data requests at its end). Still dark, with a registry
  reason: BE, CY, LV, RO (Cloudflare checks, HTTP 451, no tables) and NO, IS, RS, BA, ME, MK, AL,
  XK, MD, UA (nothing published or behind checks). The browser discovery in Actions (2026-10-28) passed
  none of those checks except Transelectrica's (no free-capacity table there): data requests.
  Open: feeder lines (National Grid NY, Eversource) need a `line` kind
  and PMTiles; ENWL, SPEN, UKPN wait for keys.
- **Keys the owner still has to provide** (`PLAN.md`): Anthropic API key for the agent, AWS
  account and deploy role for the backend (brief 25), PJM, AESO, data.go.kr, EPIAS, RTE,
  Fingrid, NREL; `EPA_API_KEY` reached Actions empty on 2026-10-18.
- **Area levels** (brief 27, planned 2026-10-29): outlines below admin-1 (Overture divisions,
  ADM2, TIGER, ONS, IRIS, CBS buurten, GHS urban centres), rasters for sums inside any polygon
  (GHSL 100 m, WorldCover, Copernicus DEM) and consumption per small area (Agence ORE, DESNZ,
  CBS, Energi Data Service, LEAD, ACS) are missing; EU LAU needs a EuroGeographics licence for
  commercial use, the Overture divisions licence is to be confirmed.
- **Energy-Charts** answers 503 since 2026-09-24 (GB and UA keep its older figures).
- **NYISO** nodal prices: bot check on automated downloads.
- **Wave 8 families** (data/coverage.yaml, 29 places each): outlines, urban_centres, rasters,
  consumption, heating, energy_poverty, industrial, oil_gas_facilities, co2_storage,
  heat_demand, fires, flood_zones, wetlands, dams, ownership. Blocked: EFFIS burnt areas
  (request form), HRL Water & Wetness (EU Login), CO2 Stored (account), EIA midstream (token),
  NWI (403). Keys still missing: FIRMS_MAP_KEY, CENSUS_API_KEY. Research per country:
  docs/research/small-area-energy.md.
- **Wave 9** ([[wave9]]): 57 new families (17 categories) with 29 cells each, generated from the
  registry; dark cells name the probe outcome and the open-data portal search. Keys still missing
  for wave 9: CENSUS_API_KEY, NREL_API_KEY, CDSAPI_KEY, NASA_EARTHDATA_TOKEN, FINGRID_API_KEY.
