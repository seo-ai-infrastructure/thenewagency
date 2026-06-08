#!/usr/bin/env python3
"""Human approval step (CLI). Thin wrapper over lib.approvals.approve_draft.
  python scripts/approve_draft.py <client> <scope> <workflow> <period> [days] [--edit "text"] [--area rpa|browser]"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from lib.approvals import approve_draft
client, scope, workflow, period = sys.argv[1:5]
days = int(sys.argv[5]) if len(sys.argv) > 5 and not sys.argv[5].startswith("--") else 7
edit = sys.argv[sys.argv.index("--edit")+1] if "--edit" in sys.argv else None
area = sys.argv[sys.argv.index("--area")+1] if "--area" in sys.argv else "rpa"
out, h = approve_draft(ROOT, client, area, scope, workflow, period, days, edit)
print(f"approved: {out.name} (hash {h[:12]}…, expires {days}d, area {area})")
