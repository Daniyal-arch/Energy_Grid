# Embeds (brief 30, Track 6.4)

## Problem

People who write about Europe's power system (newsrooms, analysts, grid operators' blogs,
teachers) want to show a live, sourced map inside their own page. A screenshot goes stale and
loses its sources; linking away loses the reader.

## Who it serves

Writers and editors who place a map in an article or a report page, and readers who then want
the full app.

## What it shows

`?embed=1` on any app URL (a dashboard `?dash=`, a hand-built view `?layers=...`, the Maps
view `?compare=1&maps=...`, a selection or a camera `?cam=`):

- the map (or the Maps view, filling the frame) as the URL describes it;
- the compact map key (the same `MapLegend` the app shows under the collapsed Layers button);
- one line of source credits (`CREDITS` in `frontend/src/ui/sources.ts`) and a link
  "Open in InfraAtlas" to the same URL without `embed=1`.

Hidden: the top bar, the Layers panel, the context panel, the time bar, the builder.

The **Embed** button sits in the Dashboards menu. It shows a copyable snippet for the view
on screen:

```html
<iframe src="https://.../?dash=...&embed=1" width="800" height="500" style="border:0" loading="lazy"></iframe>
```

## Data

Nothing new: the embed reads the same static files and live snapshots as the app, so every
figure keeps its source and refresh cycle. The URL is the whole state (`readUrl`/`writeUrl`
in `frontend/src/app/store.ts`); `writeUrl` keeps `embed=1` while embedded.

## Limits

- No panels inside the frame, so no cards or tooltips with the full figures; the reader
  follows "Open in InfraAtlas" for those.
- Day dashboards keep their clock running, but the time bar is hidden.
- Agent maps (`/api/maps/{id}`) embed only where the answer service is deployed.
- No per-site key or analytics; any page may frame the site.
