---
name: physical-risk
description: "Physical climate and hazard risk to grid assets and plants: flood, wildfire, drought, storms, earthquakes, heat. Each hazard with its own source and period; no combined risk score."
---
# Physical risk

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

1. **Assets.** plants, substations and lines inside the area (counts, MW, km).
2. **River and coastal flood.** `area_stats` measure `flood`; `wave9.gb_ea_flood_zones` (England); FEMA NFHL in place for the US (family `flood_zones`).
3. **Wildfire, drought, storms.** `w8` fires, `wave9.us_drought_monitor`, `wave9.us_noaa_storm_events` (damage as published); EU drought and wildfire hazard per family cell.
4. **Earthquake and heat.** families `earthquake` and `heat_projection`: report what the cell says when nothing is built.

Example query (replace the area id):

```sql
SELECT event_type, count(*), sum(TRY_CAST(replace(damage_property, 'K', '') AS DOUBLE)) FROM wave9.us_noaa_storm_events WHERE in_area(geometry, 'a_...') GROUP BY 1
```
