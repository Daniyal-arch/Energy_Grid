---
name: ev-electrification
description: "EV uptake and electrification: vehicles per area, chargers, heat pumps, rooftop solar. Each figure with its own source and level; no score."
---
# Ev electrification

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

1. **Vehicles.** `wave9.eu_ev_stock_nuts2` (NUTS 2), `wave9.fr_ore_ev_commune` (France per commune), `wave9.gb_ulev_la` and `wave9.gb_dft_veh0142` (GB), US per family `ev_registrations`.
2. **Chargers.** EV charging points (`ev_eu`, AFDC).
3. **Heat pumps and solar.** `wave9.eu_heat_pumps`, rooftop solar per family `rooftop_solar`.

Example query (replace the area id):

```sql
SELECT LIBGEO, NB_VP_RECHARGEABLES_EL FROM wave9.fr_ore_ev_commune ORDER BY DATE_ARRETE DESC LIMIT 10
```
