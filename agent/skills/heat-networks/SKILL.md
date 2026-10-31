---
name: heat-networks
description: "Heat networks: heat demand, heat sources (industry, wastewater, data centres), existing networks, geothermal. Each figure with its own source; no score."
---
# Heat networks

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

1. **Demand.** `area_stats` measure `heat_demand` (Hotmaps), degree days (`wave9.eu_degree_days`), building certificates per area (family `building_certificates`).
2. **Sources.** excess heat sites, wastewater plants (`wave9.eu_emodnet_wwtp`), data centres, geothermal heat flow (family `geothermal_heat_flow`).
3. **Networks.** district heating areas (family `district_heating`): say where none is published.

Example query (replace the area id):

```sql
SELECT count(*) FROM wave9.eu_emodnet_wwtp WHERE in_area(geometry, 'a_...')
```
