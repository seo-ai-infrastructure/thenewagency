#!/usr/bin/env python3
"""SERP Estate -> RPA handoff (deterministic, no LLM).

Reads the latest mobile-SERP tracker history, finds HIGH-value slots the client does
NOT own (lost to a competitor or unclaimed), and writes one recommendation per gap into
the client's approvals/pending/ folder.

These are RECOMMENDATIONS for a human, not executable work orders. A person reviews the
gap, decides the action, and supplies approved content; only then does an approved
artifact exist and the scheduler issue an RPA work order. The bridge does the first hop
only — it never decides to act on its own.

  python scripts/gaps_to_recommendations.py [--client <id>]"""
import sys, json, glob, hashlib, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLIENT = sys.argv[sys.argv.index("--client")+1] if "--client" in sys.argv else "example-hvac-client"

WINNABLE = {"organic_video", "local_pack", "local_finder", "featured_snippet",
            "ai_overview", "ai_mode_response"}
HIGH = {"high", "medium_high"}
ACTION = {
    "organic_video":     "Produce + publish a short video targeting this query.",
    "local_pack":        "GBP optimization (categories, posts, photos, reviews).",
    "local_finder":      "GBP / local optimization to enter the map pack.",
    "featured_snippet":  "Publish concise answer content structured for the snippet.",
    "ai_overview":       "Earn the AI citation with authoritative, well-structured content.",
    "ai_mode_response":  "Earn the AI Mode citation with authoritative content.",
}

def latest_tracker_history():
    files = sorted(glob.glob(str(ROOT/"automations"/"local-mobile-serp-feature-tracker"/"history"/"*.jsonl")))
    return files[-1] if files else None

def main():
    hist = latest_tracker_history()
    if not hist:
        sys.exit("no tracker history — run the SERP tracker first")
    with open(hist, encoding="utf-8") as fh:
        recs = [json.loads(l) for l in fh if l.strip()]
    pending = ROOT/"clients"/CLIENT/"rpa"/"approvals"/"pending"
    pending.mkdir(parents=True, exist_ok=True)

    seen, n = set(), 0
    for r in recs:
        if r.get("ownership_class") not in ("competitor", "unknown"): continue
        if r.get("feature_type") not in WINNABLE: continue
        if (r.get("lead_value") or "") not in HIGH: continue
        dedupe = (r["keyword"], r["feature_type"])
        if dedupe in seen: continue
        seen.add(dedupe)
        rid = "rec_" + hashlib.sha1(f"{dedupe}".encode()).hexdigest()[:10]
        rec = {
            "recommendation_id": rid, "client_id": CLIENT,
            "status": "pending_human_review",            # NOT executable yet
            "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "gap": {"keyword": r["keyword"], "feature_type": r["feature_type"],
                    "ownership_class": r["ownership_class"], "lead_value": r.get("lead_value"),
                    "query_class": r.get("query_class"), "competitors": r.get("cited_competitors", [])},
            "suggested_action": ACTION.get(r["feature_type"], "Review and decide an action."),
            "note": ("Human must choose the action and supply approved content. Only an "
                     "approved artifact lets the scheduler issue an RPA work order."),
        }
        (pending/f"{rid}.json").write_text(json.dumps(rec, indent=2)); n += 1
    print(f"[gaps] {n} gap recommendation(s) -> clients/{CLIENT}/rpa/approvals/pending/")

if __name__ == "__main__":
    main()
