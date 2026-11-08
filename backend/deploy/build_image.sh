#!/usr/bin/env bash
# Build the backend image, retrying when a registry answers 429 (public.ecr.aws limits
# anonymous pulls: "Data limit exceeded"). Usage: build_image.sh <tag> [platform] [extra args...]
# The base images are pulled first, each with up to 5 tries and a growing wait; the build then
# reuses them from the local cache.
set -euo pipefail
TAG=$1; PLATFORM=${2:-}; shift $(( $# >= 2 ? 2 : 1 ))
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PF=${PLATFORM:+--platform $PLATFORM}
for img in $(grep -oE '^(ARG PYTHON_IMAGE=|FROM )[^ ]+' "$ROOT/backend/deploy/Dockerfile" | sed -E 's/^(ARG PYTHON_IMAGE=|FROM )//' | grep -v '^\$' | sort -u); do
  for i in 1 2 3 4 5; do
    docker pull $PF "$img" && break
    [ "$i" = 5 ] && { echo "pull of $img failed 5 times" >&2; exit 1; }
    echo "pull of $img failed (try $i); waiting $((i * 30)) s" >&2; sleep $((i * 30))
  done
done
for i in 1 2 3; do
  docker build $PF -f "$ROOT/backend/deploy/Dockerfile" -t "$TAG" "$@" "$ROOT" && exit 0
  echo "build failed (try $i); waiting $((i * 60)) s" >&2; sleep $((i * 60))
done
exit 1
