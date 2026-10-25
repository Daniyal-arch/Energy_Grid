# Brief 23: room to connect, one consistent map for the EU-27, the UK and the US

Cloud session brief. Read CLAUDE.md, PLAN.md, docs/DATA_SOURCES.md ("Grid capacity", "Room to
connect" sections) and data/coverage.yaml (family `connect`) first. Work on a branch, open a PR.

## Why

The Grid capacity layer joins about twenty operator files, each drawn in its own way: points in
Great Britain, Spain and Ireland, areas in the Netherlands and Sweden, regions in Italy, nothing in
eleven countries. Users read it as inconsistent. Goal: one schema, one symbology, one country-scale
variable, and every operator that publishes data in it.

## 1. One schema (build script `scripts/build_connect_harmonised.py`)

Every published record becomes one row of `frontend/public/data/eu/connect/harmonised.json`
(and the lake table `connect/harmonised`, Parquet on R2):

| field | meaning |
|---|---|
| `cc`, `operator`, `level` | ISO alpha-2 (US: `US-<ISO/RTO or utility>`), operator, `transmission` or `distribution` |
| `id`, `name` | the operator's node, substation or area id and name |
| `kind` | `node` (a point) or `area` (an outline) |
| `lon`, `lat` / `polygon` | position as published (a node without coordinates: matched to an OpenStreetMap substation by name only when the match is unique; say how many matched) |
| `kv` | voltage as published |
| `mw_load`, `mw_gen` | free capacity for new demand / new generation, MW as published (null when the operator gives none) |
| `class` | one of `available`, `limited`, `queue` (under study or a waiting list), `none`, mapped from the operator's own classes; the mapping per operator in the script and in DATA_SOURCES.md |
| `as_of`, `source`, `url`, `licence` | the operator's date, the source name, the file's URL, its licence |

Nothing is estimated: a class is the operator's own class mapped one-to-one (document every
mapping); MW only where published. Keep the per-operator files the app reads today until the
harmonised layer replaces them.

## 2. Fill the gaps (probe first: `scripts/probe_connect_<cc>.py`, output in the PR)

Countries marked not published or partial in data/coverage.yaml, and what to try:

- **DE** (partial): the four TSOs and the large DSOs publish connection capacity under §14e EnWG
  / VDE-AR-N 4110 portals (50Hertz, Amprion, TenneT, TransnetBW; Westnetz, E.DIS, Bayernwerk,
  Netze BW, Avacon). Probe each portal for a data file or an API behind the map.
- **ES** (partial): the DSOs publish "capacidad de acceso" per substation monthly (CNMC Circular
  1/2021): i-DE, e-distribución, UFD, Viesgo, plus REE's nodes already in.
- **GB** (partial): the DNO heatmaps on their open data portals (UKPN, SSEN, NGED, Northern
  Powergrid, ENWL, SPEN: generation and demand headroom per primary/BSP). ENWL, SPEN and UKPN
  need keys: stop and ask (CLAUDE.md rule 3); .env.example lists them.
- **HR, HU, SI**: the operators publish PDFs with tables: extract with `pdfplumber` (the table as
  printed, no reading of maps); one row per substation.
- **BE, SK**: files behind a Cloudflare browser check: `.github/workflows/browser-fetch.yml`
  (Chromium) as for the earlier browser files.
- **FI, GR, LV, RO, CY**: retry with the evidence pages recorded; if still unreachable, keep
  `not_published` with the page and the date checked.
- **US**: the market queues are in; add the utilities' hosting-capacity maps that publish data
  (PG&E ICA, SCE DRPEP, SDG&E, ConEd, National Grid NY/MA, Xcel, Dominion, Duke where an
  ArcGIS service answers) as `distribution` rows; transmission headroom where an ISO publishes it.

Every new source: a row in docs/DATA_SOURCES.md, the coverage registry cell updated
(`scripts/coverage.py` regenerates docs/COVERAGE.md), licence checked before publishing.

## 3. One symbology (frontend)

- The Grid capacity layer draws `harmonised.json` only: nodes as dots, areas as outlines with a
  light fill, the same four class colours everywhere (the existing NL_COLOR ramp: available,
  limited, queue, none); dot area by `mw_gen` (or `mw_load` with the "new demand" switch) where
  published, a fixed small dot where not.
- A variable in `frontend/src/lib/measures.ts`: "Free capacity for new generation (MW)" and "for
  new demand", summing `mw_gen` / `mw_load` of the nodes inside each hexagon at country scale
  (map/hexLayers.ts), so the layer joins the hexagon, bubble, column, bivariate and side-by-side
  maps like the others. Areas count at their label point.
- The Dashboard tab's "Room to connect" card: per country in the area, MW free for generation
  and demand (sums, computed), nodes by class (a donut), and the operators listed with their date.
- The Datasets panel key: the four classes, the dot size rule, and per country the operator and
  date (from coverage.json).

## Rules (from CLAUDE.md, strictly)

Every number sourced; probe before building; stop for keys; explain any download over 100 MB and
run it in Actions; ruff, pytest and `npm run build` pass; small commits per operator; no AI
attribution in commits. The PR lists every operator added, its class mapping and its licence.
