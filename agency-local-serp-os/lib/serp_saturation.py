"""SERP saturation / multi-presence scoring.

The strategic goal is to occupy the SAME SERP 2+ times (stretch 4+) across ALL feature types
(organic + local pack/finder + people-also-ask + images + video + AI surface + forums +
shopping + ...). Where lib/estate_scoring measures *ownership-weighted share* of a SERP,
this measures *how many distinct placements* the client holds on each SERP and flags the
keywords short of the goal — with the unclaimed features as the concrete action list.

A slot counts as client presence when its ownership_class is owned/controlled/influenced
(AI surfaces become 'influenced' when the client is cited, so AI presence is captured too).
Consumes the same v3 snapshot records the tracker writes; no network.

Goal thresholds are env-overridable (a PM can retune without a code edit):
  SATURATION_GOAL_MIN      (default 2)  — at/above this, the SERP meets the goal
  SATURATION_GOAL_STRETCH  (default 4)  — above this, the SERP is in the stretch band
"""
import os
from collections import defaultdict

PRESENT = {"owned", "controlled", "influenced"}
AI_SURFACES = {"ai_overview", "ai_mode_response"}


def _appearances(present):
    """How many TIMES the client is on the page (the takeover count). Each owned/controlled
    placement counts once, de-duped across lanes by (feature, url) so the same listing returned
    by two DataForSEO lanes isn't double-counted. An AI surface counts once per client citation —
    an AI Overview that cites the client twice is two appearances — because that is how the
    operator reads the page ("we're on this SERP N times")."""
    seen, total = set(), 0
    for r in present:
        ft = r.get("feature_type")
        if ft in AI_SURFACES:
            total += max(1, r.get("client_citation_count") or 1)
        else:
            key = (ft, r.get("url") or r.get("domain") or r.get("rank_group"))
            if key in seen:
                continue
            seen.add(key)
            total += 1
    return total


def _goal(goal_min, goal_stretch):
    gm = int(os.environ.get("SATURATION_GOAL_MIN", "2")) if goal_min is None else goal_min
    gs = int(os.environ.get("SATURATION_GOAL_STRETCH", "4")) if goal_stretch is None else goal_stretch
    return gm, gs


def _serp_key(r):
    # One real-world SERP = the page a searcher actually sees: keyword + location + device.
    # The three DataForSEO lanes (local_finder / organic_mobile / ai_mode) are just collection
    # splits of that SAME page, so they are UNIONED here. The takeover goal — "be on the same
    # SERP 4-6+ times" — is measured against that real page, NOT against each lane separately
    # (counting per-lane structurally prevented ever reaching the goal).
    return (r["keyword"], r["location_name"], r["os"])


def saturate_serp(records, goal_min=None, goal_stretch=None):
    """The multi-presence picture for ONE real-world SERP. `records` share keyword+location+device;
    the lanes composing that page are unioned. A placement = a DISTINCT feature_type the client
    holds, so the same feature captured in two lanes (e.g. a local_pack returned by both the
    local_finder and organic lanes) counts once rather than inflating the takeover count."""
    goal_min, goal_stretch = _goal(goal_min, goal_stretch)
    present = [r for r in records if r.get("ownership_class") in PRESENT]
    held = sorted({r["feature_type"] for r in present})
    on_serp = sorted({r["feature_type"] for r in records})
    competitor = sorted({r["feature_type"] for r in records
                         if r.get("ownership_class") == "competitor"})
    unclaimed = [f for f in on_serp if f not in held]   # present on the SERP, client absent
    count = _appearances(present)                        # TIMES on the page (AI citations counted)
    lanes = sorted({r.get("query_class") for r in records if r.get("query_class")})
    breakdown = {}
    for r in present:
        breakdown.setdefault(r.get("query_class"), set()).add(r["feature_type"])
    lane_breakdown = {ln: sorted(fts) for ln, fts in sorted(breakdown.items())}
    band = ("above" if count > goal_stretch else
            "in_band" if count >= goal_min else "below")
    r0 = records[0]
    return {
        "keyword": r0["keyword"], "location": r0["location_name"], "os": r0["os"],
        # query_class kept (schema) as the joined lanes that make up this page; `lanes` +
        # `lane_breakdown` give the structured per-lane drill-down.
        "query_class": ", ".join(lanes), "lanes": lanes, "lane_breakdown": lane_breakdown,
        "lead_value": r0.get("lead_value"),
        "presence_count": count,
        "distinct_features_held": len(held),
        "features_held": held,
        "features_unclaimed": unclaimed,
        "competitor_features": competitor,
        "total_features_on_serp": len(on_serp),
        "goal_min": goal_min, "goal_stretch": goal_stretch,
        "meets_goal": count >= goal_min,
        "goal_band": band,
        "gap_to_goal": max(0, goal_min - count),
    }


def saturation(records, goal_min=None, goal_stretch=None):
    """Group records into SERPs and score each. Sorted biggest-gap-first = the action queue."""
    groups = defaultdict(list)
    for r in records:
        groups[_serp_key(r)].append(r)
    serps = [saturate_serp(recs, goal_min, goal_stretch) for recs in groups.values()]
    serps.sort(key=lambda s: (-s["gap_to_goal"], s["keyword"], s["location"], s["os"]))
    return serps


def summary(records, goal_min=None, goal_stretch=None):
    """Estate-level roll-up: how saturated is the whole tracked keyword set?"""
    serps = saturation(records, goal_min, goal_stretch)
    gm, gs = _goal(goal_min, goal_stretch)
    n = len(serps)
    meeting = sum(1 for s in serps if s["meets_goal"])
    avg = round(sum(s["presence_count"] for s in serps) / n, 2) if n else 0.0
    return {
        "goal_min": gm, "goal_stretch": gs,
        "n_serps": n,
        "n_meeting_goal": meeting,
        "pct_meeting_goal": round(meeting / n, 4) if n else 0.0,
        "avg_presence": avg,
        "below_goal": [s for s in serps if not s["meets_goal"]],
        "serps": serps,
    }
