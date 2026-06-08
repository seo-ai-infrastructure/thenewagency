#!/bin/bash
# Install + load both launchd agents (always-on board, morning work-order issuance).
#   bash ops/launchd/install.sh          # install + load
#   bash ops/launchd/install.sh remove   # unload + delete
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LA="$HOME/Library/LaunchAgents"
JOBS=(com.agency.serp.board com.agency.serp.genworkorders)
mkdir -p "$LA" "$REPO/ops/launchd/logs"

if [ "${1:-}" = "remove" ]; then
  for j in "${JOBS[@]}"; do
    launchctl unload "$LA/$j.plist" 2>/dev/null || true
    rm -f "$LA/$j.plist"; echo "removed $j"
  done
  exit 0
fi

for j in "${JOBS[@]}"; do
  sed "s#__REPO__#$REPO#g" "$REPO/ops/launchd/$j.plist.template" > "$LA/$j.plist"
  launchctl unload "$LA/$j.plist" 2>/dev/null || true
  launchctl load -w "$LA/$j.plist"     # modern equivalent: launchctl bootstrap gui/$(id -u) "$LA/$j.plist"
  echo "loaded $j"
done
echo
echo "Board:  http://127.0.0.1:8787"
echo "Logs:   $REPO/ops/launchd/logs/"
echo "Issue job runs daily at 07:00. Run now to test: launchctl start com.agency.serp.genworkorders"
