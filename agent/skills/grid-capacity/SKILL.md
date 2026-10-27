---
name: grid-capacity
description: Room to connect (hosting capacity) published by grid operators - the four classes, MW versus MVA, the summable rule, queues. Use for questions on where a load or plant can connect and how much capacity is free.
---
# Grid capacity

Relies on: `connect_harmonised` (every operator in one schema), `connect_eu`, `capareseau`,
`econnextion`, `elia_hosting`, `eredes_capacity`, `pse_capacity`, `mastr_grid`.

1. The four classes (`class` for generation, `class_load` for demand): `available`, `limited`,
   `queue`, `none` - the operator's own class mapped one to one. An operator that publishes MW
   only is `available` above 0 MW and `none` at 0. Nothing is estimated.
2. MW and MVA: `mw_gen` / `mw_load` are MW as published; `mva_gen` / `mva_load` are MVA (or kVA /
   1000) and are never converted to MW.
3. The summable rule: sum free capacity only where the operator's values are independent.
   Red Eléctrica's transmission nodes share capacity within a zone: do not sum them. When in
   doubt, list the nodes instead of summing.
4. Queues (`mw_queue`, US interconnection queues) are MW waiting, not free capacity.
5. Countries that publish classes per area (the Netherlands) have no MW: count areas by class.
6. Always say the operator and the publication date of the record.
