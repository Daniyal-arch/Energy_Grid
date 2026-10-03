# Europe InfraAtlas — plan

## Scope

One product: an interactive, source-backed map of Europe's power system that people
can explore and that works as LinkedIn-ready video. It is a static site (frontend +
JSON files built by scripts); there is no backend, database or AI agent.

The earlier Germany atlas is archived in the git tag `germany-atlas-final`.

## What exists

- Europe view: grid, plants, substations, gas, cross-border flows (chevrons), country
  shading by renewable share or day-ahead price, EU panel.
- Country focus: tilted camera, every unit >= 1 MW as bars or beams & fields, country
  panel (load, generation, prices per zone, flows, installed capacity, reservoirs, gas).
- 24 h replay of the latest flows; full-day time-lapse of one real day (`?day=`).
- Data pipeline: `scripts/` builds static files; `.github/workflows/eu-snapshot.yml`
  refreshes flows, prices, generation and reference figures onto the `eu-data` branch.
- Video capture: `?capture=16x9` tour and `frontend/scripts/record-video.mjs`.

## Next (in order)

1. **24 h time-lapse polish and video** — review in the app, then record.
2. **Live site** — deploy the static frontend (Cloudflare Pages recommended), mobile
   layout, link preview card, cookie-free analytics.
3. **Europe's gas security** — storage fill per country (GIE AGSI+, needs a free
   key), LNG send-out, pipelines; summer to winter.
4. **World power transition 2000–2025** — global time-lapse from Ember yearly data.

Smaller: country name + one defining number while the camera flies in; an opening
zoom from space; 4:5 exports for mobile feeds.

## Possible products later

The map is the shop window. Paying use cases in this space are grid-connection and
site intelligence for developers and clean, merged datasets (plants, grid, flows,
prices) delivered as reports or an API.
