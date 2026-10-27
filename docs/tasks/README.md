# Task briefs for cloud sessions

Each file here is one self-contained piece of work for a Claude Code cloud session
(claude.ai/code, repository `Daniyal-arch/Energy_Grid`, environment `infraatlas` with
**Full** network access). Start a session with:

> Do the task in docs/tasks/<file>.md. Follow CLAUDE.md. Work on a new branch and open a
> pull request when the done-check passes.

Every brief has the same parts: goal, sources (probe first), files, map, panels,
refresh, done-check, out of scope. Read CLAUDE.md first: its hard rules and working
rules apply to every task. Start from the vault (`vault/index.md`, skill
`.claude/skills/atlas-vault`) instead of reading the repository, chat in the caveman style
(`.claude/skills/caveman`), and update the vault before the pull request.

| # | Brief | Needs a key in the environment |
|---|---|---|
| 1 (done) | [01-gas-flows.md](01-gas-flows.md) Europe's gas flows (ENTSOG) | no |
| 2 (done) | [02-us-grid.md](02-us-grid.md) US grid pack (EIA-860M, queue, turbines, lines) | no |
| 3 (done on main) | [03-entsoe-capacity.md](03-entsoe-capacity.md) cross-border capacity, forecasts, installed capacity | `ENTSOE_API_KEY` |
| 4 (done) | [04-us-prices.md](04-us-prices.md) US day-ahead prices at one hub per market | none (`PJM_API_KEY` optional) |
| 5 (done) | [05-epa-unit-output.md](05-epa-unit-output.md) US fossil units hour by hour (EPA CAMPD) | `EPA_API_KEY` |
| 6 (done on main) | [06-climate-trace.md](06-climate-trace.md) emissions per facility worldwide (Climate TRACE) | no |
| 7 (done on main) | [07-world-hv-grid.md](07-world-hv-grid.md) the rest of the world's high-voltage grid (Overture, Actions) | no (Cloudflare stays in repo secrets) |
| 8 (done on main) | [08-eu-ets-alsi.md](08-eu-ets-alsi.md) EU CO₂ per installation, LNG send-out per terminal | `AGSI_API_KEY` (network secret, header `x-key`) |
| 9 (done on main) | [09-connect-here.md](09-connect-here.md) grid capacity and queues: GB TEC, NL capacity map, Spain nodes | no |
| 10 (done on main; PJM waits for its key) | [10-us-nodal-prices.md](10-us-nodal-prices.md) US prices at every node, markets' live queues (gridstatus) | ERCOT, PJM, ISO-NE optional |
| 11 (done on main) | [11-germany-mastr.md](11-germany-mastr.md) every generating unit in Germany (MaStR) | no |
| 12 (done on main) | [12-outages-water.md](12-outages-water.md) US outages (EAGLE-I), water stress (Aqueduct) | no |
| 13 (done on main) | [13-retail-prices.md](13-retail-prices.md) retail electricity and gas prices (Eurostat, EIA-861) | no |
| 14 (done on main) | [14-lake-entsoe.md](14-lake-entsoe.md) ENTSO-E history 2015– in the lake (Parquet on R2) | `ENTSOE_API_KEY` (repo secret; runs in Actions) |
| 15 (done on main) | [15-lake-integrated.md](15-lake-integrated.md) the lake for the datasets already on the map, catalogue, topic views, PUDL timings | no (Cloudflare stays in repo secrets) |
| 16 (pull request) | [16-wrap-up.md](16-wrap-up.md) imbalance prices (ENTSO-E A85), US EV fast chargers (NREL AFDC), GB carbon intensity, Denmark every 5 min, solar and wind resource atlases | `ENTSOE_API_KEY`; NREL needs `NREL_API_KEY` (part B waits for it: `EPA_API_KEY` reached Actions empty) |
| 17 | [17-datasets-wave5.md](17-datasets-wave5.md) 22 datasets: shapes and names, US plant performance and emitters, German redispatch, TYNDP and line outages, Global Renewables Watch, country profiles, JEPX/CENACE/Grid-India, population and night lights | `ENTSOE_API_KEY`, `EIA_API_KEY`, `EPA_API_KEY`; some may need sign-ups (listed in the PR) |
| 21 (pull request) | [21-datasets-wave6.md](21-datasets-wave6.md) 24 datasets: room to connect in six more countries, substations worldwide, grid operators and utility territories, protected areas, flood hazard, roads and rail, hydrogen, auctions, costs, gas projects, GHG inventories, OE-417, FERC 714, France/Spain regional, New Zealand and South Africa live | `EIA_API_KEY`; some may need sign-ups (listed in the PR) |
| 22 | [22-coverage-wave7.md](22-coverage-wave7.md) the same datasets for EU-27, UK and US: coverage registry, room to connect, every unit, live mix and CO₂, redispatch, GB prices, retail, emitters, plants offline, EV charging, US gas, reliability | `ENTSOE_API_KEY`, `EIA_API_KEY`; keyed sources listed as blocked |
| 23 | [23-grid-capacity-harmonised.md](23-grid-capacity-harmonised.md) room to connect in one schema and one symbology for EU-27, UK and US; probe and add every operator that publishes data; free capacity per country | `ENWL_API_KEY`, `SPEN_API_KEY`, `UKPN_API_KEY` (listed as blocked) |
| 24 | [24-emitter-positions.md](24-emitter-positions.md) EU ETS and UK ETS installations placed on the map from published positions (EUTL, EEA register by permit, NAEI and UK permit registers) | no |
| 25 | [25-agent-backend.md](25-agent-backend.md) the backend: data service and agent on AWS Lambda (FastAPI, LangGraph, any model, skills, MCP, OpenTelemetry + Langfuse, evals, SAM deploy) | `ANTHROPIC_API_KEY`, AWS deploy role, R2 tokens, Langfuse (builds with fakes until then) |
| 26 | [26-room-to-connect-everywhere.md](26-room-to-connect-everywhere.md) room to connect for every EU-27 country, the EU's neighbours, the UK and the US: research every operator (EU 2024/1711 and 2024/1747 obligations, FERC Order 2023 heatmaps, US hosting capacity maps), build what is published, document the rest | `ENWL_API_KEY`, `SPEN_API_KEY`, `UKPN_API_KEY` (blocked) |

Several sessions run at once and touch the same files (store, layers, panels, docs,
workflows): before opening a pull request, merge `origin/main` into the branch and resolve
conflicts, keeping both sides.

Full detail goes to the lake (docs/DATA_LAKE.md) through `scripts/lake.py`; sessions write the
code, GitHub Actions downloads, builds and uploads.

Keys a session does not hold (ERCOT, ISO-NE, Cloudflare, GEM) live as GitHub repo secrets:
the session writes the workflow step and the script skips a market or upload whose key is
missing. A new workflow can run before the merge with a `push:` trigger limited to the
session's branch that commits its small outputs back to that branch (the session pulls them);
remove that trigger before opening the PR.

A session that finds a source closed, changed or behind a login stops, writes what it
found in the PR description, and does not substitute an estimate.

Done on main since the first briefs (2026-10-11): output per plant in Europe (ENTSO-E A73 +
JRC), installed capacity from ENTSO-E A68, border capacity on the flow arrows (A61/A31),
wind and solar forecast vs actual, "A day in the US" (EIA-930), prices to 0.01 €.

Later: CO₂ per EU installation (EU ETS), LNG send-out per terminal (GIE ALSI), Climate TRACE
facility emissions, the rest of the world HV grid from Overture in Actions.

Done in task 16 (2026-10-18): imbalance prices per zone (card and lake history), GB carbon
intensity, Denmark every 5 minutes, the solar and wind resource atlases (layers, Check a site,
COGs in the lake). Waiting: US EV fast chargers (`NREL_API_KEY`).
