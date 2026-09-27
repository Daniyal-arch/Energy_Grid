# Germany InfraAtlas - Build Plan

This document is the product and architecture reference for the pivot from a narrow
energy construction monitor to a broader German infrastructure intelligence system.

## Product thesis

Germany's infrastructure risks are connected. Electricity prices affect industry;
gas and raw-material dependencies affect transition delivery; ports, rail, pipelines,
and transmission corridors create both resilience and chokepoints. The product should
let an analyst move from a national dependency question to the relevant corridors,
assets, observations, and primary sources without losing provenance.

Primary users are policy and geopolitical analysts, infrastructure investors,
operators, lenders, researchers, and industrial strategy teams.

## Analytical lenses

1. **Energy security** - electricity, gas, LNG, storage, hydrogen, fuels, and imports.
2. **Dependency exposure** - supplier, country, commodity, technology, and material risk.
3. **Infrastructure topology** - power, pipeline, rail, road, port, and industrial nodes.
4. **Economic resilience** - prices, trade, industrial demand, logistics, and regional exposure.
5. **Transition execution** - renewable, grid, storage, hydrogen, and charging build-out.
6. **Geopolitical events** - sanctions, conflicts, route disruption, policy shifts, and shocks.

Each lens should answer four things: what changed, where it matters, what Germany
depends on, and which primary records support the conclusion.

## Product surfaces

- **Map:** shared geospatial topology and cross-layer corridor analysis.
- **Assets:** searchable infrastructure inventory and lifecycle evidence.
- **Strategy:** analytical lenses, source coverage, and later dependency dashboards.
- **Analyst:** retrieval-only question answering over stored observations and curated sources.

## Architecture

```text
/backend      FastAPI API, retrieval agent, source catalog
/ingestion    Pluggable source adapters and normalization jobs
/frontend     React/Vite map, asset table, strategy workspace, analyst
/supabase     Postgres/PostGIS observations, assets, evidence, provenance
/docs         Source inventory and architecture decisions
/scripts      One-off source probes and dataset acquisition helpers
```

The current `sites`, `detections`, `evidence`, `deadlines`, `timeseries`,
`grid_snapshot`, and `grid_exchange` tables remain useful. In the next schema phase,
broader records should converge on these concepts:

- `infrastructure_assets`: typed nodes and corridors with geometry and ownership.
- `observations`: time-indexed values with metric, unit, geography, and source.
- `dependencies`: Germany/sector/commodity/country exposure edges.
- `events`: geopolitical, regulatory, outage, and project milestone records.
- `source_records`: immutable provenance and retrieval metadata.
- `relationships`: asset-to-corridor, asset-to-sector, and dependency graph edges.

Do not rename or delete the existing asset tables until compatibility views and
migrations are ready. The old monitoring pipeline becomes one producer of observations.

## Data roadmap

### Connected now

- MaStR energy assets and registry status.
- Energy-Charts generation, price, and cross-border electricity signals.
- Netzausbau transmission corridors and OpenStreetMap infrastructure geometry.
- Sentinel lifecycle evidence, EEG deadlines, and existing generation history.

### Next adapters

1. Bundesnetzagentur gas status: flows, storage, consumption, and prices.
2. Hydrogen core network: approved pipelines, conversion, operators, and timing.
3. Destatis/GENESIS trade: partner-country and commodity dependencies.
4. DB InfraGO and GISCO: rail, ports, and multimodal corridors.
5. Eurostat/DERA/UBA: energy dependency, material flows, and raw-material risk.
6. ENTSO-E: outages, load, balancing, and transmission confirmation.

The complete researched inventory is in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)
and is also exposed by `GET /strategy/context`.

## Delivery phases

### Phase A - Product pivot (current)

- [x] Reframe construction monitoring as an asset lifecycle signal.
- [x] Define the six strategic lenses.
- [x] Add a cited strategic source catalog to the backend and analyst.
- [x] Add a Strategy view alongside Map and Assets.
- [x] Rename user-facing product language to Germany InfraAtlas.
- [ ] Add tests for strategic context filtering and API shape.

### Phase B - Common observation model

- [ ] Add source registry and ingestion-run tables.
- [ ] Add generic observation, event, dependency, and relationship tables.
- [ ] Preserve existing endpoints through compatibility views.
- [ ] Add freshness, geography, unit, and provenance validation.

### Phase C - Dependency intelligence

- [ ] Ingest gas, hydrogen, foreign-trade, rail, port, and raw-material datasets.
- [ ] Build country/commodity/sector dependency matrices.
- [ ] Add corridor and chokepoint overlays to the map.
- [ ] Add event timelines and scenario comparison without unsupported prediction.

### Phase D - Operational product

- [ ] Saved investigations and watchlists.
- [ ] Scheduled source refresh with failure/freshness reporting.
- [ ] Briefing and evidence export.
- [ ] Authentication, deployment, and role-aware data access.

## Non-negotiables

- Every quantitative claim traces to a stored source record.
- Catalog entries describe coverage; they are never presented as current observations.
- Derived metrics are computed in ingestion code, versioned, and stored before narration.
- Source adapters remain isolated and testable.
- The interface separates observed fact, derived indicator, and analyst interpretation.
