# Videos (LinkedIn and other feeds)

The Europe view can be recorded as an MP4 exactly as it looks in the browser, with a
drawn mouse cursor as the only addition. Only the frontend dev server is needed.

## Europe tour (16:9)

The whole map first, then the cursor clicks France, Italy, Poland and Germany in
turn; each country opens in the "Beams & fields" plant style.

```sh
cd frontend
npm run dev                                   # in one terminal
npm run record:video -- --format 16x9 --viewport 1525x740 --scale 1.25 \
  --seconds 38 --poster-at 12 --name europe-tour --url "http://localhost:5173/"
```

- `--viewport` is the page size in CSS pixels: the inner size of the browser window
  to imitate. 1525x740 is a maximised Edge window on a 1920x1080 laptop screen at
  125 % Windows display scaling (Settings > System > Display > Scale; the browser's
  own zoom is separate and should be 100 %).
- `--scale` is that display scaling (1.25), so text and panels are drawn at the same
  sharpness and proportions as on the screen.
- The 1906x925 picture is centred in the 1920x1080 frame with thin bars in the map's
  background colour; it is never stretched.

The tour script is `TOUR` in `frontend/src/components/EuropeView.tsx` (capture mode
`?capture=16x9`). Headless Chrome has no OS cursor, so the page draws one, with a
ripple on each click. When the next country is out of view, the cursor first clicks
the panel's close button so the camera returns to Europe. 38 s at 30 fps takes about
13 minutes on a laptop GPU.

## 24-hour time-lapse

`?day=2026-09-24` plays that day in about 36 s (`&daySeconds=` to change). With
`?capture=16x9&day=...` the recorder starts the day on its first frame instead of the
country tour; use `--seconds` a little longer than `daySeconds`.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--format` | `4x5` | output frame: `16x9` (1920×1080), `4x5` (1080×1350), `9x16` (1080×1920) |
| `--viewport` | video size / scale | page layout size in CSS px; letterboxed into the frame |
| `--scale` | `2` | device pixels per CSS pixel |
| `--seconds` | `20` | video length |
| `--fps` | `30` | frame rate |
| `--poster-at` | `2` | second at which the poster PNG is taken |
| `--poster-only` | off | save just the poster PNG |
| `--name` | `power-grid` | file name prefix in `recordings/` |
| `--url` | `http://localhost:5173/` | dev server address |

The MP4 and a poster PNG go to `recordings/` (git-ignored). Chrome is used headless
(Edge works too; set `CHROME_PATH` otherwise). No ffmpeg is needed.

## Content rules

- Every number on screen comes from a named source (docs/DATA_SOURCES.md), passed
  through or computed in a build script and labelled as such. Nothing is estimated.
- Recordings of the app show the page as it is; nothing is hidden or restyled unless
  asked.
- Clock times are the market's own time (CET/CEST) of the data on screen.
- Post captions: data-led, no tech stack, real numbers only.

## How it works

- `frontend/scripts/record-video.mjs` starts headless Chrome at the viewport size
  with `deviceScaleFactor = scale` and installs a **virtual clock** before any page
  script runs (`performance.now`, `Date.now` and `requestAnimationFrame` all read
  it). Once the page sets `window.__captureReady`, it calls `window.__captureGo()`
  (starts the tour or the day), then steps the clock by exactly 1/fps per frame and
  takes a screenshot, so motion is even however slowly the GPU renders. Anything
  animated on the page must run on `requestAnimationFrame`/`performance.now`, not
  CSS animations.
- Frames are encoded to H.264 inside Chrome with WebCodecs and written by a small
  built-in MP4 muxer, so no external tools are needed.

## Troubleshooting

- **"page never became ready"**: a data file did not load; open the same URL in the
  browser and check the console.
- **Do not edit frontend files while a recording runs**: a Vite hot reload breaks it.
- **Blank map**: headless Chrome could not create a WebGL context; the recorder
  passes `--enable-unsafe-swiftshader` as a software fallback (slower).
