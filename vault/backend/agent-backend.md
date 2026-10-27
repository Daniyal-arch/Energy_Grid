---
title: Agent and backend service
tags: [backend, agent]
updated: 2026-10-27
paths: [backend/, agent/, docs/AGENT.md, docs/tasks/25-agent-backend.md]
status: built (brief 25); deploy waits on the owner's AWS setup
---

# Agent and backend service

`backend/`: one FastAPI service (Python 3.12, own uv project) with three faces: the data
service (no agent), `/api/ask` (the LangGraph agent over SSE) and `/mcp` (the same read-only
tools for other agents). Runs on AWS Lambda from a container image. Contract: `docs/AGENT.md`
(section 11 describes what was built); how to run and deploy: `backend/README.md`.

## Parts
- [[backend-service]]: FastAPI app, settings, routes, SSE, data layer, SQL guard, caps.
- [[agent-tools]]: the tools, the catalogue, site figures, MapSpec, skills.
- [[agent-graph]]: guard, router, analyst, cartographer, grounding, finish.
- [[agent-models]]: the registry, providers, the fake model, evals.
- [[backend-observability]]: spans, Langfuse, run records, metrics.
- [[backend-deploy]]: Docker image, SAM, workflows, the Worker, what the owner sets up.

## Shared files outside backend/
- `agent/catalog/*.yaml` (meaning; see [[lake]]), `agent/skills/<name>/SKILL.md`,
  `agent/models.yaml`, `agent/mcp.yaml`, `agent/mapspec.schema.json` (generated),
  `agent/evals/questions.yaml` (generated), `frontend/src/lib/mapspec.ts` (generated).
