---
title: Backend observability
tags: [backend, ops]
updated: 2026-10-27
paths: [backend/obs/, backend/agent/runs.py, backend/agent/usage.py]
---

# Backend observability

Traces, run records and metrics for [[backend-service]] and [[agent-graph]].

- `obs/tracing.py`: OTel provider; OTLP to `OTEL_EXPORTER_OTLP_ENDPOINT`, else Langfuse's OTLP
  endpoint when its keys are set; console with `OTEL_CONSOLE`; in-memory for tests. Spans:
  `http.request`, `agent.ask`, `agent.node.*` (`gen_ai.*` usage and cost from
  `agent/usage.py`), `agent.tool`, `sql.query` (hash, rows, ms).
- `obs/langfuse.py`: LangChain `CallbackHandler(trace_context=trace id)`, session id =
  conversation id, tags model/version; grounding and eval scores.
- Run record per question: `agent/logs/<date>/<trace>.json` on R2 (local store without R2); no
  IP stored (hashed only for the rate limit). 90-day R2 lifecycle rule set by the owner.
- `obs/metrics.py`: EMF lines, namespace `InfraAtlas/Agent`, per model and dimensionless.
- `obs/cost.py`: usage x registry prices (LangChain's `input_tokens` include cached ones).
