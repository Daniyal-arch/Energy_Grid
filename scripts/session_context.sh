#!/bin/bash
# Context for Claude Code cloud sessions (.claude/settings.json runs this at session start; its
# output is added to the session's context). Prints nothing on a laptop, where the owner's own
# plugins do the same: only cloud sessions set CLAUDE_CODE_REMOTE=true.
if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then
  exit 0
fi
cat <<'EOF'
CAVEMAN MODE ACTIVE (level full): reply in chat in the style of .claude/skills/caveman/SKILL.md.
Code, comments, commits, docs, PR text and the vault stay in normal English.
VAULT FIRST: read vault/index.md and only the notes the task needs before reading code
(.claude/skills/atlas-vault/SKILL.md); update the vault before the commit or pull request.
EOF
exit 0
