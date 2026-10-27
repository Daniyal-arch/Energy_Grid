# How the map shows data (the owner's design, 2026-10-22/23)

The owner's requirements, collected from the sessions of 22 and 23 October 2026, and their state.
Read this before changing how anything is drawn. Every item applies to every layer, to countries,
cities, drawn polygons and to future datasets.

## Requirements

1. **Clean at every scale.** Many datasets on the map still read clearly. Country scale: data
   summarised (hexagons, bivariate); site and city scale: every record as a point.
2. **Several maps of one place.** A country (city, polygon) can be shown in up to six maps at
   once, one theme each, one camera for all. "Germany in detail" opens this way.
3. **Adding a dataset asks:** show it on top of the current map, or add it as a new map (six at
   most).
4. **The Dashboard shows every selected dataset's figures**, with the chart that fits: bars,
   donuts (pie), tiles, lists.
5. **Styles, the same menu everywhere:**
   - points: bubbles sized by the value (capacity, tonnes, count), 3D bars, 3D beams, hexagons;
   - continuous data and rasters (solar and wind resource, flood, population): the raster as
     published, a simple choropleth (hexagon mean), 3D terrain;
   - lines: lines.
6. **Colours relative to the scale.** At Europe scale the classes compare countries; in a city they
   spread over that city's range (classes recomputed for what is in view).
7. **Emitters everywhere:** shown consistently at world, Europe, country, city and polygon scale.
8. **Grid capacity consistent** for every EU country, the UK and the US: one schema, one
   symbology, every operator that publishes (brief docs/tasks/23-grid-capacity-harmonised.md).
9. **Nothing switches by itself and breaks another view:** a selected country's 3D bars and beams
   for its plants keep working.

## State

| # | State | Where |
|---|---|---|
| 1 | Every dataset with figures has a style (below); hexagons and bubbles summarise at any scale, the hexagons keep their size on screen (1–45 km), so a city shows its own detail. A country's dashboard opens as themed maps, one theme each, so no map is crowded. | map/styleLayers.ts, map/hexLayers.ts |
| 2 | Done. The Maps view: up to six maps of the area, one camera (the map being moved leads), each a full map (land, labels, grid tiles) drawn by the same code as the main map, each with its datasets, styles, keys and sources; ✕ removes a map, "+ Add a map" adds one. Country dashboards open in it; the top bar's "Maps" button opens it for anything else. The main map pauses meanwhile. | ui/MapsView.tsx, app/maps.ts |
| 3 | Done. Switching a dataset on while others are on asks: "On this map" (or "On map N" in the Maps view) or "As a new map" (the current map becomes map 1). | ui/LayersPanel.tsx |
| 4 | Area cards with tiles, bars and donuts; the cards of the datasets on the map first. Every dataset with figures has a card. | components/AreaCards.tsx |
| 5 | Done. Records: Points (the dataset's own drawing), Bubbles, Hexagons, 3D bars, 3D beams. Rasters (solar, wind, flood): Raster (as published), Choropleth (hexagon mean of the grid's cells), 3D terrain. Lines: their own drawing. The same chips in the Layers panel, the Dashboard tab ("On the map", with "All as") and on each map of the Maps view; a 3D style tilts the map. | map/styleLayers.ts, ui/StyleControls.tsx |
| 6 | Done. Sizes, heights, hexagon strength and raster ramps are scaled to what is in view; two hexagon datasets: classes are the thirds of the hexagons in view. | map/styleLayers.ts, map/hexLayers.ts |
| 7 | Emitters (EU ETS and EPA GHGRP) default to hexagons at every scale, the same for both files; verified CO₂ as figures at every scale. The EU ETS places only the installations the EEA links (Germany 78 of 1,818). | app/styleDefaults.ts, lib/measures.ts |
| 8 | Brief written for a cloud session; until then the style menu draws the operators' points in four classes. | docs/tasks/23-grid-capacity-harmonised.md |
| 9 | Done. No style changes with the zoom; a dataset keeps its style until one is chosen. A selected country's plant 3D bars and beams (Points style) work again. | map/MapCanvas.tsx |
