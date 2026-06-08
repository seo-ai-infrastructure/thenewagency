"""AEO recommendation generation — deterministic, no LLM. Two pipelines off the SERP tracker:

  Citation Conquest:   an AI surface (ai_overview / ai_mode_response) where the client is NOT
                       cited but a competitor IS -> a wordpress-publisher draft to displace them.
  Aggregator Conquest: a directory (yelp/angi/...) holds the slot -> a cloakbrowser job to
                       optimize the client's LISTING inside that aggregator (never a new page).

Like scripts/gaps_to_recommendations, these are RECOMMENDATIONS for a human (rec_*.json in the
owning area's approvals/pending/), not executable work orders. board_scan renders them in
NEEDS APPROVAL; only an approved artifact lets the scheduler issue a real work order.
"""
import json
import hashlib
import datetime
import pathlib

AI_SURFACES = ("ai_overview", "ai_mode_response")


def _rid(*parts):
    return "rec_" + hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:10]


def citation_conquest(records, client):
    """AI surfaces the client lost to a cited competitor -> content-displacement recs (web)."""
    out, seen = [], set()
    for r in records:
        if r.get("feature_type") not in AI_SURFACES:
            continue
        if r.get("client_cited"):
            continue
        comps = r.get("cited_competitors") or []
        if not comps:
            continue
        key = (r["keyword"], r["feature_type"])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "recommendation_id": _rid("citation", client, *key),
            "client_id": client, "area": "web", "subsystem": "wordpress-publisher",
            "status": "pending_human_review", "kind": "ai_citation_conquest",
            "gap": {"keyword": r["keyword"], "feature_type": r["feature_type"],
                    "query_class": r.get("query_class"), "competitors": comps,
                    "cited_sources": r.get("cited_sources", []), "lead_value": r.get("lead_value")},
            "suggested_action": (f"AI Citation Conquest: {', '.join(comps)} cited for "
                                 f"'{r['keyword']}' and you are not. Publish authoritative content "
                                 f"covering this nuance to displace their citation."),
            "note": "Human reviews + supplies approved content before any publish work order issues.",
        })
    return out


def aggregator_conquest(records, client):
    """Slots a directory holds for the client -> optimize the client's listing inside it (browser)."""
    out, seen = [], set()
    for r in records:
        if r.get("ownership_class") != "aggregator":
            continue
        domain = (r.get("domain") or "").lower()
        key = (r["keyword"], domain, r.get("feature_type"))
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "recommendation_id": _rid("aggregator", client, *key),
            "client_id": client, "area": "browser", "subsystem": "cloakbrowser",
            "status": "pending_human_review", "kind": "aggregator_listing_optimization",
            "gap": {"keyword": r["keyword"], "feature_type": r.get("feature_type"),
                    "query_class": r.get("query_class"), "aggregator": domain,
                    "lead_value": r.get("lead_value")},
            "suggested_action": (f"Aggregator '{domain}' holds the {r.get('feature_type')} slot for "
                                 f"'{r['keyword']}'. Optimize the client's listing INSIDE {domain} "
                                 f"(cloakbrowser profile job) — do not build a new page."),
            "note": "Human reviews before any cloakbrowser profile work order issues.",
        })
    return out


def entity_conquest_recs(evaluation, client):
    """Entities a competitor states but the client does NOT -> AEO entity-injection recs (web).

    `evaluation` is the dict returned by lib.aeo_evaluator.evaluate().  Its
    `entity_conquest` key maps entity_name -> list of competitor domains that
    explicitly state that entity while the client does not.  One rec per
    missing entity; empty list when there are no gaps.
    """
    out = []
    for entity_name, competitor_domains in (evaluation or {}).get("entity_conquest", {}).items():
        domains = list(competitor_domains)
        out.append({
            "recommendation_id": _rid("entity", client, entity_name),
            "client_id": client, "area": "web", "subsystem": "wordpress-publisher",
            "status": "pending_human_review", "kind": "aeo_entity_injection",
            "gap": {"entity": entity_name, "competitors": domains},
            "suggested_action": (
                f"AEO Entity Injection: competitors {', '.join(domains)} explicitly state "
                f"'{entity_name}' and your site does not. Add explicit, machine-readable "
                f"'{entity_name}' text to the relevant page so AI crawlers can extract it."
            ),
            "note": "Human reviews + supplies approved copy before any publish work order issues.",
        })
    return out


def write_recs(root, recs):
    """Write each rec to clients/<client>/<area>/approvals/pending/<rid>.json (atomic). Stamps
    `created` here so the generator functions stay deterministic/testable."""
    root = pathlib.Path(root)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    paths = []
    for rec in recs:
        rec = {**rec, "created": now}
        pending = root / "clients" / rec["client_id"] / rec["area"] / "approvals" / "pending"
        pending.mkdir(parents=True, exist_ok=True)
        out = pending / f"{rec['recommendation_id']}.json"
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rec, indent=2))
        tmp.replace(out)
        paths.append(out)
    return paths
