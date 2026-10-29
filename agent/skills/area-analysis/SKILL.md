---
name: area-analysis
description: Questions about any area - a region, county, city, neighbourhood, a drawn polygon or circle, the map on screen, several places together, a buffer, a bidding zone, the world. Resolve the area, give its own figures, count and sum each dataset inside it, map it one level down, compare with peers, say what coverage is partial.
---
# Area analysis

Relies on: `resolve_area`, `area_stats`, `run_sql` (the `areas` view and `in_area`,
`intersects_area`, `km_inside`, `km2_inside`, `area_geom`), `agent/areas/levels.yaml` (which
dataset exists at which level), `agent/areas/groups.yaml` (named groups), `data/coverage.yaml`.

1. **Resolve first.** `resolve_area(names=[...])`; "here" or "this area" is
   `from_view="drawn"` when something is drawn, else `from_view="screen"`; "within 30 km of X"
   is `names=["X"], radius_km=30`; "A and B" is `names=["A", "B"]` (a union); "X and 10 km
   around it" is `buffer_km=10`. When the result says `ambiguous`, pick the candidate in view or
   ask, naming each with its parent ("Paris, France or Paris, Texas?"). When `area` is null
   with a note, say what exists instead (the municipality, the urban centre, a circle) and never
   draw an outline that is not in the data.
2. **The area's own figures** come with it: `area_km2` (geodesic) and `people` (GHSL cells whose
   centre lies inside). Quote them with their rule.
3. **Inside the area, every query filters on the server**:
   - a country or a group of countries, on a table with a country key: filter by the key
     (`country IN (...)`, from the area's `iso3`); outlines are generalised and offshore sites
     lie outside the land, so in_area would drop coastal and offshore records;
   - points, any other area: `WHERE in_area(lon, lat, 'a_...')` (the bounding box test is
     added for you) and `count(*)`, `sum(mw)`;
   - lines: `sum(km_inside(geometry, 'a_...'))` filtered with `intersects_area(geometry,
     'a_...')` and, first, the bbox columns (`bbox.xmax >= xmin AND bbox.xmin <= xmax ...` from
     the `areas` view); label "km of line inside the area (computed, geodesic)";
   - polygons: `sum(km2_inside(geometry, 'a_...')) / <area_km2>` as the share covered;
   - tables keyed by region: when the area is that region, join by its key. When the area is
     drawn or of another level, **never split a region's total by area share**: sum the regions
     wholly inside (`ST_Within(region.geometry, area_geom(...))`) and list the regions partly
     inside with their full values ("3 regions lie partly inside; their totals are shown, not
     split");
   - live figures (ENTSO-E, EIA-930) are per zone or country: name the zones the area touches
     and give their figures as such.
4. **Rasters**: `area_stats(area_id, [people, built_up, land_cover, slope, solar, wind, flood])`;
   quote the cell size it names.
5. **Which data answers at this level**: read `datasets_at_level` in resolve_area's result (from
   `agent/areas/levels.yaml`). A city question is answered with point data inside its outline,
   rasters, and tables at municipality or small-area level where the country publishes them;
   name the level used ("2023, per municipality").
6. **Maps**: query the rows; the cartographer sets `area` on the map (outline, clip, camera) and
   uses the shapes one level below (country -> nuts2/nuts3/admin1; region -> nuts3, admin2,
   divisions:county, lau; city -> divisions:neighborhood, iris, lsoa, msoa, nl_buurt; US state ->
   us_counties -> us_tracts). Up to ~20,000 points draw as dots; more as hexbin or as H3 cells
   summed in SQL (`h3_latlng_to_cell(lat, lon, 7)` with count and sum, shapes `h3:7`). Every
   record counts; none is dropped.
7. **Comparison**: with the parent area or peers when asked: resolve each and run the same query
   per area (`in_area(..., 'a_1')`, `in_area(..., 'a_2')`), or two panels each with its area.
8. **Partial coverage**: from `data/coverage.yaml` for the countries the area touches, say how
   much is covered ("12 of 14 grid operators in this area publish free capacity"; "Germany
   publishes consumption per municipality only for some Länder").
