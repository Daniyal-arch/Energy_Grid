---
title: Styles and the Maps view
tags: [frontend, map, design]
updated: 2026-10-27
paths: [frontend/src/map/styleLayers.ts, frontend/src/map/hexLayers.ts, frontend/src/lib/measures.ts, frontend/src/lib/rasterCache.ts, frontend/src/ui/MapsView.tsx, frontend/src/ui/StyleControls.tsx, frontend/src/ui/MapVariables.tsx, docs/VISUALIZATION.md]
---

# Styles and the Maps view

The owner's design (`docs/VISUALIZATION.md`, its state table is kept current): one style menu for
every dataset, the same on the main map and in the Maps view; nothing switches by itself; sizes
and colours relative to what is in view. Rendering basics in [[map-rendering]].

## Styles
- Records: Points (the dataset's own drawing), Bubbles (area by value), Hexagons (sums per
  hexagon, about the same size on screen), 3D bars, 3D beams (about 90 px tall for the largest in
  view at any zoom). Rasters: Raster (tiles as published), Choropleth (mean of the grid's cells
  per hexagon), 3D terrain. Lines: their own drawing.
- `lib/measures.ts`: one figure per record per dataset (`MEASURES`, `measureOfDataset`):
  plants MW, registers MW, verified CO₂, Climate TRACE CO₂e, EV points, data centres, GEM
  industry and fuels, hydrogen, offshore wind, substations, room to connect (free MW for
  generation from `connect/harmonised.json`). `RASTERS`: solar, wind, flood lookup grids.
- `map/styleLayers.ts`: `applyStyles(layers, styles)` (a styled dataset's own layers step aside),
  `styleLayers(frame)`, `useStyleInfo` (each map's key figures), empty notes.
- `map/hexLayers.ts`: hexagons; two hexagon datasets make a 3×3 bivariate map (terciles in view).
- `lib/rasterCache.ts`: raster cells for a box (one range request, retried after 10 s on failure).

## Maps view
- `ui/MapsView.tsx`: up to six maps (`maps` in the store), each a MapLibre map with its own
  overlay drawn by `buildLayers` with its own `scope`; one camera (the map being moved leads).
  Small keys at the top left (title, style drop-down, one line per dataset, "about" for the
  explanation and sources). Country dashboards open it; the top bar's Maps button too.
- Adding a dataset asks: on this map, on map N, or as a new map (`ui/LayersPanel.tsx` `AddChoice`).
