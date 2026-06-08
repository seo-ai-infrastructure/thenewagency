"""Unit tests for AEO recommendation generation (lib/aeo_recs):
Citation Conquest (AI surface lost to a cited competitor -> wordpress-publisher draft) and
Aggregator Conquest (directory holds the slot -> cloakbrowser listing-optimization job).
Deterministic, no LLM, mirrors scripts/gaps_to_recommendations. Hermetic."""
import json
from lib import aeo_recs


RECS = [
    # AI overview, client NOT cited, competitor cited -> citation conquest
    {"client_id": "c1", "keyword": "best ac repair", "feature_type": "ai_overview",
     "query_class": "organic_mobile", "client_cited": False, "cited_competitors": ["rival.com"],
     "cited_sources": ["rival.com"], "ownership_class": "competitor", "lead_value": "high"},
    # AI mode, already cited -> NO conquest rec
    {"client_id": "c1", "keyword": "ac maintenance", "feature_type": "ai_mode_response",
     "query_class": "ai_mode", "client_cited": True, "cited_competitors": [],
     "cited_sources": ["mybiz.com"], "ownership_class": "influenced", "lead_value": "high"},
    # aggregator holds the local pack -> aggregator conquest (cloakbrowser)
    {"client_id": "c1", "keyword": "ac repair near me", "feature_type": "local_pack",
     "query_class": "local_finder", "ownership_class": "aggregator", "domain": "yelp.com",
     "client_cited": False, "cited_competitors": [], "lead_value": "high"},
    # plain competitor organic -> neither pipeline
    {"client_id": "c1", "keyword": "hvac", "feature_type": "organic", "query_class": "organic_mobile",
     "ownership_class": "competitor", "domain": "rival.com", "client_cited": False,
     "cited_competitors": [], "lead_value": "low"},
]


def test_citation_conquest_targets_uncited_ai_with_competitor():
    recs = aeo_recs.citation_conquest(RECS, "c1")
    assert len(recs) == 1
    r = recs[0]
    assert r["area"] == "web" and r["subsystem"] == "wordpress-publisher"
    assert r["kind"] == "ai_citation_conquest"
    assert r["gap"]["keyword"] == "best ac repair" and "rival.com" in r["gap"]["competitors"]
    assert r["recommendation_id"].startswith("rec_")


def test_citation_conquest_skips_when_already_cited():
    assert all(r["gap"]["keyword"] != "ac maintenance" for r in aeo_recs.citation_conquest(RECS, "c1"))


def test_aggregator_conquest_routes_to_cloakbrowser():
    recs = aeo_recs.aggregator_conquest(RECS, "c1")
    assert len(recs) == 1
    r = recs[0]
    assert r["area"] == "browser" and r["subsystem"] == "cloakbrowser"
    assert r["kind"] == "aggregator_listing_optimization"
    assert r["gap"]["aggregator"] == "yelp.com" and r["gap"]["keyword"] == "ac repair near me"


def test_recommendation_ids_are_deterministic():
    a = aeo_recs.citation_conquest(RECS, "c1")[0]["recommendation_id"]
    b = aeo_recs.citation_conquest(RECS, "c1")[0]["recommendation_id"]
    assert a == b


def test_entity_conquest_recs_targets_missing_entities():
    evaluation = {"entity_conquest": {"hours": ["rival.com"], "guarantee": ["rival.com", "other.com"]}}
    recs = aeo_recs.entity_conquest_recs(evaluation, "c1")
    assert len(recs) == 2
    for r in recs:
        assert r["area"] == "web"
        assert r["subsystem"] == "wordpress-publisher"
        assert r["kind"] == "aeo_entity_injection"
        assert r["recommendation_id"].startswith("rec_")
    hours_rec = next(r for r in recs if r["gap"]["entity"] == "hours")
    assert "rival.com" in hours_rec["gap"]["competitors"]
    guarantee_rec = next(r for r in recs if r["gap"]["entity"] == "guarantee")
    assert guarantee_rec["gap"]["competitors"] == ["rival.com", "other.com"]


def test_entity_conquest_recs_empty_when_no_gaps():
    assert aeo_recs.entity_conquest_recs({"entity_conquest": {}}, "c1") == []


def test_entity_conquest_recs_handles_none():
    assert aeo_recs.entity_conquest_recs(None, "c1") == []


def test_entity_conquest_recs_ids_deterministic():
    evaluation = {"entity_conquest": {"hours": ["rival.com"]}}
    a = aeo_recs.entity_conquest_recs(evaluation, "c1")[0]["recommendation_id"]
    b = aeo_recs.entity_conquest_recs(evaluation, "c1")[0]["recommendation_id"]
    assert a == b


def test_write_recs_lands_in_area_pending_with_rec_prefix(tmp_path):
    recs = aeo_recs.citation_conquest(RECS, "c1") + aeo_recs.aggregator_conquest(RECS, "c1")
    paths = aeo_recs.write_recs(tmp_path, recs)
    assert len(paths) == 2
    web = tmp_path / "clients" / "c1" / "web" / "approvals" / "pending"
    browser = tmp_path / "clients" / "c1" / "browser" / "approvals" / "pending"
    web_files = list(web.glob("rec_*.json"))
    assert web_files and json.loads(web_files[0].read_text())["status"] == "pending_human_review"
    assert json.loads(web_files[0].read_text())["created"]            # writer stamps a timestamp
    assert list(browser.glob("rec_*.json"))
