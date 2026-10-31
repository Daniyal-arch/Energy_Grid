---
name: public-money
description: "Public money and incentives: grants, loans, tax-credit and transition areas, ownership. Each figure with its own source; no score."
---
# Public money

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

1. **Grants and loans.** `wave9.eu_kohesio_2014_2020` (cohesion projects), US awards (family `public_funding`).
2. **Areas.** `wave9.us_opportunity_zones`, energy communities and just-transition territories (family `transition_areas`).
3. **Ownership.** GEM ownership (`gem_ownership.*`).

Example query (replace the area id):

```sql
SELECT count(*) FROM wave9.us_opportunity_zones WHERE intersects_area(geometry, 'a_...')
```
