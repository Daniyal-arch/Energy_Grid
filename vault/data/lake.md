---
title: Lake
tags: [data, lake]
updated: 2026-10-27
paths: [docs/DATA_LAKE.md, agent/catalog/]
---

# Lake

Full-detail Parquet for the agent, on R2. The full standard is `docs/DATA_LAKE.md`; the agent's
use of it is in [[agent-backend]].

## Facts
- Bucket `infraatlas-raw` (private), prefix `lake/`. Layout
  `lake/<dataset>/<table>/<partition>=<value>/part-<n>.parquet` (Hive), small tables as one file.
- Catalogues: `lake/<dataset>/_catalog.json` per dataset and `lake/_catalog.json` for all (rows,
  bytes, columns, partitions, licence, script); `lake.duckdb` holds views over the files.
- Written only by GitHub Actions; files ≤ 250 MB; snapshots never overwritten. About 4 GB today
  (estimate in `docs/DATA_LAKE.md` §7, replaced by the measured catalogue).
- The rule: API or Parquet (`docs/DATA_LAKE.md` §1): live and small current-state sources are
  read by API; history and big registers live in the lake.
- Meaning for the agent: one YAML per dataset in `agent/catalog/` (grain, keys, measures with
  units, time range, joins, example questions with answers that double as evals).
- Shapes for joins: countries, US states and counties, NUTS 0–3, bidding zones, world admin-1,
  GeoNames cities (lake `shapes/`).
