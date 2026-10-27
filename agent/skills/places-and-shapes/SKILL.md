---
name: places-and-shapes
description: Place keys and joins - ISO codes, US state and county FIPS, NUTS, bidding zones, cities - and which shapes a choropleth uses. Use when a question names places or a map shades areas.
---
# Places and shapes

Relies on: `find_place`, `nuts`, `admin1`, `bidding_zones`, `cities`, `es_regions`, `fr_regions`.

1. Resolve names with `find_place` first; use the codes it returns, never guessed ones.
2. Keys: Europe's countries ISO alpha-2 (`DE`; the UK is `GB`, Greece `GR`); the world's ISO
   alpha-3; US states two-letter codes; US counties five-digit FIPS strings (keep leading
   zeros); NUTS codes (`DE1`, `DE11`, ...); bidding zones as ENTSO-E names (`DE-LU`, `DK1`).
3. Shapes for a choropleth (`data.shapes`): `countries` (ISO alpha-2), `us_states`,
   `us_counties`, `nuts0`-`nuts3`, `bidding_zones`, `admin1`. The query must return the key
   column in that form.
4. Points to areas: the lake's `shapes` tables join points to areas (spatial `ST_Within`); the app
   tables carry `country` already.
5. Coordinates are lon, lat in degrees (WGS84) everywhere in the data.
