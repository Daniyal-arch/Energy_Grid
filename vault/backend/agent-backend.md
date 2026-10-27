---
title: Agent and backend service
tags: [backend, agent]
updated: 2026-10-27
paths: [docs/AGENT.md, docs/tasks/25-agent-backend.md, agent/]
status: planned
---

# Agent and backend service

> [!info] Planned
> Not built yet. Brief 25 (`docs/tasks/25-agent-backend.md`) builds it in one cloud session.
> The session replaces this note with notes per part (service, graph, tools, models,
> observability, deploy) and links them from [[index]].

## What it will be
- `backend/`: a FastAPI service with the data endpoints the app can use without the agent
  (catalogue, places, "Check a site" figures, saved maps) and `/api/ask`, the agent, streamed as
  Server-Sent Events.
- The agent: a LangGraph graph (guard, router, analyst, cartographer, grounding, finish); tools of
  `docs/AGENT.md` §3 over the [[lake]] with DuckDB; skills in `agent/skills/` loaded on demand;
  every number checked against the turn's tool results.
- Any model: `init_chat_model("<provider>:<model>")` with the registry `agent/models.yaml`
  (Anthropic by default; see [[decisions]] 2026-10-18 and 2026-10-27).
- MCP: the same tools at `/mcp`; external MCP servers attachable from `agent/mcp.yaml`.
- Traced: OpenTelemetry spans and Langfuse traces per question; run records on R2
  `agent/logs/`; CloudWatch logs, metrics, dashboard.
- Hosted: AWS Lambda container image with the Lambda Web Adapter (streaming), Function URL,
  SAM, DynamoDB counters, SSM secrets, GitHub Actions deploy with OIDC; a Cloudflare Worker
  routes `/api/*` from the site's domain.

## Contract
`docs/AGENT.md`: what the agent answers, the tools and their limits, the semantic catalogue
(`agent/catalog/*.yaml`), the MapSpec, the SSE events, costs and caps, evals.
