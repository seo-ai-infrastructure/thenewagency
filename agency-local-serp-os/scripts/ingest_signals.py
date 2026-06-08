#!/usr/bin/env python3
"""Thin CLI -> automations/search-signals-ingest/run.py. See that file for flags."""
import sys, runpy, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.argv[0] = str(ROOT / "automations" / "search-signals-ingest" / "run.py")
runpy.run_path(sys.argv[0], run_name="__main__")
