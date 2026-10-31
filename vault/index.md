---
title: InfraAtlas vault index
tags: [index]
updated: 2026-10-31
---

# InfraAtlas vault

Read this first, then only the notes your task needs (`.claude/skills/atlas-vault/SKILL.md`).

## Project
- [[architecture]]: the parts (static site, data scripts and workflows, lake, planned backend) and how they connect.
- [[rules]]: the hard rules and working rules in short (CLAUDE.md is the full text).
- [[decisions]]: dated decisions by the owner and what they rule out.
- [[gotchas]]: what breaks and how to avoid it.
- [[log]]: what each session changed.

## Frontend (`frontend/src`)
- [[state-and-datasets]]: the store, URL state, datasets.json, dashboards, places and coverage.
- [[map-rendering]]: the render loop, every deck.gl layer, MapLibre tiles, area clipping.
- [[styles-and-maps-view]]: the style menu (points, bubbles, hexagons, 3D, rasters), the Maps view.
- [[panels-and-cards]]: Layers panel, context panel, Dashboard tab, area cards.

## Data
- [[pipeline-and-workflows]]: scripts, GitHub Actions, the data branches, R2.
- [[lake]]: the Parquet lake on R2 and its catalogue.
- [[wave9]]: the wave 9 registry, build, render and customer tasks (brief 28).
- [[coverage-and-gaps]]: what each dataset covers, known gaps, keys still missing.

## Backend
- [[agent-backend]]: the agent and the backend service (brief 25; AWS Lambda, LangGraph, any model).
- [[backend-service]]: FastAPI app, routes, SSE, DuckDB lake and SQL guard, caps, MCP server.
- [[agent-tools]]: tools, catalogue, site figures, MapSpec, skills.
- [[areas]]: resolve_area, the area object, in_area() in SQL, area_stats over rasters (brief 27).
- [[agent-graph]]: the LangGraph flow, prompts, grounding check.
- [[agent-models]]: model registry, providers, the fake model, evals.
- [[backend-observability]]: spans, Langfuse, run records, EMF metrics, cost.
- [[backend-deploy]]: Docker image, SAM template, workflows, Worker, owner setup.
