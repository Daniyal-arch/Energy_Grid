# Data sources

Every file the app reads lives in `frontend/public/data/eu/` and is built by a script
in `scripts/`. Values are passthrough from the source unless a row says otherwise.

## Static layers (`scripts/fetch_eu_energy.py` → `scripts/build_eu_grid.py`)

| File | Records | Source |
|---|---:|---|
| `grid.json` | 9,162 lines >= 220 kV, 39 HVDC links, 6,863 substations | PyPSA-Eur prebuilt network from OpenStreetMap ([Zenodo 18619025](https://zenodo.org/records/18619025)), ODbL |
| `plants.json` | 7,838 operating units >= 20 MW | powerplantmatching (PyPSA). One threshold for all countries, because the German input is unit-level (MaStR); German wind is listed per turbine, so it falls under the cut at continent scale |
| `plants/<ISO>.json` | 61,872 units >= 1 MW | powerplantmatching, loaded when a country is focused (columns from 10 MW, flat dots below; "Beams & fields" sums units under 200 MW per 24 km hexagon in the browser and labels it so) |
| `gas.json` | 4,840 pipe segments, 29 LNG, 216 storages | SciGRID_gas IGGIELGN (2021, [Zenodo 4767098](https://zenodo.org/records/4767098)), CC BY 4.0; clipped to the mapped countries; capacities only where the dataset marks them as not estimated. Predates the 2022+ German LNG terminals |
| `countries.json` | 35 countries: land, coast, borders | Eurostat GISCO countries 1:20M (2024); overseas territories dropped |

```sh
uv run python scripts/fetch_eu_energy.py   # ~50 MB into data/eu/ (gitignored)
uv run python scripts/build_eu_grid.py
```

## Live figures (`scripts/fetch_eu_snapshot.py`, `scripts/fetch_eu_reference.py`)

| File | Records | Source |
|---|---:|---|
| `flows.json` | 79 borders | Energy-Charts `/cbpf` per country (ENTSO-E physical flows): latest complete 15-min value per border, plus 24 h of 15-min values for the replay |
| `stats.json` | EU + per country | Energy-Charts `/public_power` (country=eu and per country): load, generation by source group, published renewable share of generation; `/price` day-ahead price for 41 bidding zones |
| `reference.json` | per country | Energy-Charts `/installed_power` (newest year with values) and ENTSO-E A72 hydro reservoir energy (newest week, same week a year earlier) |

`.github/workflows/eu-snapshot.yml` refreshes these every 30 min onto the `eu-data`
branch; the app reads that copy from raw.githubusercontent.com and falls back to the
bundled one (newer wins). Reservoirs need the repo secret `ENTSOE_API_KEY`.

## One day for the time-lapse (`scripts/build_eu_day.py`)

| File | Records | Source |
|---|---:|---|
| `day/<YYYY-MM-DD>.json` | 96 slots (15 min) of a local day (Europe/Berlin) | Energy-Charts with start/end: `/price` per zone, `/public_power` per country (and EU, hourly), `/cbpf` per country |
| `day/index.json` | list of built days | — (`?day=latest` opens the newest) |
| `day/<date>.json` → `highlights` | ~9 key moments per day | computed by `scripts/day_highlights.py` from the same file: min/max of EU load, solar, wind, gas; lowest/highest zone price; largest border flow; highest renewable share at the solar peak. The captions only word these values |

**Rolling archive:** `.github/workflows/eu-days.yml` runs every morning
(`build_eu_day.py --recent 30`): it builds yesterday, rebuilds the two newest days
for late corrections and drops days older than 30, on the `eu-days` branch. All
missing days are fetched in one window (one request per series), so a 30-day
backfill costs about as much as one day. The app merges that archive with the days
bundled in `frontend/public/data/eu/day/` and offers them in a date picker.

The time-lapse clock shows the market's own time (CET/CEST) of the slot on screen.
The "price range, all zones" chart is the lowest and highest zone price per slot.

## Notes

- Energy-Charts answers 429 to bursts; all scripts ask one request at a time.
- ENTSO-E Transparency (A11) returns the same flows but took more than 10 minutes for
  all 164 border directions (`scripts/probe_entsoe_borders.py`).
- Energy-Charts has no load/generation data for GB, UA and XK, and no prices for IE,
  MK, BA, AL, XK, UA, MD.
