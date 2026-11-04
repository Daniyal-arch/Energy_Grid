---
name: industrial-decarbonisation
description: "Industrial decarbonisation: clusters, emissions, heat, CO2 storage, hydrogen, water. Each figure with its own source; no score."
---
# Industrial decarbonisation

Relies on: `resolve_area`, `run_sql` (`in_area`, `km_inside`, `km2_inside`), `area_stats`,
`describe_table`, the catalogue (`agent/catalog/wave9.yaml` and the earlier entries) and
`data/coverage.yaml` for what each country publishes.

**Rules for every step.** Resolve the area first (`resolve_area`; skill `area-analysis`). Each
criterion is answered on its own, with its source, its date and its level ("published per NUTS 2",
"per county"). There is **no composite score**: never weight, rank or combine criteria into one
number or a "best site"; list the evidence per criterion and let the reader weigh it. A missing
source is reported as missing, with the coverage cell's reason (`data/coverage.yaml` family named
below; "not published in <country>: <note>"), never filled with an estimate. Positioned tables are
queried with `in_area(geometry, '<area id>')`; tables keyed by region join on the region code;
rasters go through `area_stats`. Wave-9 tables are `wave9.<id>` (catalogue `agent/catalog/wave9.yaml`,
levels `agent/areas/levels.yaml`).

Run the checklist in order:

1. **Clusters and emissions.** ETS installations, EEA industrial releases (`industrial.*`), US GHGRP.
2. **Heat.** excess heat (`hotmaps.industrial_sites`), heat demand (`area_stats` measure `heat_demand`).
3. **CO2 and hydrogen.** CO2StoP, `wave9.us_epa_class_vi` when built, hydrogen projects, salt caverns (family `h2_storage_potential`).
4. **Fuels.** biogas, landfill gas and biofuel plants (`wave9.us_epa_lmop`, `wave9.us_eia_ethanol`, `wave9.us_eia_biodiesel`).

Example query (replace the area id):

```sql
SELECT count(*) FROM wave9.us_epa_lmop WHERE in_area(geometry, 'a_...')
```
