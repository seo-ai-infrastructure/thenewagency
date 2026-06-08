#!/usr/bin/env python3
"""AEO gaps -> recommendations (deterministic, no LLM).

Reads the latest mobile-SERP tracker history and writes:
  - Citation Conquest recs (AI surface lost to a cited competitor) -> web/approvals/pending
  - Aggregator Conquest recs (directory holds the slot)            -> browser/approvals/pending
Human-reviewed recommendations, exactly like scripts/gaps_to_recommendations — never executable
work orders on their own. board_scan surfaces them in NEEDS APPROVAL.

  python scripts/aeo_gaps_to_recommendations.py [--client <id>]
"""
import sys, json, glob, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from lib import aeo_recs
CLIENT = sys.argv[sys.argv.index("--client") + 1] if "--client" in sys.argv else "example-hvac-client"


def main():
    files = sorted(glob.glob(str(ROOT / "automations" / "local-mobile-serp-feature-tracker" / "history" / "*.jsonl")))
    if not files:
        sys.exit("no tracker history — run the SERP tracker first")
    
    # Load all runs for velocity tracking
    from lib import paa_velocity
    runs_data = []
    for f in files:
        run_id = pathlib.Path(f).stem
        records = []
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip(): continue
                try: records.append(json.loads(line))
                except Exception: continue
        scoped = [r for r in records if r.get("client_id") in (CLIENT, None)] or records
        runs_data.append((run_id, scoped))
        
    latest_scoped = runs_data[-1][1]
    
    cc = aeo_recs.citation_conquest(latest_scoped, CLIENT)
    ag = aeo_recs.aggregator_conquest(latest_scoped, CLIENT)
    
    # PAA Velocity
    paa_events = paa_velocity.detect_velocity(runs_data)
    paa = paa_velocity.velocity_recs(paa_events, CLIENT)
    
    paths = aeo_recs.write_recs(ROOT, cc + ag + paa)
    print(f"[aeo] {len(cc)} citation, {len(ag)} aggregator, {len(paa)} paa velocity rec(s) "
          f"-> clients/{CLIENT}/(web|browser)/approvals/pending/ ({len(paths)} files)")


if __name__ == "__main__":
    main()
