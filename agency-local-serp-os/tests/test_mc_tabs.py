"""Unit tests for the Search Intelligence and AI Search dashboard tabs
(lib/mission_control.search_intelligence / ai_search). Read-only projections; hermetic."""
import json
from lib import mission_control as mc


def _root(tmp_path):
    root = tmp_path
    cfg = root / "clients" / "c1" / "config"; cfg.mkdir(parents=True)
    (cfg / "sources.yaml").write_text(
        "version: 1\ngsc:\n  site_url: \"https://ex.com/\"\nbing:\n  site_url: \"https://ex.com/\"\n"
        "clarity:\n  enabled: true\ngbp_insights:\n  zernio_account_id: \"a\"\n")
    sig = root / "clients" / "c1" / "signals"; sig.mkdir(parents=True)
    (sig / "2026-06-06.json").write_text(json.dumps({
        "client": "c1", "date": "2026-06-06",
        "search": {
            "gsc": [
                {"query": "ac repair ftl", "clicks": 5, "impressions": 100, "ctr": 0.05, "position": 8.2},
                {"query": "ac maintenance", "clicks": 0, "impressions": 50, "ctr": 0.0, "position": 22},
                {"query": "emergency ac", "clicks": 10, "impressions": 200, "ctr": 0.05, "position": 3.1}],
            "bing": [{"query": "hvac ftl", "impressions": 10, "clicks": 1,
                      "avg_impression_position": 6, "avg_click_position": 4}]},
        "local": {"gbp": {}}, "behavior": {"ga4": [], "clarity": {}}, "derived": {}}))
    th = root / "automations" / "local-mobile-serp-feature-tracker" / "history"; th.mkdir(parents=True)
    recs = [
        {"query_class": "local_finder", "keyword": "ac repair", "location_name": "FTL", "os": "ios",
         "ownership_class": "owned", "feature_type": "local_finder", "rank_absolute": 2,
         "lead_value": "high", "client_cited": False, "cited_sources": [], "cited_competitors": []},
        {"query_class": "local_finder", "keyword": "ac repair", "location_name": "FTL", "os": "ios",
         "ownership_class": "competitor", "feature_type": "organic", "rank_absolute": 5,
         "lead_value": "high", "client_cited": False, "cited_sources": [], "cited_competitors": []},
        {"query_class": "organic_mobile", "keyword": "ac repair cost", "location_name": "FTL", "os": "ios",
         "ownership_class": "competitor", "feature_type": "organic", "rank_absolute": 1,
         "lead_value": "medium", "client_cited": False, "cited_sources": [], "cited_competitors": ["rival.com"]},
        {"query_class": "organic_mobile", "keyword": "ac repair cost", "location_name": "FTL", "os": "ios",
         "ownership_class": "influenced", "feature_type": "ai_overview", "rank_absolute": 1,
         "lead_value": "medium", "client_cited": True, "cited_sources": ["mybiz.com"], "cited_competitors": ["rival.com"]},
        {"query_class": "ai_mode", "keyword": "who fixes ac", "location_name": "FTL", "os": "ios",
         "ownership_class": "influenced", "feature_type": "ai_mode_response", "rank_absolute": None,
         "lead_value": "high", "client_cited": True, "cited_sources": ["mybiz.com", "ref.com"], "cited_competitors": []},
        {"query_class": "ai_mode", "keyword": "best ac company", "location_name": "FTL", "os": "ios",
         "ownership_class": "competitor", "feature_type": "ai_mode_response", "rank_absolute": None,
         "lead_value": "high", "client_cited": False, "cited_sources": ["rival.com"], "cited_competitors": ["rival.com"]},
    ]
    (th / "mobile_serp_20260606T000000Z.jsonl").write_text("\n".join(json.dumps(r) for r in recs))
    return root


# ---------------- Search Intelligence ----------------
def test_search_performance_totals(tmp_path):
    si = mc.search_intelligence(_root(tmp_path), "c1")
    sp = si["search_performance"]
    assert sp["gsc"]["has_data"] is True and sp["gsc"]["totals"]["clicks"] == 15
    assert sp["gsc"]["totals"]["impressions"] == 350
    assert sp["bing"]["totals"]["impressions"] == 10 and sp["bing"]["has_data"] is True


def test_striking_distance_only_positions_5_to_15(tmp_path):
    si = mc.search_intelligence(_root(tmp_path), "c1")
    q = [r["query"] for r in si["striking_distance"]]
    assert "ac repair ftl" in q          # position 8.2 -> quick win
    assert "emergency ac" not in q        # position 3.1 -> already top
    assert "ac maintenance" not in q      # position 22 -> too far


def test_keyword_rankings_client_best_rank(tmp_path):
    si = mc.search_intelligence(_root(tmp_path), "c1")
    lf = {r["keyword"]: r for r in si["keyword_rankings"]["local_finder"]}
    assert lf["ac repair"]["present"] is True and lf["ac repair"]["best_rank"] == 2
    assert lf["ac repair"]["best_competitor_rank"] == 5


def test_search_intelligence_validates_client(tmp_path):
    si = mc.search_intelligence(_root(tmp_path), "../../etc")   # crafted -> falls back
    assert si["client"] == "c1"


# ---------------- AI Search ----------------
def test_ai_search_citation_counts(tmp_path):
    ai = mc.ai_search(_root(tmp_path), "c1")
    assert ai["n_queries"] == 3           # ac repair cost (AIO), who fixes ac, best ac company
    assert ai["n_cited"] == 2             # client cited on 2 of 3
    assert ai["citation_share"] == round(2 / 3, 4)


def test_ai_search_competitor_leaderboard(tmp_path):
    ai = mc.ai_search(_root(tmp_path), "c1")
    top = ai["cited_competitors_leaderboard"][0]
    assert top["domain"] == "rival.com" and top["count"] == 2


def test_ai_search_uncited_queries_surface_first(tmp_path):
    ai = mc.ai_search(_root(tmp_path), "c1")
    # the not-yet-cited AI query is the action item -> it sorts first
    assert ai["queries"][0]["client_cited"] is False
    assert ai["queries"][0]["keyword"] == "best ac company"


# ---------------- AEO tab ----------------
def test_aeo_conquest_queue_from_ai_gaps(tmp_path):
    aeo = mc.aeo(_root(tmp_path), "c1")
    kws = [c["gap"]["keyword"] for c in aeo["conquest_queue"]["citation"]]
    assert "best ac company" in kws            # uncited AI query w/ competitor -> conquest item
    assert aeo["conquest_queue"]["n"] >= 1
    assert aeo["crawlability"] is None         # no crawl run yet -> graceful empty
    assert aeo["client"] == "c1"


def test_aeo_validates_client(tmp_path):
    assert mc.aeo(_root(tmp_path), "../../x")["client"] == "c1"


# ---------------- Real-Time Feedback tab ----------------
def test_competition_intell_demo_payload(tmp_path):
    ci = mc.competition_intell(_root(tmp_path), "c1")
    assert ci["client"] == "c1"
    assert ci["title"] == "House AC Repair Real-Time Feedback"
    assert ci["summary"]["competitors"] == 3
    assert ci["summary"]["market_leader"] == "Quality Air"
    assert ci["competitors"][0]["profile_reviews"] == 1010
    assert ci["competitors"][0]["review_velocity_share"] == 43.5
    assert ci["hiring_signals"]["status"] == "pending"
    assert any(a["issue"] == "Pricing / surprise charges" for a in ci["issue_angles"])


def test_competition_intell_validates_client(tmp_path):
    assert mc.competition_intell(_root(tmp_path), "../../x")["client"] == "c1"
