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
| 1 | [01-gas-flows.md](01-gas-flows.md) Europe's gas flows (ENTSOG) | no |
| 2 | [02-us-grid.md](02-us-grid.md) US grid pack (EIA-860M, queue, turbines, lines) | no |
| 3 | [03-entsoe-capacity.md](03-entsoe-capacity.md) cross-border capacity, forecasts, installed capacity | `ENTSOE_API_KEY` |

A session that finds a source closed, changed or behind a login stops, writes what it
found in the PR description, and does not substitute an estimate.
