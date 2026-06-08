#!/usr/bin/env python3
"""Dry-run the whole chain on fixtures: tracker -> estate scoring."""
import subprocess, sys, pathlib
R = pathlib.Path(__file__).parent
for step in ["automations/local-mobile-serp-feature-tracker/run.py",
             "automations/serp-estate-scoring/run.py"]:
    print(f"\n=== {step} ===")
    rc = subprocess.run([sys.executable, str(R/step)] +
                        (["--dry-run"] if "tracker" in step else [])).returncode
    if rc != 0:                       # don't let the scorer run on a previous run's history
        sys.exit(f"step failed (exit {rc}): {step}")
