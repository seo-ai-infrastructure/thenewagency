#!/usr/bin/env python3
"""Cadence orchestrator CLI (Plan 3) — the autonomous-loop conductor.

Chains ingest Signals -> generate (drafts + work orders) -> gated publish, on a schedule.
GATE-SAFE: it only prepares + runs the publish lane; publishers ship ONLY approved artifacts.

  python scripts/cadence.py --frequency daily|weekly|monthly --client <id> [--dry-run]

Wire it to Windows Task Scheduler / cron: daily 1x/day, weekly on its day, monthly on the 1st.
--dry-run makes the whole chain offline (ingest skips missing creds; publishers fake their calls).
"""
import sys, subprocess, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()
from lib import cadence


def execute(name, argv):
    """Run a step as a subprocess; return (ok, last-line-of-output)."""
    r = subprocess.run([sys.executable, str(ROOT / argv[0])] + argv[1:],
                       cwd=str(ROOT), capture_output=True, text=True)
    out = (r.stdout or "").strip().splitlines()
    return r.returncode == 0, (out[-1] if out else (r.stderr or "")[-200:])


def main():
    def arg(n, d=None): return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
    freq = arg("--frequency", "daily")
    client = arg("--client", "example-hvac-client")
    dry = "--dry-run" in sys.argv
    print(f"[cadence] {freq} for {client}{' (dry-run)' if dry else ''}")
    log = cadence.run_cadence(freq, client, execute, dry=dry)
    for e in log:
        print(f"  {'OK ' if e['ok'] else 'ERR'} {e['step']:20s} {e['output'][:90]}")
    ok = sum(1 for e in log if e["ok"])
    print(f"[cadence] {ok}/{len(log)} steps ok")
    sys.exit(0 if ok == len(log) else 1)


if __name__ == "__main__":
    main()
