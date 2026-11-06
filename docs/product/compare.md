# Compare (brief 30, Track 6.3)

## Problem

"How does France's grid compare with Germany's and Spain's?" Today that takes three
selections and a notepad. The instant answers (`GET /api/quick/compare`) already compute the
same figures for two to six places with the same queries; they need a page.

## Who it serves

Analysts, journalists and students comparing countries or regions, who want one shareable
link with the figures and their sources.

## What it shows

`?compare=France;Germany;Spain` (two to six places, names as the search understands them:
countries, groups, regions, cities, zones):

- one table per measure (plants by fuel, substations by voltage, line length inside the
  area, data centres), the places as columns and the measure's rows (fuel, voltage) as rows;
- under each table its method and "as of" date, and the SQL behind it on demand;
- the sources line (dataset, licence, retrieval date) for the whole page;
- an input to change the places; it rewrites the URL so the link is shareable;
- a link opening the places in the Maps view (`?compare=1&area=FRA,DEU,ESP`).

`?compare=1` stays the Maps view; any other value is this page.

## Data

The backend's instant answer `compare` (`backend/tools/quick.py`): the area profile queries
run once per place over the app tables (powerplantmatching / GEM plants, OSM substations and
lines, data centres). A whole country or group is filtered by its country codes, a smaller
area by its outline. The page shows the numbers as returned; it computes nothing.

## Limits

- Needs the answer service (`/api/quick`). Where it is not deployed the page says "the answer
  service is not set up on this site yet" and shows no figures.
- Places in different regions (Europe, the US, elsewhere) get different measures; a cell
  with no figure shows "not in this measure".
- Line length exists only for areas smaller than a country (the query cuts lines by outline).
- Tables only; the side-by-side maps are the Maps view, one link away.
