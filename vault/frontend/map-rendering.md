---
title: Map rendering
tags: [frontend, map]
updated: 2026-10-31
paths: [frontend/src/map/MapCanvas.tsx, frontend/src/map/build.ts, frontend/src/map/style.ts, frontend/src/map/tiles.ts, frontend/src/map/areaLayers.ts, frontend/src/map/tooltip.ts, frontend/src/map/memo.ts]
---

# Map rendering

MapLibre draws the globe, the land, labels and every tiled layer; deck.gl draws everything else
inside MapLibre's WebGL context. State comes from [[state-and-datasets]]; dataset styles from
[[styles-and-maps-view]].

## Where
- `map/MapCanvas.tsx`: the main map. A requestAnimationFrame loop: `wantedKeys` loads files,
  clocks advance (24 h replay, years), `applyStyles` turns the store's layers into the frame's
  layers, `applyMapLibre` (land colours, tiles via `tileSync`), then `buildLayers(frame)` into the
  MapboxOverlay. It pauses while the Maps view is open (`compare`). Globe below zoom 7, flat
  (mercator) above it and for any tilted 3D view.
- `map/build.ts`: `Frame` (everything a frame needs; `scope` is "main" or "mapN") and
  `buildLayers(frame)`: Europe's countries, summaries, coverage tint, hexagons and styled
  datasets, then every dataset's own layers (flows, prices terrain, plants, grid, gas, the world,
  the US...), then `areaLayers` and `clipToArea`. Labels are a MapLibre GeoJSON source
  (`labelsOf()`).
- `map/style.ts`: the MapLibre style (`STYLE`), add-functions for tiled layers (world and US grid,
  predicted grid, GRW, protected areas, flood, roads, atlases), per-map line filters
  (`setWorldGridOutside`, `setAreaWithin`), camera presets.
- `map/tiles.ts`: `tileSync(map)`: adds and shows the tiles of what is on, kept to the area.
- `map/areaLayers.ts`: coverage tint (`coverageLayers`, under the data), the area veil, outline
  and drawing; `clipToArea` keeps only records inside a country or drawn area (by each layer's
  position, path or polygon accessor; continents are not clipped).
- `map/agentLayers.ts`: the agent's 22 map styles (`Frame.agent`), keys in `useAgentKeys`,
  hover cards (`agentTip`); deck.gl aggregation layers for heatmap and contour.
- `map/tooltip.ts`: hover cards by layer id; `map/memo.ts`: memoised layer data by name.

## How it works
- A layer's data array keeps its identity across frames (memo) so deck.gl uploads nothing new.
- A selected country in live mode shows every plant unit as 3D bars or beams (`plantStyle`).

> [!warning] Shared memo slots
> Memo keys are global: anything that differs per map must include `fr.scope` in its key.
- **Wave 8 layers** (`map/wave8Layers.ts`): industrial facilities, dams, CO₂ storage, excess
  heat (points from `w8/*.json`) and fires (NIFC perimeters, FIRMS detections); hover cards list
  the published fields with the source. Agent areas draw as `shape` specs (`lib/area.ts`).
- **Wave 9 layers** (`map/wave9Layers.ts`): one scatter layer per `w9:<id>` file, colour by group.
- **Wave 9 tiles and colourings**: `map/wave9Tiles.ts` (MapLibre vector layers per source, minzoom
  by size, click popup); `w9c_` colourings in `countryColour` and county polygons in wave9Layers.
