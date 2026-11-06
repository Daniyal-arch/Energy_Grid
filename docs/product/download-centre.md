# Download centre

Track 6.7 of brief 30. MVP: `frontend/src/ui/Downloads.tsx` (`?downloads`), its index
`frontend/public/data/downloads.json` built by `scripts/build_downloads.py`.

## Problem

Every dataset on the map is a static file, but nobody can tell which file belongs to which
layer, under which licence it may be reused, how to attribute it, or how fresh it is.

## Who it serves

Researchers, consultants and developers who want the data behind a layer, and need to know
whether they may republish it.

## What it shows

One table, one row per dataset of the Layers panel (`app/datasets.json` and the registry waves):
name, category, where it has data, its files (the URLs the app reads under `/data/...`, the
live copy on the `eu-data` / `eu-days` branch where one exists, and the public tiles), the lake
tables that hold it in full (agent only), the licence, the attribution text and the "as of"
date read from each file. A filter box narrows by name, source, licence or place, and a toggle
shows only the downloadable ones.

Only datasets whose licence allows redistribution get links: CC BY, CC0, ODbL (with the
share-alike note), the UK Open Government Licence, Licence Ouverte / Etalab, dl-de/by and
dl-de/zero, NLOD, the NESO Open Data Licence, public domain and US government works. Every
other dataset is listed as "view only: <licence>" with no link; a dataset whose licence is not
recorded is "view only: licence not recorded".

## Its data

`scripts/build_downloads.py` joins `frontend/src/app/datasets.json`, `wave9.json`,
`wave10.json`, the agent catalogue (`agent/catalog/*.yaml`: licences and lake tables) and a
short table in the script for the core datasets (files and licences as docs/DATA_SOURCES.md
states them). The "as of" date is the file's own `fetched` / `at` / `date` field.

## Its limits

- The bundled copies' dates are those of the last build; live files on `eu-data` and `eu-days`
  are newer (the row links both).
- The lake (R2 `infraatlas-raw`) is private: lake tables are listed for the agent, not offered.
- Global Energy Monitor files stay view only (the project keeps GEM's download-form files
  private), as do ENTSO-E, Open-Meteo (non-commercial) and every source without a stated licence;
  the owner decides on those.
- The licence classifier is a fixed allowlist of names; a new licence wording needs a line in it.
