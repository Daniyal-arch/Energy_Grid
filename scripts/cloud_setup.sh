#!/bin/bash
# Dependencies for Claude Code cloud sessions (.claude/settings.json runs this at session
# start). Does nothing on a laptop: only cloud sessions set CLAUDE_CODE_REMOTE=true.
if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then
  exit 0
fi
cd "$CLAUDE_PROJECT_DIR" || exit 0
uv sync --quiet || echo "uv sync failed"
(cd frontend && npm ci --no-audit --no-fund --loglevel=error) || echo "npm ci failed"
exit 0
