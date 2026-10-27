---
name: site-screening
description: Screening a site for a load or a plant (data centre, electrolyser, solar or wind park, battery) - the site figures, room to connect, constraints and how to compare places. Use for "is X a good place for ..." and site comparisons.
---
# Site screening

Relies on: the `site_figures` tool (the "Check a site" panel's sources), `connect_harmonised`,
`connect_eu`, `capareseau`, `econnextion`, `elia_hosting`, `eredes_capacity`, `pse_capacity`,
`protected`, `flood`.

1. Resolve the place (`find_place`), then call `site_figures(lon, lat, radius_km)`; 50 km is the
   panel's default (choices 5, 10, 25, 50, 100).
2. Report what the figures say, each with its source: substations nearby and their voltage, the
   nearest one, plants by status, the zone's day-ahead average and hours below zero, water risk.
3. Room to connect: query `connect_harmonised` (or the country's table) for nodes near the site;
   load questions use `mw_load` / `class_load`, generation `mw_gen` / `class`. Follow the
   grid-capacity skill for summing.
4. Never score or rank a site with a made-up formula. Compare places figure by figure, side by
   side, and say which figures favour which place.
5. Say what is not covered: line distances come from the map's tiles (only in the app), and some
   countries publish no connection capacity (data/coverage.yaml).
