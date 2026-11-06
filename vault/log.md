---
title: Log
tags: [log]
updated: 2026-11-03
---

# Log

Newest first. One entry per session or merged pull request.

- **2026-11-06** (claude/loving-dijkstra-5q8n1c, PR #19 ready): brief 30 done-check. Real-lake
  probe: names 12/12, first event 0.01 s, run_sql p50 0.46 s, resolve_area p50 5.3 s (not met;
  outlines now fetched by box, table list cached). Second dark-cell pass merged (64 cells,
  `data/dark_evidence.yaml`, pxweb kind). Coverage built 1,473 to 1,855 of the 29 places' cells.
  Open: resolve_area breakdown, deck.gl after first frame (bundle 771 kB), FEMA/ENTSO-E balancing/
  EEA AQ readers, conversation permalinks, KPX wiring (owner). Notes: areas, coverage-and-gaps.

- **2026-11-06** (claude/loving-dijkstra-5q8n1c, PR #19): Track 3 (H3 rollups, history
  snapshots, customer-gap sources, live grids: KPX ready but not wired), Track 4 (lazy agent
  import, data API), Track 5 (code-split bundle 863 to 208 kB entry, recently used, coverage
  explorer, Ask chips/resume, colour-blind palettes, as-of on layer cards), Track 6 (seven MVPs),
  neighbours in the coverage registry. Notes: product, instant-answers, freshness, wave9, index.

- **2026-11-05** (claude/loving-dijkstra-5q8n1c, PR #19, brief 30): Track 1 (area names via
  Overture aliases and named areas, loop guard, browser-fetch skips, ECR retries, 10 of 12
  failed wave 9 builds fixed, GISCO replacement behind `?shapes=open`), Track 2 (91 page-only
  sources decided, raster/census/parquet/data-fair kinds, coverage built 1,473 to 1,776 cells),
  Track 3.1 (freshness), Track 4 (instant answers, cache, SSE resume/cancel, security tests, six
  tools, MCP docs, name_norm index, warm start). Notes: areas, agent-graph, instant-answers,
  freshness, wave9, gotchas, pipeline-and-workflows, index.

- **2026-11-04** (main, local): brief 30 written (`docs/tasks/30-long-run.md`): a multi-day
  cloud run in seven tracks (harden, coverage, new data, agent speed, frontend, product MVPs,
  docs). Notes: none.

- **2026-11-04** (main, local): PR #18 (waves 9 and 10) checked: CI green, 658 new tables, 49
  layers, 494 colourings; R2 holds 38.2 GB. Gemini tested locally (`probes/probe_gemini.py`):
  free-tier flash models in the registry; tool arguments as lists (Gemini refuses tuples); the
  lake's CA bundle set globally with a certifi fallback (R2 reads failed on Windows). Notes:
  agent-models, gotchas.

- **2026-11-03** (claude/funny-euler-7vwg1s): wave 10 (brief 29) gathered and built: 571
  sources (323 Eurostat tables, 225 WDI indicators, 23 GB district tables), colourings per
  country, world country and GB district (`gb_lad24`). The wave-9 machinery runs any wave
  (`WAVE=N`, ids `w<N>_`/`w<N>c_`); new loader kinds `wdi`, `eurostat_tsv` (tables over
  Eurostat's 5 million row cap) and stacked workbook sheets. Country colourings now redraw when
  their file loads (also wave 9). Skill `energy-statistics`, eight evals. Notes: wave10, wave9,
  gotchas.

- **2026-11-03** (claude/funny-euler-7vwg1s): GB local authority districts (ONS Dec 2021 BUC,
  `gb_lad.json`) as the shapes of a new colouring scope `gb_lad`; DfT VEH0131 plug-in cars per
  district coloured (2021 Q4, 385 districts). `wave9.py render` is idempotent again (coverage
  cells merged each source once). Notes: wave9, map-rendering.

- **2026-10-31** (claude/funny-euler-7vwg1s): every positioned wave 9 source on the map (vector
  tiles for 24 large or line/polygon sources) and 16 area series as colourings (Eurostat
  countries, USGS US counties); NPG and NGED tables gained BNG positions. Notes: wave9,
  map-rendering.

- **2026-10-31** (main, local): PR #17 (brief 27) checked: the backend image job's failure was
  public.ecr.aws's anonymous pull limit (429), green on main; coverage per family reviewed.
  Brief 28 written: finish wave 8 and wave 9 in 17 categories chosen by customer needs, with
  EU, UK and US sources, dashboards and agent skills per customer task. Notes: gotchas.

- **2026-10-31** (claude/funny-euler-7vwg1s): brief 28: wave 9 registry (`scripts/wave9_sources.yaml`,
  213 sources probed, 87 built), generic builder and `wave9.yml`, render of coverage families, research doc,
  catalogue, levels and the app's layer list; Part A sources (EIA layers, EA flood zones, census
  outlines, Zensus heating, CSO small areas); eleven Tasks dashboards, eleven task skills, 33
  eval cases; wave 9 map files served as `app.w9_<id>`. Notes: wave9 (new), coverage-and-gaps,
  lake, agent-tools, state-and-datasets, map-rendering, pipeline-and-workflows, gotchas, index.

- **2026-10-29** (claude/funny-euler-7vwg1s): brief 27 built: areas (`resolve_area`, area
  object and store, `in_area()` macros with bbox pruning, `area_stats` over COGs, MapSpec
  `area`/`shapes`, drawn and screen areas from the app, area-analysis skill, level matrix,
  20 area evals, timing probe); wave 8 data (outlines at every level, GHSL/WorldCover/slope
  rasters, energy per small area for FR, GB, NL, DK, PT, SE, IE, ES-CT, US, EEA industrial,
  dams, CO2StoP, Hotmaps, fires, GEM ownership, TRI, EA Pollution Inventory), five map layers,
  15 coverage families for 29 places, `wave8.yml`. Notes: areas (new), agent-tools, lake,
  coverage-and-gaps, gotchas, decisions, pipeline-and-workflows, map-rendering,
  state-and-datasets, index.

- **2026-10-29** (main, local): brief 27 written (`docs/tasks/27-any-area-wave8.md`): the agent
  resolves any area (country to neighbourhood, drawn polygon, circle, zone, union, buffer,
  world), filters queries and clips maps to it, sums rasters inside it; data wave 8 chosen from
  a review of peer platforms and their sources; consistency rule: one coverage cell per EU-27
  country, GB and US for every family, one level ladder, UK and US equivalents named. Notes:
  coverage-and-gaps, agent-tools.

- **2026-10-29** (main, local): Ask in the app (`ui/AskTab.tsx`, `app/agent.ts`); MapSpec v2 with
  12 flat and 10 3D styles, 2-6 maps side by side (`panels`) and edits (`replaces`);
  `map/agentLayers.ts` draws them; the cartographer designs the maps and edits the ones on
  screen; the analyst no longer calls make_map; SQL previews of 200 rows. Notes: agent-tools,
  agent-graph, panels-and-cards, map-rendering.

- **2026-10-29** (main, local): backend tested locally on Groq (data routes, the agent end to end);
  Groq and Bedrock API key support, Groq models in the registry, Bedrock probe (quotas 0);
  fixes: internal instructions no longer stream as answer text, thousands with spaces ground,
  answers do not paste the MapSpec; backend CI installs DuckDB's extensions; UTF-8 file IO.
  Notes: agent-models.

- **2026-10-28** (claude/room-to-connect-everywhere): browser discovery for the Cloudflare-checked
  operators (`scripts/browser_discover.py`, browser-fetch.yml sources "discover"): only
  Transelectrica passed, and it publishes requested capacity as an image; the rest stay data
  requests. Notes: coverage-and-gaps.

- **2026-10-28** (claude/room-to-connect-everywhere): brief 26: research of every operator in
  the EU-27, the neighbours, the UK and the US (`docs/research/room-to-connect.md`, probe
  `scripts/probe_connect_h26.py`); 14 new operators in the harmonised rows
  (`scripts/build_connect_h26.py`); OSM matching per area (`osm_area`, `match_name`), `summable`
  in the operator files; the registry's neighbours (`regions: [neighbours]`). Notes:
  coverage-and-gaps, pipeline-and-workflows.

- **2026-10-28** (claude/no-session-links): no Claude Code session links on GitHub; removed from
  the bodies of PRs #1-#14; CLAUDE.md's PR rule changed. Notes: rules, decisions.

- **2026-10-27** (main): room-to-connect research handed to a cloud session: brief 26 rewritten for
  EU-27, neighbours, UK and US with every finding (probes `probe_connect_gaps.py`,
  `probe_connect_us_heatmaps.py`). Notes: coverage-and-gaps.

- **2026-10-27** (main, local): every room-to-connect record kept (3D draws unsized ones as flat
  dots; "nothing published for this side" in grey); a class share bar in the key; dark countries
  say why (registry); probe of the missing countries and brief 26; planned gas projects as a donut
  per country with the count; "Also with data here" chips removed. Notes: coverage-and-gaps.

- **2026-10-27** (main, local): Layers panel rows reduced to name and an ON/OFF switch, details on
  click; room to connect asks its question ("Where can new generation connect?"), follows the
  side switch in every style, greys the countries with no published data; 3D only for records
  with a figure. Notes: panels-and-cards, styles-and-maps-view, coverage-and-gaps.

- **2026-10-27** (main): the Maps view (up to six maps of a place, one camera) and one style menu
  for every dataset; PR #13 merged (room to connect in one schema); compact map keys, 3D at a
  fixed size on screen, empty maps say why; brief 24 (ETS positions) and brief 25 (backend);
  the vault and the project skills created. Notes: all.

- **2026-10-27** (claude/hopeful-cerf-7kcepr): brief 25 built: `backend/` (FastAPI data
  service, LangGraph agent with grounding, MCP server, DuckDB with the SQL guard, OTel/Langfuse,
  evals, Lambda image, SAM, workflows, Worker), eight agent skills, the model registry, generated
  MapSpec schema and TS types; seven catalogue YAML files fixed. Notes: agent-backend,
  backend-service, agent-tools, agent-graph, agent-models, backend-observability,
  backend-deploy, architecture, lake, gotchas, index.
