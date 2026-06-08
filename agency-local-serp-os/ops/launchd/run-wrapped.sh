#!/bin/bash
# launchd entrypoint. Resolves the repo from its own location, loads secrets.env (which a
# scheduled job otherwise never sees), ensures a sane PATH, then execs the given command.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"   # cover system + Homebrew python
if [ -f "$REPO/secrets.env" ]; then set -a; . "$REPO/secrets.env"; set +a; fi
exec "$@"
