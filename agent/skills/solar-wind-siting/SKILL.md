---
name: solar-wind-siting
description: "Solar and wind siting: resource, connection, land constraints, land quality and prices, hazards. Each criterion with its own source; no site score."
---
# Solar wind siting

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

1. **Resource.** `area_stats` measures `solar` (PVOUT) and `wind` (mean speed at 100 m).
2. **Connection.** room to connect, substations, lines (`km_inside`).
3. **Land.** protected areas, acceleration areas where designated (family `acceleration_areas`), farmland quality (`wave9.gb_ne_alc`), land prices per NUTS 2 (`wave9.eu_land_prices`), heritage and aviation (`wave9.gb_he_listed`, `wave9.us_nrhp`, `wave9.world_ourairports`, `wave9.world_ourairports_navaids`).
4. **Hazards.** flood, slope (`area_stats` measure `slope`), land cover.

Example query (replace the area id):

```sql
SELECT count(*) FROM wave9.world_ourairports WHERE in_area(geometry, 'a_...') AND type IN ('large_airport', 'medium_airport')
```
