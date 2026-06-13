# Data sources

Every source is an adapter in `ingestion/ingestion/sources/` implementing `BaseSource` and registered via `@register`. Status values: `planned` → `probe` → `implemented` → `tested` → `live`.

| Phase | Source | Adapter name | Access | Credentials | Cadence | Status | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Google Earth Engine — Sentinel-2 L2A + Sentinel-1 GRD | `gee` | Python API (`earthengine-api`), service account | GEE service account JSON | weekly (backfill since 2021) | **tested** (validated end-to-end, real NDVI/BSI/VH stored) | NDVI, BSI (S2, SCL cloud mask), VH backscatter (S1) reduced server-side per site polygon. Store only reduced values + scene IDs. Chips exported on detection. |
| 1 | Marktstammdatenregister | `mastr` | **open-mastr Zenodo snapshot** (zip in `data/`; official bulk server throttled to ~6 KB/s) | none | monthly | **implemented + tested** (5,402 sites loaded) | All generation tech ≥5 MW nationwide. Solar: ground-mounted (`Lage=='Freifläche'`); wind: turbines clustered into farms; others: ground-based facilities. AOI = capacity-based buffer (OSM `landuse=solar` refinement is Phase 2). Verified schema in `scripts/probe_mastr_*.py`. |
| 1 | DWD weather via Bright Sky | `brightsky` | free JSON API | none | daily | implemented + tested (mocked) | Daily rain_mm / snow / temp per site centroid → `weather`. Used for false-alarm masking. |
| 2 | EEG auction deadlines | `eeg` | Derived from MaStR `Zuschlagsnummer` (no scrape) | none | monthly | **implemented + tested** (1,074 deadlines) | Award number encodes auction series+year+round → Gebotstermin + 24-month realization (§55 EEG) = legal completion deadline; also planned-commissioning dates. Month-precision estimates; agent uses them for "behind schedule" answers. Exact Gebotstermine can replace the cadence table later. |
| 2 | ENTSO-E Transparency | `entsoe` | REST API | ENTSOE_API_KEY (free registration) | daily | planned | Per-unit generation only ≥100 MW; regional aggregates otherwise → `power_output`. Production start = construction complete (cross-check). |
| 2 | SMARD | `smard` | free JSON API | none | daily | planned | German market data, regional generation. |
| 2 | OpenStreetMap | `osm` | Overpass API / Geofabrik | none | monthly | planned | Solar polygons (AOI refinement), roads, substations for site context. |
| 3 | ESA WorldCover / Copernicus DEM | `worldcover_dem` | via GEE | GEE service account | one-time per site | planned | Prior land cover + terrain enrichment. |
| 3 | State orthophotos (BW/BY WMS) | `orthophoto_wms` | WMS GetMap | none | on demand | planned | High-res validation chips, no storage of raw data. |
| 3 | Netztransparenz | `netztransparenz` | downloads | TBD | TBD | stub only | |
| 3 | Permits (UVP portal) | `uvp` | scraping | none | TBD | stub only | |
| 3 | netzausbau.de | `netzausbau` | downloads | none | TBD | stub only | |
| 3 | Local news | `news` | scraping/RSS | none | TBD | stub only | |

## Adapter contract

```python
@register
class MySource(BaseSource):
    meta = SourceMeta(
        name="mysource",
        description="...",
        cadence="daily",
        requires_credentials=("MY_API_KEY",),  # () if none
        phase=1,
    )

    def fetch(self, ctx: RunContext) -> Iterable[RawRecord]: ...
    def transform(self, raw: Iterable[RawRecord]) -> Iterable[Loadable]: ...
    def load(self, records: Iterable[Loadable], db: Client) -> LoadStats: ...
```

Run any adapter with `uv run python -m ingestion.run --source <name> [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--site-id UUID] [--dry-run]`.
