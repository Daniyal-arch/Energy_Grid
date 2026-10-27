---
title: Panels and cards
tags: [frontend, ui]
updated: 2026-10-27
paths: [frontend/src/ui/App.tsx, frontend/src/ui/LayersPanel.tsx, frontend/src/ui/Panel.tsx, frontend/src/ui/DashboardTab.tsx, frontend/src/ui/Dashboards.tsx, frontend/src/ui/Catalogue.tsx, frontend/src/components/AreaCards.tsx, frontend/src/components/RoomCards.tsx]
---

# Panels and cards

One Layers panel on the left, one context panel on the right, a time bar at the bottom ([[rules]]).

## Where
- `ui/App.tsx`: desktop and phone layouts; top bar (dashboards menu, search, Check a site, Draw an
  area, Maps button, Live / Years).
- `ui/LayersPanel.tsx` ("Datasets"): datasets on the map first, then categories; a dataset's name
  switches it on and opens its details (coverage, sources); the switch turns it off; style chips
  and a one-line key under each dataset on; `LayerLegend` per layer.
- `ui/Panel.tsx`: the context panel's tabs (Dashboard, Now, 7 days, Prices, Gas & LNG, 25 years...).
- `ui/DashboardTab.tsx`: the dashboard's area, "also with data here" chips, `MapVariables`
  ("On the map": every styled dataset with its key, "All as"), and `AreaCards`.
- `ui/Dashboards.tsx`: the dashboards menu, any country, the builder; `ui/Catalogue.tsx`: the data
  catalogue over the map; `ui/Search.tsx`: places, plants, coordinates (a city opens a 25 km circle).
- `components/AreaCards.tsx`: the area dashboard (overview, electricity, emissions, plants, grid,
  capacity, registers, demand, fuels, risk) with tiles, bars and donuts; counts by country code
  for countries, by position for drawn areas; runs card by card after the panel draws.
- `components/RoomCards.tsx`: room to connect per country (PR #13). Other cards: one file per
  family in `components/`.
