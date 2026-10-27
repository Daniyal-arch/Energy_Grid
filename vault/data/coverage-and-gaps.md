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
- **Room to connect**: one schema since PR #13 (`connect/harmonised.json`, 39 operators in 25
  countries); no operator data for AL, BA, BE, CH, LV, MD, ME, MK, NO, RO, RS, UA (drawn dark,
  labelled with the reason from the registry, `capacityGapLayers` in `map/connectHLayers.ts`;
  probe `scripts/probe_connect_gaps.py`: most answer Cloudflare checks, Sadales tīkls HTTP 451,
  Statnett and Elvia 404). Brief 26 fills what can be filled. ENWL, SPEN, UKPN wait for keys.
- **Keys the owner still has to provide** (`PLAN.md`): Anthropic API key for the agent, AWS
  account and deploy role for the backend (brief 25), PJM, AESO, data.go.kr, EPIAS, RTE,
  Fingrid, NREL; `EPA_API_KEY` reached Actions empty on 2026-10-18.
- **Energy-Charts** answers 503 since 2026-09-24 (GB and UA keep its older figures).
- **NYISO** nodal prices: bot check on automated downloads.
