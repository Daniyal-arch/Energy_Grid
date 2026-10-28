---
title: Rules in short
tags: [rules]
updated: 2026-10-28
paths: [CLAUDE.md]
---

# Rules in short

CLAUDE.md is the full text; this is the checklist.

- Every number shown is sourced: passthrough or computed in a script, documented in
  `docs/DATA_SOURCES.md`, labelled in the UI with how it was computed. Never estimate or invent.
- Probe before implementing (`scripts/probe_*.py`, show the output).
- Stop and ask for credentials: say where to register and which env var; keep `.env.example`.
- Explain large downloads first; heavy downloads run in GitHub Actions.
- Type hints everywhere; `uv run ruff check . && uv run ruff format .`, `uv run pytest`,
  `cd frontend && npm run build` before a commit or a pull request.
- Small commits; no AI attribution in commits or PRs; never commit videos, images or secrets.
- Never put a link to a Claude Code session (claude.ai/code) anywhere on GitHub (PRs, commits,
  comments, files); the owner's decision of 2026-10-28.
- Cloud sessions work on their own branch and open a pull request; the owner merges. Never
  commit to or force-push `eu-data` or `eu-days`.
- Raw licensed GEM files only in the private R2 bucket; never republish them.
- Calm, reference-clean maps: the grid is the hero; no blur or blinking; keys compact; one
  Layers panel and one context panel.
- No over-engineering: static site, scripts, workflows; a backend only for the agent and its service.
- Chat replies in the caveman style (`.claude/skills/caveman`); code, docs, commits, PRs and the
  vault in normal English.
