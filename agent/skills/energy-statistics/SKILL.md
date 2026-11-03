---
name: energy-statistics
description: "Country, world and GB local authority statistics of wave 10: Eurostat energy balances, prices, emission accounts, vehicles by fuel, SDG tables; World Bank WDI energy and climate indicators; DESNZ, DfT and Census 2021 tables per GB district. Use for a country comparison, a national or world indicator, or a figure per GB local authority."
---
# Energy statistics (wave 10)

Relies on: `search_catalog`, `describe_table`, `run_sql`, the catalogue
`agent/catalog/wave10.yaml` (one table per source, `wave10.<id>`), `resolve_area` for a GB
district or a country, and `data/coverage.yaml` (families `energy_balances`,
`energy_infrastructure_stats`, `energy_prices_taxes`, `emission_accounts`, `vehicle_fleet`,
`water_materials`, `sdg_indicators`, `world_indicators`, `local_energy_gb`,
`local_emissions_gb`, `local_homes_gb`).

1. **Find the table.** `search_catalog` with the subject ("final energy consumption",
   "electric cars", "access to electricity"); Eurostat tables are `wave10.eu_<code>`
   (e.g. `wave10.eu_nrg_bal_s`), WDI indicators `wave10.wb_<indicator>` (e.g.
   `wave10.wb_eg_elc_accs_zs`), GB tables `wave10.gb_*`. `describe_table` before the query.
2. **Eurostat tables are long SDMX tables**: one row per code combination, columns
   `freq`, the table's dimensions (`nrg_bal`, `siec`, `unit`, ...), `geo`, `time_period`,
   `obs_value`, `obs_flag`. Always filter every dimension to one code (a table mixes units:
   never sum across `unit`), and say the codes used. Greece is `EL`, the EU total `EU27_2020`.
3. **WDI tables**: `iso2`, `iso3`, `country`, `aggregate` (regions and income groups are
   `true`: leave them out of country rankings), `year`, `value`; the indicator name carries the
   unit. The original source (often IEA or UN) is in the table's note: name it with the World Bank.
4. **GB districts**: keyed by ONS code (`code`, `local_authority_code`, `geography_code`);
   workbooks stacked by year have a `sheet` column. DESNZ consumption covers Great Britain;
   Census 2021 tables England and Wales only. Resolve the district with `resolve_area` and
   filter on its code.
5. **Values as published.** Quote the period and flag; never compute a per-capita or a share the
   table does not publish unless asked, and then say it is computed and how.

Example queries:

```sql
SELECT geo, time_period, obs_value FROM wave10.eu_nrg_bal_s
WHERE nrg_bal = 'GIC' AND siec = 'TOTAL' AND unit = 'KTOE' AND geo IN ('DE', 'FR', 'PL')
ORDER BY time_period DESC LIMIT 9
```

```sql
SELECT country, year, value FROM wave10.wb_eg_elc_accs_zs
WHERE NOT aggregate AND year = (SELECT max(year) FROM wave10.wb_eg_elc_accs_zs WHERE value IS NOT NULL)
ORDER BY value LIMIT 10
```
