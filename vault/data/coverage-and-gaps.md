---
title: Coverage and gaps
tags: [data, coverage]
updated: 2026-10-27
paths: [data/coverage.yaml, docs/COVERAGE.md, frontend/public/data/eu/coverage.json, docs/tasks/]
---

# Coverage and gaps

What each dataset family covers per country (EU-27, UK, US) is in `data/coverage.yaml`
(rendered in `docs/COVERAGE.md`, read by the app as `coverage.json`). Open work is in the briefs
of `docs/tasks/`.

## Known gaps (2026-10-27)
- **Emitters with a position**: EU ETS 2,234 of 9,668 installations placed (Germany 78 of
  1,818); UK ETS 747 installations, none placed. Brief 24 (`docs/tasks/24-emitter-positions.md`).
  Until then the Maps view offers Climate TRACE's modelled emissions where none is placed.
- **Room to connect**: one schema since PR #13 (`connect/harmonised.json`); operators that need
  keys stay blocked (ENWL, SPEN, UKPN).
- **Keys the owner still has to provide** (`PLAN.md`): Anthropic API key for the agent, AWS
  account and deploy role for the backend (brief 25), PJM, AESO, data.go.kr, EPIAS, RTE,
  Fingrid, NREL; `EPA_API_KEY` reached Actions empty on 2026-10-18.
- **Energy-Charts** answers 503 since 2026-09-24 (GB and UA keep its older figures).
- **NYISO** nodal prices: bot check on automated downloads.
