# Germany InfraAtlas data sources

This catalog separates **connected observations** from **researched coverage**.
`implemented` means code or local map assets already exist in this repository;
`partial` means only part of the source is represented; `planned` is committed next
work; `candidate` is a validated source that still needs an adapter.

The machine-readable version lives in
[`backend/app/strategic_context.py`](../backend/app/strategic_context.py) and is exposed
by `GET /strategy/context`.

## Energy and system security

| Status | Source | Access and cadence | Intended use |
|---|---|---|---|
| implemented | [MaStR public data download](https://www.marktstammdatenregister.de/MaStR/Datendownload) | Daily XML bulk files | Official electricity/gas assets, units, actors, and registry status. |
| implemented | [Energy-Charts API](https://www.energy-charts.info/api.html) | Free API; hourly/quarter-hourly | Generation, prices, installed capacity, and cross-border electricity flows. |
| planned | [ENTSO-E Transparency Platform](https://www.entsoe.eu/data/transparency-platform/) | Token API; hourly/daily | Load, generation, outages, balancing, and transmission confirmation. |
| partial | [Bundesnetzagentur Netzausbau](https://www.netzausbau.de/) | Project pages, GIS/downloads; event-driven | Transmission corridors, project phase, voltage, and operator. |
| implemented | [SciGRID gas IGGIELGNC-3](https://github.com/Netizine/SciGRID_gas-IGGIELGNC-3) | GitHub release/archive | Open gas pipelines, storage, LNG terminals, and border points for map context. |
| candidate | [Bundesnetzagentur gas supply status](https://www.bundesnetzagentur.de/DE/Gasversorgung/aktuelle_gasversorgung/start.html) | Charts and CSV; daily/monthly | Gas flows, storage, consumption, prices, and domestic production. |
| candidate | [ENTSOG maps and transparency data](https://www.entsog.eu/maps) | Maps, Excel, dashboards | European pipelines, cross-border capacity, storage, and LNG context. |
| partial | [German hydrogen core network](https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/Wasserstoff/Kernnetz/start.html) | Official annexes and map files | Approved length, conversion share, target year, cost, and caveat text. Exact route geometry is not drawn yet. |
| planned | [Bundesnetzagentur EV charging register](https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/start.html) | Register downloads/API | Charging build-out and regional grid-demand pressure. |

Existing specialist layers remain useful producers: Google Earth Engine/Sentinel for
asset lifecycle signals, Bright Sky/DWD for weather masking, SMARD for generation
history, and EEG-derived deadlines for schedule risk.

## Transport and topology

| Status | Source | Access and cadence | Intended use |
|---|---|---|---|
| implemented | [DB InfraGO infrastructure data](https://data.gov.de/suche/daten/infrastrukturdaten-der-db-infrago) | CSV archive; periodic | Rail routes, operating points, level crossings, bridges, and tunnels. |
| implemented | [Eurostat GISCO transport networks](https://ec.europa.eu/eurostat/en/web/gisco/geodata/transport-networks) | GDB/SHP/GeoPackage | German ports and airports for logistics and dependency mapping. |
| implemented | [Eurostat GISCO NUTS 2024](https://gisco-services.ec.europa.eu/distribution/v2/nuts/nuts-2024-files.html) | GeoJSON | German federal-state boundaries for atlas framing. |
| implemented | [OpenStreetMap](https://www.openstreetmap.org/) | Overpass/extracts; continuous | Power, substations, solar footprints, ports, and fallback geometry. |

Future transport work should also evaluate Mobilithek road/freight feeds and official
waterway/port sources once the rail and port baseline is connected.

## Trade, economy, and dependencies

| Status | Source | Access and cadence | Intended use |
|---|---|---|---|
| candidate | [Destatis foreign trade](https://www.destatis.de/DE/Themen/Wirtschaft/Aussenhandel/_inhalt.html) | GENESIS tables; monthly/annual | Imports/exports by partner, commodity, fuel, and goods group. |
| candidate | [GENESIS-Online](https://genesis.destatis.de/datenbank/online/statistics) | API and downloads | Sea, road, inland-waterway, pipeline, port, and industrial statistics. |
| candidate | [Eurostat energy dependency](https://www.destatis.de/Europa/DE/Thema/Umwelt-Energie/Energieabhaengigkeit.html) | Eurostat database; annual | Net import dependency by country and energy product. |
| candidate | [Eurostat material-flow accounts](https://ec.europa.eu/eurostat/en/web/environment/information-data/material-flows-resource-productivity) | Database/bulk; annual | Extraction, imports, exports, and material consumption. |
| candidate | [Eurostat FIGARO](https://ec.europa.eu/eurostat/en/web/esa-supply-use-input-tables/database) | CSV/Excel; annual | Imported value added and cross-country industry exposure. |
| candidate | [UBA raw-material footprint](https://www.umweltbundesamt.de/en/indicator-raw-material-footprint) | Excel/PDF; annual | Raw-material equivalents embedded in consumption and investment. |
| candidate | [DERA raw-material list](https://www.bgr.bund.de/DE/Gemeinsames/Nachrichten/Aktuelles/2023/2023-07-26_dera_veroeffentlicht_rohstoffliste_2023.html) | Report/tables; biennial | Supply concentration and country risk for critical materials. |
| implemented | [European Industrial Emissions Portal](https://industry.eea.europa.eu/industrial-emissions/dataset) | EEA download/API; annual | Large German energy, metals, minerals, chemicals, paper, and wood sites. |

## Browser infrastructure layers

The first broader-scope frontend dataset build is generated by
[`scripts/build_infrastructure_layers.py`](../scripts/build_infrastructure_layers.py).
Raw archives remain in gitignored `data/source_downloads`; normalized frontend assets
are written to `frontend/public/data`.

Current generated layers:

| File | Records | Frontend use |
|---|---:|---|
| `rail_network.geojson` | 1,765 routes | DB rail routes as a logistics/dependency layer. |
| `rail_structures.geojson` | 1,810 structures | DB rail bridges and tunnels as a detail overlay. |
| `gas_network.geojson` | 1,876 segments | Gas pipeline model with animated flow trails. |
| `state_boundaries.geojson` | 16 boundaries | German federal-state atlas frame. |
| `infrastructure_nodes.geojson` | 33,014 points | Rail nodes/crossings, ports, airports, gas facilities, and strategic industrial sites. |
| `energy_sites.json` | 51,368 sites | Capacity-filtered, coordinate-backed MaStR electricity units for offline energy map rendering. |
| `infrastructure_manifest.json` | source metadata | Source names, dates, caveats, counts, and hydrogen network context. |

Rebuild with:

```sh
.venv\Scripts\python.exe scripts\build_infrastructure_layers.py --fetch-industry
```

## Recommended ingestion order

1. Gas supply status and hydrogen core network, because they extend the existing
   energy model with Germany's most important non-electric dependencies.
2. Destatis foreign trade and DERA risk data, producing country-commodity exposure
   records rather than isolated charts.
3. DB InfraGO and GISCO ports, joining dependency records to physical corridors.
4. ENTSO-E outages and load, enriching the live electricity layer.
5. FIGARO input-output tables, connecting imported inputs to exposed industries.

## Adapter contract

Every ingestible source belongs in `ingestion/ingestion/sources/`, implements
`BaseSource`, and registers with `@register`. Raw payloads should be retained or
fingerprinted, transformed values must carry source/version timestamps, and derived
metrics must be stored before the analyst narrates them.

```python
@register
class MySource(BaseSource):
    meta = SourceMeta(
        name="mysource",
        description="...",
        cadence="daily",
        requires_credentials=(),
        phase=2,
    )

    def fetch(self, ctx: RunContext) -> Iterable[RawRecord]: ...
    def transform(self, raw: Iterable[RawRecord]) -> Iterable[Loadable]: ...
    def load(self, records: Iterable[Loadable], db: Client) -> LoadStats: ...
```

Run adapters with:

```sh
uv run python -m ingestion.run --source <name> --since YYYY-MM-DD --dry-run
```
