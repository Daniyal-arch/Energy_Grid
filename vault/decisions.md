---
title: Decisions
tags: [decisions]
updated: 2026-10-27
---

# Decisions

- **2026-10-03 Europe-first static map.** The earlier Germany atlas (backend, ingestion, agent)
  is archived in the git tag `germany-atlas-final`; not reintroduced.
- **2026-10-05 ENTSO-E for every live European figure** (`scripts/entsoe.py`). Energy-Charts has
  answered 503 since 2026-09-24; nothing depends on it.
- **2026-10-06 The data branches belong to workflows.** `eu-data` (live snapshot) and `eu-days`
  (day archive) are written only by Actions.
- **2026-10-18 No Claude on Bedrock.** AWS credits do not pay for Claude (Marketplace) and the
  quotas were 0. Claude runs through the Anthropic API (startup credits or pay-as-you-go). AWS
  credits can still pay for compute and for non-Claude Bedrock models.
- **2026-10-22/23 The owner's map design** (`docs/VISUALIZATION.md`): one style menu for every
  dataset at every scale; up to six maps of one place; nothing switches by itself; colours
  relative to what is in view. See [[styles-and-maps-view]].
- **2026-10-27 Backend on AWS Lambda, model-agnostic, LangGraph.** The backend service and the
  agent run on AWS Lambda (container image, streamed responses), compute paid by AWS credits;
  the model is configuration (Anthropic by default; OpenAI, Google, Bedrock non-Claude, local
  models possible). Tracing with OpenTelemetry and Langfuse. Brief 25; replaces the Cloudflare
  Containers plan of `docs/AGENT.md` (2026-10-18). See [[agent-backend]].
