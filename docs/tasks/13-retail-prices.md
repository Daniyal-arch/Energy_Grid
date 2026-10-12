# 13. What consumers pay: retail electricity and gas prices (Eurostat, EIA-861)

No keys (EIA's bulk files need none).

- **Europe, Eurostat:** `nrg_pc_204` (households, electricity), `nrg_pc_205` (non-households),
  `nrg_pc_202`/`203` (gas), half-yearly, by consumption band; all taxes, excluding VAT,
  excluding taxes (Eurostat API, CC BY 4.0). Use the standard bands (households DC
  2,500–5,000 kWh; non-households ID 500–2,000 MWh) and say so.
- **US, EIA-861 / 861M:** average retail price by state and sector (residential, commercial,
  industrial), monthly (bulk xlsx from eia.gov).

Files: `scripts/fetch_retail_prices.py` → `frontend/public/data/eu/retail.json`; monthly in
`eu-days.yml`. Map: "Colour countries by → Household electricity price" (Europe; US states
when the camera faces the US, outlines from `us/states.json`). Panels: a country/state card
"What households pay" next to the wholesale price, taxes split where Eurostat gives them.
docs/DATA_SOURCES.md section; ruff, pytest, `npm run build`; three values checked against
Eurostat/EIA (PR). Merge `origin/main` before opening the PR.
