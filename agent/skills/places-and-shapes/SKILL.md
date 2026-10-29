---
name: places-and-shapes
description: Place keys and joins - ISO codes, US state and county FIPS, NUTS, bidding zones, cities - and which shapes a choropleth uses. Use when a question names places or a map shades areas.
---
# Places and shapes

Relies on: `find_place`, `resolve_area`, `nuts`, `admin1`, `bidding_zones`, `cities`,
`es_regions`, `fr_regions`, the outline sets `outlines.*` (brief 27).

1. Resolve names with `find_place` (codes, centre) or `resolve_area` (an outline with an
   `area_id`, any level); use the codes they return, never guessed ones. Questions about an
   area's contents: load the area-analysis skill.
2. Keys: Europe's countries ISO alpha-2 (`DE`; the UK is `GB`, Greece `GR`); the world's ISO
   alpha-3; US states two-letter codes; US counties five-digit FIPS strings (keep leading
   zeros); NUTS codes (`DE1`, `DE11`, ...); bidding zones as ENTSO-E names (`DE-LU`, `DK1`).
3. Shapes for a choropleth (`data.shapes`): `countries` (ISO alpha-2), `us_states`,
   `us_counties`, `nuts0`-`nuts3`, `bidding_zones`, `admin1`, and below them `admin2`, `lau`,
   `divisions:<subtype>` (Overture ids), `us_places`, `us_tracts` (GEOIDs), `lad`, `msoa`,
   `lsoa` (ONS codes), `fr_communes`, `iris` (INSEE codes), `nl_gemeente`, `nl_wijk`, `nl_buurt`
   (CBS codes), `urban_centres`, `h3:<res>` (H3 cell ids) and `area`. The query must return the
   key column in that form.
4. Points to areas: the lake's `shapes` tables join points to areas (spatial `ST_Within`); the app
   tables carry `country` already.
5. Coordinates are lon, lat in degrees (WGS84) everywhere in the data.
