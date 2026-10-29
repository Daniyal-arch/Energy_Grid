---
title: State and datasets
tags: [frontend, state]
updated: 2026-10-29
paths: [frontend/src/app/store.ts, frontend/src/app/datasets.json, frontend/src/app/datasets.ts, frontend/src/app/maps.ts, frontend/src/app/data.ts, frontend/src/app/areaShape.ts, frontend/src/lib/area.ts]
---

# State and datasets

The app's state is one zustand store mirrored in the URL; the datasets users browse are one JSON
registry. Drawing is in [[map-rendering]]; styles and the Maps view in [[styles-and-maps-view]].

## Where
- `frontend/src/app/store.ts`: `useApp` (mode live / day / years, `layers` by `LayerId`,
  `colour`, `selection`, `area` (ISO alpha-3 list), `drawn` (polygon or circle), `dashboard`,
  `compare` (Maps view open), `maps` (MapPanel[]), `mapStyles` (dataset id to style), ...),
  `actions`, `DASHBOARDS` presets, URL read and write (`layers`, `area`, `poly`, `circle`,
  `dash`, `compare`, `maps`, `styles`, `cam`...), `findDashboard` (also `country:XXX`).
- `frontend/src/app/datasets.json` + `datasets.ts`: 63 datasets (category, parts with `layer`,
  `where` (ISO codes or World, Europe, EU, US), what, source, doc; optional `colour` for the
  country colourings, `family` for `data/coverage.yaml`). Helpers: `DATASET_BY_ID`, `datasetOn`,
  `datasetsOn`, `toggleDataset`, `covers`, `partsIn(d, mode)`, `layersOfDatasets`,
  `coverageIso3`, `inAreaCountry`, `countryDashboards` (any country's dashboard).
- `frontend/src/app/maps.ts`: Maps view themes (`THEMES`, `defaultMaps(area)`, `panelOf`), the
  `Style` type. `app/styleDefaults.ts`: `DEFAULT_STYLE` (emitters as hexagons), `styleOf`.
- `frontend/src/app/data.ts`: file loaders by key (`bundled`, `bundledUs`, `snapshot` from
  `eu-data`, `archive` from `eu-days`), `ensure(key)`, `useFile`, `fileOf`, `useDataStore`.
- `frontend/src/app/areaShape.ts` + `lib/area.ts`: area shapes (countries, drawn polygons,
  circles), `inside`, `pick`, `kmInside`, `readGrid` (range reads of lookup grids on R2).

## How it works
- A dashboard sets layers, colour, area and camera; a country dashboard opens the Maps view.
- `edited` marks a changed dashboard; "Save as dashboard" keeps it in localStorage.
- Every file a map needs is listed by `wantedKeys(zoom, layers)` in `map/MapCanvas.tsx`; a
  country's own files load only for the dashboard's countries.
- **Wave 8**: LayerIds `w8Industrial`, `w8Dams`, `w8Co2Storage`, `w8ExcessHeat`, `w8Fires`;
  datasets.json entries carry their coverage `family`; `?aid=` opens an agent area; the
  camera's `box` goes to the agent with drawn shapes (`viewOf`).
