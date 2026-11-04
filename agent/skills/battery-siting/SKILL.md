---
name: battery-siting
description: "Battery storage siting: free connection capacity and substation headroom, then price spreads and negative hours, then land and hazards. Each criterion with its own source; no site score."
---
# Battery siting

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

1. **Connection.** room to connect per substation (`connect_harmonised`), distribution headroom (`wave9.gb_npg_heatmap_substations`, `wave9.gb_nged_generation_capacity`), the queue (`usQueue` app table for the US).
2. **Revenues.** day-ahead spreads and negative-price hours per zone (skill `prices`), balancing reserve prices (`wave9.dk_energinet_reserves`; family `balancing`), capacity markets (family `capacity_markets`).
3. **Land and hazards.** flood (`area_stats` measure `flood`), protected areas, existing storage nearby (MaStR, REPD registers).

Example query (replace the area id):

```sql
SELECT sum("PriceTotalEUR" * "PurchasedVolumeTotal") / sum("PurchasedVolumeTotal") FROM wave9.dk_energinet_reserves
```
