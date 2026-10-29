---
name: make-map
description: Designing maps - existing app layers first, the 22 map styles (12 flat, 10 in 3D) and when each fits, several maps side by side, editing a map on screen, the app's palettes, legends with how the value was computed. Use when the answer is a map or the user asks to change one.
---
# Making a map

Relies on: `frontend/src/app/datasets.json` (the map's datasets and their layers), the MapSpec
schema (`agent/mapspec.schema.json`). A separate step (the cartographer) writes the spec from
your query results; your job is to query the rows each map needs.

1. Existing layers first: when an app layer already shows the answer (plants, prices, flows,
   outages, water risk, queue, grid capacity), it is switched on in `app.layers`; overlays add
   only what no layer shows.
2. Query for the design:
   - places with amounts: lon, lat, the value, a type column (dots, bubbles, columns, spikes,
     lollipops, beams, point_cloud, hexbin/grid and their 3D forms, heatmap, contour, terrain);
   - a value per country, US state or zone: the key column (ISO alpha-2/alpha-3, state code)
     and the value (choropleth, prisms, labels);
   - two variables: both columns on the same rows (bivariate);
   - composition per place: place, category, value (pies);
   - movement: from_lon, from_lat, to_lon, to_lat and the value (lines, flows, arcs_3d).
3. Several datasets or variables in one question: query each; the cartographer may put them on
   one map (two overlays at most) or on 2-6 maps side by side (`panels`), one each.
4. Edits ("make it 3D", "use hexagons", "split into two maps", "colour by fuel"): the maps on
   screen come with the request; their data is reused, no new query needed unless the user asks
   for new data.
5. Palettes (the app's own): price, price_glow, share, heat, cool, green, purple, emissions,
   room, solar, wind, fuel, plant_type (categorical), voltage, offline, neutral. Scales:
   sequential for amounts, diverging when zero or a middle matters, categorical for types.
6. Areas: when the question is about an area, its `area_id` (resolve_area) goes on the map as
   `area`; choropleths use the shapes one level below the area (area-analysis skill).
7. Legend: a short title and `how` ("sum of the plants of 20 MW and more"); `source` names the
   data source. Colours follow the data; never invent a domain or a value.
