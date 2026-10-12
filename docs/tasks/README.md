# Task briefs for cloud sessions

Each file here is one self-contained piece of work for a Claude Code cloud session
(claude.ai/code, repository `Daniyal-arch/Energy_Grid`, environment `infraatlas` with
**Full** network access). Start a session with:

> Do the task in docs/tasks/<file>.md. Follow CLAUDE.md. Work on a new branch and open a
> pull request when the done-check passes.

Every brief has the same parts: goal, sources (probe first), files, map, panels,
refresh, done-check, out of scope. Read CLAUDE.md first: its hard rules and working
rules apply to every task.

| # | Brief | Needs a key in the environment |
|---|---|---|
| 1 (done) | [01-gas-flows.md](01-gas-flows.md) Europe's gas flows (ENTSOG) | no |
| 2 (done) | [02-us-grid.md](02-us-grid.md) US grid pack (EIA-860M, queue, turbines, lines) | no |
| 3 (done on main) | [03-entsoe-capacity.md](03-entsoe-capacity.md) cross-border capacity, forecasts, installed capacity | `ENTSOE_API_KEY` |
| 4 (done) | [04-us-prices.md](04-us-prices.md) US day-ahead prices at one hub per market | none (`PJM_API_KEY` optional) |
| 5 (done) | [05-epa-unit-output.md](05-epa-unit-output.md) US fossil units hour by hour (EPA CAMPD) | `EPA_API_KEY` |
| 6 | [06-climate-trace.md](06-climate-trace.md) emissions per facility worldwide (Climate TRACE) | no |
| 7 | [07-world-hv-grid.md](07-world-hv-grid.md) the rest of the world's high-voltage grid (Overture, Actions) | no (Cloudflare stays in repo secrets) |
| 8 | [08-eu-ets-alsi.md](08-eu-ets-alsi.md) EU CO₂ per installation, LNG send-out per terminal | `AGSI_API_KEY` (network secret, header `x-key`) |
| 9 | [09-connect-here.md](09-connect-here.md) grid capacity and queues: GB TEC, NL capacity map, Spain nodes | no |
| 10 | [10-us-nodal-prices.md](10-us-nodal-prices.md) US prices at every node, markets' live queues (gridstatus) | ERCOT, PJM, ISO-NE optional |
| 11 | [11-germany-mastr.md](11-germany-mastr.md) every generating unit in Germany (MaStR) | no |
| 12 | [12-outages-water.md](12-outages-water.md) US outages (EAGLE-I), water stress (Aqueduct) | no |
| 13 | [13-retail-prices.md](13-retail-prices.md) retail electricity and gas prices (Eurostat, EIA-861) | no |

Several sessions run at once and touch the same files (store, layers, panels, docs,
workflows): before opening a pull request, merge `origin/main` into the branch and resolve
conflicts, keeping both sides.

A session that finds a source closed, changed or behind a login stops, writes what it
found in the PR description, and does not substitute an estimate.

Done on main since the first briefs (2026-10-11): output per plant in Europe (ENTSO-E A73 +
JRC), installed capacity from ENTSO-E A68, border capacity on the flow arrows (A61/A31),
wind and solar forecast vs actual, "A day in the US" (EIA-930), prices to 0.01 €.

Later: CO₂ per EU installation (EU ETS), LNG send-out per terminal (GIE ALSI), Climate TRACE
facility emissions, Global Solar/Wind Atlas rasters, the rest of the world HV grid from
Overture in Actions.
