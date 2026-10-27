---
name: make-map
description: Building a MapSpec - existing app layers first, which overlay kind fits, the app's palettes and scales, legends with how the value was computed, calm maps. Use when the answer is a map.
---
# Making a map

Relies on: `frontend/src/app/datasets.json` (the map's datasets and their layers), the MapSpec
schema (`agent/mapspec.schema.json`).

1. Existing layers first: when an app layer already shows the answer (plants, prices, flows,
   outages, water risk, queue), switch it on in `app.layers` and frame it with `camera`; add an
   overlay only for what no layer shows. `search_catalog` returns map datasets with their layers.
2. Kind: rows with lon/lat -> `points` (size by MW, colour by type); a value per country, zone,
   state or county -> `choropleth` (`data.key` + `data.shapes`); flows between places -> `arcs`;
   heights at places -> `columns`; a few names -> `labels`.
3. Palettes (the app's own): `price` and `price_glow` (EUR/MWh, diverging around zero),
   `share` (0-100 %), `offline` (GW out), `solar`, `wind`, `fuel` and `plant_type`
   (categorical), `voltage`, `neutral`. Scale: `sequential` for amounts, `diverging` when zero or
   a middle matters, `categorical` for types.
4. Legend: a short title and `how` ("sum of the plants of 20 MW and more", "mean of the hourly
   prices"). `source` names the data source of the result.
5. Calm: one or two overlays, sizes within bounds, no extra colours. Colours are relative to
   what is in view; never invent a domain.
6. The map needs the rows: query them with the key or lon/lat columns the overlay uses.
