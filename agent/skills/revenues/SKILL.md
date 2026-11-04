---
name: revenues
description: "Balancing, capacity and support revenues for storage, flexible plants and renewables. Each market with its own source and period; no combined revenue estimate."
---
# Revenues

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

1. **Wholesale.** day-ahead prices, spreads and negative hours (skill `prices`).
2. **Balancing.** `wave9.dk_energinet_reserves` (FCR-D), `wave9.gb_elexon_balancing` (system prices); other countries per family `balancing`.
3. **Capacity and support.** families `capacity_markets` and `support_contracts` (the LCCC register is blocked: say so); network charges `wave9.gb_neso_tnuos`, `wave9.us_openei_urdb`.

Example query (replace the area id):

```sql
SELECT "ProductName", avg("PriceTotalEUR") FROM wave9.dk_energinet_reserves GROUP BY 1
```
