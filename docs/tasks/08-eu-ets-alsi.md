# 8. CO₂ per plant in Europe (EU emissions register) and LNG per terminal (GIE ALSI)

`AGSI_API_KEY` (GIE; the same key serves ALSI) must be a cloud **network secret**: header
`x-key` on `alsi.gie.eu` and `agsi.gie.eu`. Scripts send that header from `AGSI_API_KEY` when
the variable is set (GitHub Actions has it as a repo secret) and no key otherwise.

## Part A: verified emissions per installation (yearly)

Probe (`scripts/probe_eu_ets.py`) the candidates and pick the one that gives an installation's
**location and verified CO₂** without estimating:
1. the Union Registry's yearly compliance data (installation, permit, verified emissions;
   addresses, no coordinates),
2. the EEA Industrial Emissions Portal (facility coordinates and reported CO₂, linked to
   EU ETS installation ids where available),
3. EEA's EU ETS data viewer (aggregates only).
Join on official identifiers only; an installation that cannot be placed by an id is counted,
not geocoded by name.

Files: `scripts/fetch_eu_ets.py` → `frontend/public/data/eu/ets.json` (per installation: lon,
lat, country, name, activity, verified t CO₂ per year for the last years). Map: layer
"CO₂ per installation" (Europe; dots by tonnes, colour by activity: power, steel, cement,
refineries…); country card "Largest emitters"; hover with the years.

## Part B: LNG send-out per terminal (daily)

GIE ALSI API (`https://alsi.gie.eu/api`): per terminal and day send-out (GWh/d), inventory,
capacity. Files: `scripts/fetch_alsi.py` → `lng_terminals.json` (last 30 days); the GEM LNG
terminal layer's hover and the country "Gas & LNG" tab show today's send-out and the 30-day
line; the gas flow layer's LNG sources can name the terminals.

## Both

docs/DATA_SOURCES.md sections; refresh in `.github/workflows/eu-days.yml` (ALSI daily, ETS
when the yearly release changes); ruff, pytest, `npm run build`; three values checked
against the registry / ALSI website (in the PR).
