---
title: Log
tags: [log]
updated: 2026-10-29
---

# Log

Newest first. One entry per session or merged pull request.

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
