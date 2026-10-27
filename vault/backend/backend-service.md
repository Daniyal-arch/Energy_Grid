---
title: Backend service
tags: [backend]
updated: 2026-10-27
paths: [backend/app/, backend/data/, backend/agent/limits.py, backend/mcp_server/]
---

# Backend service

The FastAPI app of [[agent-backend]]. Entry: `backend/app/main.py` (`uvicorn app.main:app`).

## Where
- `app/settings.py`: pydantic-settings; env first, then SSM `/infraatlas/*` in Lambda (only
  names in `SSM_NAMES`). List settings take JSON or comma-separated values.
- `app/main.py`: middleware (request id, W3C trace context, proxy secret, body size), CORS,
  routers, the MCP app mounted last at `/` (it answers `/mcp`, 404 elsewhere).
- `app/routes/`: `health`, `catalog`, `places`, `site`, `maps`, `ask`, `admin`.
- `app/sse.py`: graph stream -> SSE events, heartbeat every 15 s.
- `data/duck.py`: the DuckDB connection (`get_lake`), app tables from the map files, lockdown,
  `run()` with timeout (cursor interrupt). `data/guard.py`: the sqlglot guard.
  `data/gazetteer.py`: places and point-in-outline. `data/r2.py`: R2 or local store.
- `agent/limits.py`: per-IP token bucket and daily spend (DynamoDB or memory).
- `mcp_server/server.py`: FastMCP (stateless streamable HTTP), bearer keys; `client.py`:
  external MCP servers from `agent/mcp.yaml`.

> [!warning] DuckDB 2.0 lockdown
> With `enable_external_access=false`, HTTPS needs the CA bundle in `allowed_paths` and
> `ca_cert_file`, and `allow_persistent_secrets=false` (else it reads `~/.duckdb`). Cursors
> start in the default catalog: `Lake.cursor()` runs `USE lake` first.

> [!warning] MCP session manager runs once
> The MCP lifespan builds a new session manager each start (`mcp_server/server.py`); tests start
> the app twice.
