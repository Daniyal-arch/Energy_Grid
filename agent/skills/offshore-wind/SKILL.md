---
name: offshore-wind
description: "Offshore wind: zones and leases, existing farms, depth, seabed, shipping, ports, grid at the coast. Each criterion with its own source; no site score."
---
# Offshore wind

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

1. **Zones and leases.** `wave9.eu_emodnet_wind_farms`, `wave9.eu_emodnet_msp_zoning`, `wave9.us_boem_wind_leases`, `wave9.us_boem_active_leases`; military and aggregate areas (`wave9.eu_emodnet_military`, `wave9.eu_emodnet_aggregates`).
2. **Seabed and depth.** `wave9.eu_emodnet_substrate`; depth is family `bathymetry` (say what is published).
3. **Other users.** platforms and pipelines (`wave9.eu_emodnet_platforms`, `wave9.eu_emodnet_pipelines`), marine protected areas (`wave9.eu_emodnet_mpa`), shipping density (family `shipping_density`).
4. **Ports and grid.** `wave9.eu_emodnet_ports`, `wave9.world_port_index`, coastal substations and cables.

Example query (replace the area id):

```sql
SELECT count(*) FROM wave9.eu_emodnet_platforms WHERE in_area(geometry, 'a_...')
```
