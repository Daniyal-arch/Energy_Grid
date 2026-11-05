# Brief 30 baselines (2026-11-04)

Measured at the start of the long run (branch `claude/loving-dijkstra-5q8n1c`, base `e39b928`),
in a Linux cloud container.

## Tests
- `uv run pytest`: 162 passed.
- `cd backend && uv run pytest`: 164 passed once the DuckDB 2.0 extensions (httpfs, spatial,
  h3) are in `~/.duckdb/extensions/v2.0.0/linux_amd64/`. The backend opens DuckDB with
  `autoinstall_known_extensions = false` (lockdown), so a fresh machine without them fails 48
  tests and errors 6 with "Extension ... not found". CI installs them in its setup step.

## Frontend bundle (`npm run build`)
| Chunk | Size | gzip |
|---|---|---|
| `index-*.js` (initial) | 3,256.18 kB | 863.14 kB |
| `EuropeView-*.js` (lazy) | 102.43 kB | 31.74 kB |
| `index-*.css` | 110.25 kB | 18.14 kB |

Vite warns: a chunk over 500 kB. Target (Track 5): initial JS under 500 kB gzip.

## Frontend bundle after code-splitting (2026-11-05, Track 5.1)
| Chunk | gzip | Loaded |
|---|---|---|
| `index-*.js` (entry: map, Layers panel, store) | 207.69 kB (was 863.14 kB with everything) | at start |
| `maplibre-*.js` | 284.74 kB | at start (the map) |
| `deckgl-*.js` (deck.gl, luma.gl, math.gl, loaders.gl) | 233.14 kB | at start (the map's layers) |
| `react-*.js` | 45.49 kB | at start |
| `Panel-*.js` (context panel and its cards) | 72.24 kB | after the first frame |
| `WorldCards`, `CountryReport`, `Catalogue`, Ask, Maps view, dashboard builder | 1.7-15 kB each | when shown |

Initial JS (entry + map libraries + React): 771 kB gzip, against the 500 kB target. MapLibre
alone is 285 kB and deck.gl 233 kB; reaching 500 kB means loading deck.gl after the base map's
first frame (a change to the render loop in `map/MapCanvas.tsx`), left for a follow-up.
