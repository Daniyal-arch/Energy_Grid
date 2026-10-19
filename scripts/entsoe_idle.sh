#!/usr/bin/env bash
# Wait until no "Lake ENTSO-E" run is in progress or queued (ENTSO-E banned the key when A78 ran
# beside the lake backfill). Usage: entsoe_idle.sh MAX_MINUTES. Exit 1 when still busy.
max=${1:-300}
for ((m = 0; m <= max; m += 5)); do
  busy=0
  for st in in_progress queued; do
    n=$(curl -s -H "Authorization: Bearer ${GITHUB_TOKEN:-}" \
      "https://api.github.com/repos/${GITHUB_REPOSITORY}/actions/workflows/lake-entsoe.yml/runs?status=$st&per_page=1" |
      python3 -c 'import json,sys; print(json.load(sys.stdin).get("total_count", 0))')
    busy=$((busy + n))
  done
  [ "$busy" -eq 0 ] && { echo "no Lake ENTSO-E run active"; exit 0; }
  echo "Lake ENTSO-E active ($busy run(s)); waiting ($m of $max min)"
  sleep 300
done
echo "Lake ENTSO-E still active after $max min"; exit 1
