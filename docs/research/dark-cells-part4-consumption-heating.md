# Dark cells, second pass (dark3), 2026-11-06

Families: `consumption` (Energy consumption per small area) for BG, HR, CY, EE, GR, HU, LU, MT, RO, SK;
`heating` (Heating fuel per small area) for BG, CY, GR, MT, US. 15 cells checked.

## New build entries (sources.yaml)

| id | place | level | what |
|---|---|---|---|
| sk_susr_energy_consumption_okres | SK | okres (79) | ŠÚ SR DATAcube en3001rr: electricity MWh, gas, heat, oil, coal per okres 2000-2024, CC BY 4.0. Covers reporting organisations of the ŠÚ SR survey (okresy sum to 14.4 TWh in 2024, about half of final use; seats in Bratislava I carry big totals), not households: label accordingly and confirm in the methodology. Download is a zip (csv_zip). |
| gr_elstat_heating_energy_regional_unit | GR | regional unit (75) | ELSTAT census 2021 Α13: households by main energy source for heating / cooking / hot water. Fuel, but NUTS 3-like level. |
| gr_elstat_heating_settlement | GR | settlement (13,586) | ELSTAT census 2021 Γ09: dwellings with central (autonomous / not), other or no heating, down to οικισμός. Heating type, not fuel. |
| us_acs_heating_fuel | US | tract | ACS 2020-2024 B25040, 10 fuels with MOE, kind census; needs CENSUS_API_KEY. |

Both ELSTAT workbooks have multi-row headers (Α13 rows 4-6, Γ09 rows 4-8) and Α13 puts the fuel name
in the area column under each area: wave9 needs a small reshape (header names by hand, carry the
area code down). ELSTAT licence: free reuse "τόσο για μη εμπορικούς όσο και για εμπορικούς σκοπούς",
source named, modifications stated (Copyright_Reuse_Policy_GR.pdf).

## Blockers

- HU: KSH (www.ksh.hu, statinfo) answers an F5 "Request Rejected" page; TEIR needs a login.
- MT: nso.gov.mt, open.data.gov.mt, rews.org.mt behind a Cloudflare challenge (403).
- RO: TEMPO-Online is plain HTTP on port 8077, not carried by the sandbox proxy; data.gov.ro and
  insse.ro silent. Probe from Actions.
- US: CENSUS_API_KEY not set (data calls redirect to missing_key.html).

## Not published / left out

- BG: heating energy asked in census 2021 but published nationally only (PDF); consumption national.
- CY: CYSTAT-DB has no heating table; energy = oil sales only.
- EE: KE07 fuel per county (archived 1991-2019) left out; no municipal electricity.
- HR, GR (consumption): nothing below the region on data.gov.hr / ELSTAT / HEDNO.
- LU: ILR dashboards (CC BY 4.0) national only.

## Probe notes

- ŠÚ SR STATdata API: `https://statdata.statistics.sk/public/api/dc/public/<cube>/info` and
  `/opendata/cube/dataset/<cube>/download?lang=SK&type=CSV` answer without login; catalogue and meta
  endpoints need one. data.gov.sk SPARQL (`https://data.slovensko.sk/api/sparql`) gives the licence per
  distribution. Other ŠÚ SR cubes with `rr` (regional) suffix may hold more okres data.
- CYSTAT-DB is a PxWeb v1 API (`https://cystatdb.cystat.gov.cy/api/v1/el/8.CYSTAT-DB`); it resets
  connections under fast walking (retry with pauses).
