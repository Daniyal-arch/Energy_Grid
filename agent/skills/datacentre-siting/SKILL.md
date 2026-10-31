---
name: datacentre-siting
description: "Data-centre and large-load siting: where power is available soonest, then fibre, water, land, permitting and incentives, in that order. Each criterion with its own source; no site score."
---
# Datacentre siting

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

1. **Power.** free capacity and queues near the area: `connect_harmonised` (room to connect), `app.eu_substations` and `overture_power.sites` (substations), the grid lines (`app.eu_lines`, km inside with `km_inside`), large-load figures (`wave9.ie_cso_datacentres`, family `large_load`), distribution headroom where published (`wave9.gb_npg_heatmap_substations`, family `distribution_data`).
2. **Fibre and exchanges.** sea cables and existing data centres on the map (`cables`, `app.data_centres`); PeeringDB is left out (its terms forbid commercial reuse): say so. Broadband per region: `wave9.eu_broadband_nuts2` (EU, NUTS 2), Ofcom and FCC are blocked (family `broadband`).
3. **Water.** water stress (`aqueduct` in the lake) and abstraction (`wave9.eu_water_abstraction`, country level; `wave9.us_usgs_water_use`, per county), wastewater plants for cooling water or heat (`wave9.eu_emodnet_wwtp`).
4. **Land and hazards.** protected areas (`protected.natura2000`, `km2_inside`), flood (`area_stats` measure `flood`; `wave9.gb_ea_flood_zones`), farmland quality where published (`wave9.gb_ne_alc`), brownfield registers (`wave9.gb_brownfield_register`).
5. **Permitting and incentives.** major consents (family `energy_consents`), transition areas (`wave9.us_opportunity_zones`; family `transition_areas`), public funding (`wave9.eu_kohesio_2014_2020`).

Example query (replace the area id):

```sql
SELECT count(*) AS substations FROM app.eu_substations WHERE in_area(geometry, 'a_...')
```
