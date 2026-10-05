# Europe InfraAtlas

Europe's power system as one interactive map: the high-voltage grid, power plants,
gas infrastructure, measured cross-border electricity flows, day-ahead prices and
the generation mix of each country.

- **Whole Europe:** 9,162 transmission lines (220 kV and above), 39 HVDC links,
  6,863 substations, plants of 20 MW and more, cross-border flows on 79 borders,
  countries shaded by renewable share or day-ahead price.
- **Country focus:** click a country to tilt into it. Every plant of 1 MW and more
  appears as a 3D column ("Bars") or as light beams over hexagon fields ("Beams &
  fields"), next to load, generation, prices, flows, installed capacity, hydro
  reservoirs and gas infrastructure.
- **24 hours:** `?day=2026-09-24` plays one real day every 15 minutes: market clock,
  flows, prices and renewable share changing through the day.
- **2000–2025:** `?view=transition` colours every country on the globe by Ember's
  yearly renewable share, wind + solar share, coal share or carbon intensity and plays
  25 years; click a country for its generation by source.

All figures come from public sources (ENTSO-E, Ember, GIE, powerplantmatching,
OpenStreetMap via PyPSA-Eur, SciGRID_gas, Eurostat GISCO); see
[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Run it

```sh
cd frontend && npm install && npm run dev      # http://localhost:5173
```

The app is a static site: it reads JSON files from `frontend/public/data/eu/` and
needs no server. A GitHub Action refreshes the live figures every 30 minutes.

## Rebuild the data

```sh
uv sync
uv run python scripts/fetch_eu_energy.py       # raw inputs into data/eu/ (~50 MB, gitignored)
uv run python scripts/build_eu_grid.py         # grid, plants, gas, countries
uv run python scripts/fetch_eu_snapshot.py     # current flows, prices, generation
uv run python scripts/fetch_eu_reference.py    # installed capacity, reservoirs
uv run python scripts/build_eu_day.py 2026-09-24   # one day for the time-lapse
```

## Documentation

- [Plan](PLAN.md)
- [Engineering conventions](CLAUDE.md)
- [Data sources](docs/DATA_SOURCES.md)
- [Videos](docs/VIDEO.md)

The earlier Germany atlas (backend, ingestion, AI analyst, Germany power and rail
views) is preserved in the git tag `germany-atlas-final`.
