---
title: InfraAtlas vault index
tags: [index]
updated: 2026-10-27
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
- [[coverage-and-gaps]]: what each dataset covers, known gaps, keys still missing.

## Backend
- [[agent-backend]]: the agent and the backend service (brief 25; AWS Lambda, LangGraph, any model).
