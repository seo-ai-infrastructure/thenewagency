#!/usr/bin/env python3
"""Create a hashed, scoped, expiring, single-use approval artifact.
  python make_approval.py <client> <profile> <workflow> <period> "<approved content>" [days]"""
import sys, pathlib

def root(s):
    for d in [s, *s.parents]:
        if (d/"integrations"/"duoplus").exists(): return d
    raise SystemExit("root not found")
ROOT = root(pathlib.Path(__file__).resolve().parent)
sys.path.insert(0, str(ROOT))
from lib import approvals   # single source of truth for hashing/scope/expiry + atomic write

if len(sys.argv) < 6:
    raise SystemExit('usage: make_approval.py <client> <profile> <workflow> <period> "<content>" [days]')
client, profile, workflow, period, content = sys.argv[1:6]
days = int(sys.argv[6]) if len(sys.argv) > 6 else 7
# write_approval creates the approved/ dir if missing and writes atomically (tmp + replace),
# producing the exact artifact shape verify_approval expects.
out, h = approvals.write_approval(ROOT, client, "rpa", profile, workflow, period,
                                  {"text": content}, days=days,
                                  provenance={"source": "make_approval.py cli"})
print(f"approval written: {out.name}  (hash {h[:12]}…, expires {days}d)")
