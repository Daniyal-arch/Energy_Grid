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
