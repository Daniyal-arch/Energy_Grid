---
name: grid-planning
description: "Grid planning: where demand grows, what is planned, where the constraints are. Each figure with its own source; no score."
---
# Grid planning

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

1. **Planned grid.** `tyndp.projects` (lines, `km_inside`), national plans (family `planned_grid`).
2. **Constraints.** congestion and redispatch (skill `grid-capacity`), curtailment events (`wave9.gb_npg_curtailment_events`), constraint costs (`wave9.gb_neso_constraint_costs`).
3. **Demand growth.** EV stock per NUTS 2 (`wave9.eu_ev_stock_nuts2`), heat pumps (`wave9.eu_heat_pumps`), data-centre consumption (`wave9.ie_cso_datacentres`), degree days (`wave9.eu_degree_days`).
4. **Connections.** room to connect and queues.

Example query (replace the area id):

```sql
SELECT geo, TIME_PERIOD, OBS_VALUE FROM wave9.eu_ev_stock_nuts2 WHERE geo LIKE 'DE%' ORDER BY TIME_PERIOD DESC LIMIT 20
```
