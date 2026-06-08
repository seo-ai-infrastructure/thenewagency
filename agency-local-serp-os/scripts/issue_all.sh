#!/bin/bash
# Issue today's work orders for every client that has any schedules. No --date = today.
set -euo pipefail
cd "$(dirname "$0")/.."
for d in clients/*/; do
  c="$(basename "$d")"
  if [ -f "clients/$c/rpa/schedules.yaml" ] || [ -f "clients/$c/browser/schedules.yaml" ] || [ -f "clients/$c/web/schedules.yaml" ]; then
    echo "[issue_all] $c"
    python3 scripts/gen_workorders.py --client "$c" || echo "  (skipped $c: $?)"
  fi
done
python3 scripts/notify_digest.py || true
