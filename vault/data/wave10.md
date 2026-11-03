---
title: Wave 10
tags: [data, wave10, coverage]
updated: 2026-11-03
paths: [scripts/probe_wave10.py, scripts/wave10_manual.yaml, scripts/wave10_sources.yaml, scripts/wave10_families.yaml, data/wave10_gather.json, data/wave10_built/, frontend/src/app/waves.ts, docs/tasks/29-wave10.md]
---

# Wave 10 (brief 29)

Hundreds of country, world and GB district series, gathered first, then built with the
[[wave9]] machinery run as `WAVE=10`.

- **Gathering** `scripts/probe_wave10.py eurostat|wdi|registry` → `data/wave10_gather.json`:
  323 Eurostat tables (energy, environmental accounts, SDG, vehicles by fuel, rail, circular
  economy; codes earlier waves name are skipped), one named series per table chosen from the
  newest period (a total if published, else the code covering most countries); 225 WDI
  indicators of topics 5, 6, 9, 19 (each licence read from series metadata: all CC BY 4.0).
- **Registry** `scripts/wave10_sources.yaml` is generated (edit `wave10_manual.yaml` or the
  gathering): 571 sources, all built (2026-11-03); 477 colourings (Eurostat ≥ 15 countries,
  WDI ≥ 30). 22 tables over Eurostat's 5 million row cap come from the TSV form (313 M rows).
- **GB districts**: DESNZ sub-national consumption, renewables, emissions; DfT EV charging;
  Census 2021 via Nomis (TYPE424 = April 2023 districts; TS006 only TYPE154). Scope `gb_lad24`
  on `eu/gb_lad24.json` (ONS Dec 2024 BUC, `wave9.py gb-lad`).
- **Loader additions**: kind `wdi` (aggregates flagged from the WB country list, filter
  `aggregate: false`); `sheets` regex stacks workbook sheets with a `sheet` column, header
  names normalised per sheet; Eurostat's queued SOAP answer is retried every 30 s.
- **Generic waves**: ids `w<N>_<id>` and `w<N>c_<id>` (`app/waves.ts`: `waveKey`, `deckId`,
  `isWaveColour`); duck.py serves every `eu/w<N>/` file as `app.w<N>_<id>`; levels.yaml keeps
  one generated block per wave; the workflow reads `[w<N>: ...]`.
- **Groups**: Energy statistics, World indicators (new), Prices, Emissions, Mobility, Water &
  telecom, People & places (Census), Industry & demand (circular economy).

See [[coverage-and-gaps]], [[lake]], [[agent-tools]], [[state-and-datasets]].
