#!/usr/bin/env bash
# Commit the app's data files a wave-5 job wrote and push them to the branch it ran on (several
# jobs push in turn: rebase and retry).
set -u
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add frontend/public/data agent/catalog 2>/dev/null || git add frontend/public/data
git diff --cached --quiet && { echo "nothing to commit"; exit 0; }
git commit -q -m "$1"
for i in 1 2 3 4 5; do
  git pull -q --rebase origin "$GITHUB_REF_NAME" && git push -q origin "HEAD:$GITHUB_REF_NAME" && exit 0
  sleep $((i * 5))
done
echo "push failed"; exit 1
