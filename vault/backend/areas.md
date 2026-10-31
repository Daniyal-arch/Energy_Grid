---
title: Areas
tags: [backend, agent, areas]
updated: 2026-10-29
paths: [backend/data/areas.py, backend/tools/areas.py, backend/tools/area_stats.py, backend/data/duck.py, agent/areas/, agent/rasters.yaml, agent/skills/area-analysis/]
---

# Areas (brief 27 part A)

Any area the user names, draws or sees becomes one object the other tools use.

- **Area** (`backend/data/areas.py`): id `a_` + 12 hex of the SHA-256 of the normalised WKB,
  name, level, iso3 list, bbox, km² (`ST_Area_Spheroid`; the world is a constant), source,
  display geometry simplified above 20k points. `AreaStore` keeps them under
  `results_dir/areas` and the object store `agent/areas/`.
- **resolve_area** (`backend/tools/areas.py`): names (with qualifiers "Name, X" or "(X)"),
  levels, `from_view` drawn | screen | countries, point + `radius_km`, `buffer_km`,
  `intersect_with`, unions; groups from `agent/areas/groups.yaml` (eu27, nordics, cwe, atlas29...).
  Ranking: exact match, wanted level, outline before point, in view, lake outline, population.
  Ambiguity only within one level class. The lake's `outlines/names` index is searched first.
- **SQL**: `run_sql(..., areas=[ids])` registers temp table `areas` and macros `in_area(geom,
  id)`, `intersects_area`, `km_inside`, `km2_inside`; `expand_in_area` adds a literal bbox
  filter so Parquet row groups are skipped. Country and group areas: filter by the country key
  too (coastal plants fall outside 1:20M outlines).
- **area_stats** (`backend/tools/area_stats.py`, measures in `agent/rasters.yaml`): rasterio
  zonal sums/means/classes with the cell-centre rule; tiles on the GHSL grid; finest layer
  within `area_stats_max_cells` (60 M), else the next published layer (sums) or an overview
  (means, classes). Names the cell size used.
- **MapSpec**: `area` on the map and panels, `shapes` sets (admin2, lau, us_places, lsoa,
  iris, nl_buurt, `divisions:<subtype>`, `h3:<res>`); `/api/areas/*` and `/api/shapes/*`.
- Level matrix `agent/areas/levels.yaml`: which datasets exist at which level per country.
- Evals: `agent/evals/areas.yaml` (20 cases, numbers computed from app tables).

See [[agent-tools]], [[backend-service]], [[lake]].
