# Power-grid videos (LinkedIn and other feeds)

The power view can be rendered as a vertical MP4: the German transmission grid
with dots moving along it, power plants by fuel, cross-border flows, a 48-hour
wind and solar chart and a generation legend. The framing is made for phones:
**4:5 (1080×1350)** is the tallest format the LinkedIn feed shows in-line, and
**9:16 (1080×1920)** fills the full-screen vertical player.

## Make a video

1. Start the API and the frontend (two terminals, from the repo root):

   ```sh
   uv run uvicorn app.main:app --app-dir backend --port 8000
   cd frontend && npm run dev
   ```

2. Render:

   ```sh
   cd frontend
   npm run record:video                                 # 4:5, 20 s, 30 fps
   npm run record:video -- --format 9x16 --seconds 15
   npm run record:video -- --poster-only                # one still, for a quick check
   ```

The MP4 and a poster PNG are written to `recordings/` (git-ignored), named
`power-grid-<format>-<date>.mp4` unless `--out` is given. A 20 s video takes
about 3–4 minutes on a laptop GPU (plus ~1 minute of data loading).

| Option | Default | Meaning |
|---|---|---|
| `--format` | `4x5` | `4x5` (1080×1350) or `9x16` (1080×1920) |
| `--seconds` | `20` | video length |
| `--fps` | `30` | frame rate |
| `--scale` | `2` | device pixels per CSS pixel; the page is laid out at video size / scale |
| `--poster-at` | `2` | second at which the poster PNG is taken |
| `--poster-only` | off | save just the poster PNG, no video |
| `--out` | `../recordings/power-grid-<format>-<date>.mp4` | output path |
| `--url` | `http://localhost:5173/` | dev server address |

Chrome is used headless; Edge works too. Set `CHROME_PATH` if neither is found in
the standard install location. No ffmpeg is needed.

**Preview in the browser:** open `http://localhost:5173/?capture=4x5` (or `9x16`).
The stage is laid out at half the video size, so zoom the browser to 200% to see it
as the video will look.

**Posting on LinkedIn:** upload the MP4 and use "Edit thumbnail" to set the poster
PNG; the automatic thumbnail may be a less representative frame. Use 4:5 for the
feed. LinkedIn autoplays muted, and the video starts on the finished scene.

## Content rules: everything written in the video must be real

The video is published, so its text follows one rule: **every number is a value
from a named source, passed through unchanged.** Nothing is estimated. A data point
that cannot be sourced is left out rather than approximated. The frame also shows
**no dates, times, weekdays or "live" wording**, and has no intro (it starts on
the finished scene). If a post needs the snapshot time, put it in the post text,
and note that cross-border flows are published about 2 h after generation. When
changing the overlay (`frontend/src/components/CaptureOverlay.tsx`), keep to this
table:

| Element in the video | Source |
|---|---|
| `89.1 % of generation renewable` | Energy-Charts' published "Renewable share of generation" (`renewable_share_of_generation`), same interval as the generation figures |
| Generation strip (Wind, Solar, Lignite, Hard coal, Gas, Biomass, Hydro, GW) | Energy-Charts `public_power` categories, one interval; Wind = onshore + offshore, Gas = fossil gas + coal-derived gas, Hydro = run-of-river + reservoir + pumped storage |
| Wind + solar chart, last 48 h | Energy-Charts `public_power` series via `/grid/history` |
| Cross-border labels (`NL export 3.9 GW` …) | Energy-Charts `cbpf` (physical flows), newest complete interval; positive = import into Germany. Idle links (under 20 MW) keep their line but get no label |
| Grid lines and substations | OpenStreetMap 220/380 kV lines (merged corridors), substations where corridors meet |
| Plant circles | MaStR operating units (open-mastr snapshot), grouped in ~28 km cells at this zoom, larger groups shown; size = capacity |
| City names | fixed list, for orientation only |

Rules that are easy to break:

- A metric is shown only if its timestamp equals the generation interval's; mixed
  intervals are dropped rather than shown side by side.
- Values the project computes itself are **not** used in the video. That includes
  the backend's `renewable_share` (own definition), `carbon_intensity` (uses assumed
  emission factors) and plant-to-substation links (nearest substation, not the real
  connection point).
- Dots on lines **inside** Germany show a typical north→south direction, because
  per-line flows are not published. The credits say so. Keep that line. Dots on
  cross-border links follow the real sign of the flow.
- The credits carry the required attributions: © OpenStreetMap contributors,
  © EuroGeographics (GISCO boundaries) and © CARTO (basemap).

## How it works

- `?capture=4x5|9x16` (`frontend/src/lib/capture.ts`) turns the app into a fixed
  stage: the power scene opens by itself, the map is framed to Germany and its
  neighbours, interaction and the app UI are off, and `CaptureOverlay` draws the
  title, chart, legend and credits. The page sets `window.__captureReady` only once
  generation, flows and the 48 h series have all loaded (the history call is
  retried for about 80 s). If something never loads, the recorder stops with an
  error instead of rendering an incomplete video.
- `frontend/scripts/record-video.mjs` starts headless Chrome at the stage size with
  `deviceScaleFactor = scale`, and installs a **virtual clock** before any page
  script runs (`performance.now`, `Date.now` and `requestAnimationFrame` all read
  it). Once the page is ready, it steps the clock by exactly 1/fps per frame and
  takes a screenshot, so motion is perfectly even however slowly the GPU renders.
  Anything animated on the capture page must therefore run on
  `requestAnimationFrame`/`performance.now`, not CSS animations.
- Frames are encoded to H.264 inside Chrome with WebCodecs and written by a small
  built-in MP4 muxer (ftyp/moov/mdat, faststart), so no external tools are needed.

## Data freshness

- `/grid/latest` and `/grid/exchange` fall back to Energy-Charts directly when the
  database is unreachable **or its newest rows are older than 3 hours**. Old rows
  are therefore never presented as the current state.
- Energy-Charts publishes the newest 15-minute interval before every operator has
  reported. Missing neighbours show up as 0 and are filled in later, so the backend
  uses the newest *complete* interval (`power_live.newest_complete_index`).

## Troubleshooting

- **"page never became ready"**: the API is not running, or one of `/grid/latest`,
  `/grid/exchange`, `/grid/history` returns nothing. Energy-Charts calls take ~1 s;
  when the Supabase host does not resolve, each API call first waits for that to
  fail (several seconds). Check e.g.
  `curl "http://localhost:8000/grid/history?metric=gen_wind&hours=48"`.
- **Do not edit frontend files while a recording runs**: the page is served by
  the Vite dev server, and a hot reload in the middle breaks the recording.
- **Blank map in the video**: headless Chrome could not create a WebGL context. The
  recorder passes `--enable-unsafe-swiftshader` as a software fallback (slower).
