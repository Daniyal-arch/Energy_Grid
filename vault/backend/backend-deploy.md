---
title: Backend deploy
tags: [backend, ci]
updated: 2026-10-27
paths: [backend/deploy/, .github/workflows/backend.yml, .github/workflows/agent-evals.yml]
---

# Backend deploy

How [[agent-backend]] reaches AWS Lambda.

- `backend/deploy/Dockerfile`: build from the repo root; LWA 0.9.1 in `/opt/extensions`, uv
  sync from the lock, DuckDB extensions in `/opt/duckdb_ext`, a few map files and `agent/`.
  Optional build secret `ca` for TLS-inspecting proxies (the cloud session needs it).
- `template.yaml` (SAM, cfn-lint clean): function (arm64, 3008 MB, 2048 MB /tmp, 300 s, reserved
  10), Function URL `RESPONSE_STREAM`, DynamoDB `Counters` (pk, ttl), log group 30 days,
  dashboard, alarms (function errors, agent errors, daily spend, p90 latency), SNS topic.
- `iam/`: GitHub OIDC trust policy and the deploy policy (placeholders for account and region).
- `worker/`: Cloudflare Worker for same-origin `/api/*` and `/mcp` (secret header, rate-limit
  binding, streams through).
- `backend.yml`: check (ruff, format, mapspec check, pytest) and an arm64 image smoke test on
  PRs; on main OIDC -> ECR -> `sam deploy` -> smoke test -> Worker (continue-on-error until the
  Cloudflare token has Workers rights). Skips with setup steps without `AWS_DEPLOY_ROLE_ARN`.

> [!warning] Same origin
> The site is a Worker on `energy-grid.infraatlas.workers.dev`; zone routes need a custom
> domain (`SITE_DOMAIN`). Until then the app calls the Function URL with CORS.
