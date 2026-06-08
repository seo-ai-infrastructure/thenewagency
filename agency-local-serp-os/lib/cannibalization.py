"""Ghost-Asset Cannibalization Alarm — deterministic, no LLM.

Agencies build 'controlled'/'influenced' assets (YouTube, Medium, directory profiles) to flood the
SERP. When one of those outranks the client's OWNED core domain for a transactional query, it can
steal direct-conversion attribution. This scans tracker records per SERP and flags those cases,
then emits a [De-optimization] recommendation (web/wordpress) to push internal equity back to the
core page. Like the other rec pipelines, output is a human-gated rec_*.json (via aeo_recs.write_recs).
"""
import hashlib
from collections import defaultdict

GHOST = ("controlled", "influenced")
TRANSACTIONAL = ("high", "medium_high")     # lead_value as a transactional-intent proxy


def _rid(*parts):
    return "rec_" + hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:10]


def detect_cannibalization(records, transactional_leads=TRANSACTIONAL):
    """Per (keyword, location, os, lane): if the best-ranked ghost asset outranks the best-ranked
    owned asset for a transactional keyword, flag it (lower rank_absolute = better position)."""
    groups = defaultdict(list)
    for r in records:
        groups[(r["keyword"], r.get("location_name", ""), r.get("os", ""), r.get("query_class", ""))].append(r)
    flags = []
    for (kw, loc, os_, qc), recs in groups.items():
        lead = recs[0].get("lead_value")
        if transactional_leads and lead not in transactional_leads:
            continue
        owned = [r for r in recs if r.get("ownership_class") == "owned" and r.get("rank_absolute") is not None]
        ghosts = [r for r in recs if r.get("ownership_class") in GHOST and r.get("rank_absolute") is not None]
        if not owned or not ghosts:
            continue
        best_owned = min(owned, key=lambda r: r["rank_absolute"])
        best_ghost = min(ghosts, key=lambda r: r["rank_absolute"])
        if best_ghost["rank_absolute"] < best_owned["rank_absolute"]:
            flags.append({"keyword": kw, "location": loc, "os": os_, "query_class": qc, "lead_value": lead,
                          "owned_rank": best_owned["rank_absolute"], "owned_domain": best_owned.get("domain"),
                          "ghost_rank": best_ghost["rank_absolute"], "ghost_domain": best_ghost.get("domain"),
                          "ghost_ownership": best_ghost.get("ownership_class"),
                          "ghost_feature": best_ghost.get("feature_type")})
    flags.sort(key=lambda f: (f["ghost_rank"], f["keyword"]))
    return flags


def cannibalization_recs(flags, client):
    """One [De-optimization] Structural Cannibalization Alert rec per flag (web/wordpress)."""
    out = []
    for f in flags:
        out.append({
            "recommendation_id": _rid("cannibal", client, f["keyword"], f.get("ghost_domain")),
            "client_id": client, "area": "web", "subsystem": "wordpress-publisher",
            "status": "pending_human_review", "kind": "structural_cannibalization",
            "gap": f,
            "suggested_action": (
                f"[De-optimization] Structural Cannibalization Alert: your {f['ghost_ownership']} asset "
                f"{f.get('ghost_domain')} (rank {f['ghost_rank']}) outranks your core domain "
                f"{f.get('owned_domain')} (rank {f['owned_rank']}) for the transactional query "
                f"'{f['keyword']}'. De-optimize the {f['ghost_ownership']} asset and push internal "
                f"links/CTAs to the core page to reset the natural hierarchy."),
            "note": "Human reviews before any de-optimization work order issues.",
        })
    return out
