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
| 4 | [04-us-prices.md](04-us-prices.md) US day-ahead prices at one hub per market | none (`PJM_API_KEY` optional) |
| 5 | [05-epa-unit-output.md](05-epa-unit-output.md) US fossil units hour by hour (EPA CAMPD) | `EPA_API_KEY` |

A session that finds a source closed, changed or behind a login stops, writes what it
found in the PR description, and does not substitute an estimate.

Done on main since the first briefs (2026-10-11): output per plant in Europe (ENTSO-E A73 +
JRC), installed capacity from ENTSO-E A68, border capacity on the flow arrows (A61/A31),
wind and solar forecast vs actual, "A day in the US" (EIA-930), prices to 0.01 €.

Later: CO₂ per EU installation (EU ETS), LNG send-out per terminal (GIE ALSI), Climate TRACE
facility emissions, Global Solar/Wind Atlas rasters, the rest of the world HV grid from
Overture in Actions.
