"""Unit tests for the core ownership classifier (lib/serp_features.classify) — the repo's
headline deliverable. Pure logic; no network."""
from lib import serp_features as sf

ASSETS = {"owned": ["mybiz.com", "youtube.com/@mybiz"], "controlled": ["mybiz.gbp"],
          "influenced": ["partnerblog.com"]}
COMP = ["competitor.com", "rival.com"]


def _item(itype, **kw):
    d = {"type": itype}; d.update(kw); return d


def test_all_feature_types_are_tracked():
    # GOAL: occupy the SAME SERP 4-6+ times across ALL features, so NOTHING is silently
    # dropped. Unmapped DataForSEO item types pass through under their own name; mapped
    # types still normalize (answer_box -> featured_snippet). (flips the old skip behavior)
    slots = sf.classify(
        [_item("paid"), _item("shopping", domain="x.com"), _item("top_stories"),
         _item("answer_box", domain="x.com"), _item("organic", domain="x.com")],
        "organic_mobile", ASSETS, COMP)
    assert [s["feature_type"] for s in slots] == [
        "paid", "shopping", "top_stories", "featured_snippet", "organic"]


def test_item_without_a_type_is_skipped():
    # only truly untyped items are dropped — we can't name the feature for one with no type
    slots = sf.classify([{"domain": "x.com"}, _item("organic", domain="x.com")],
                        "organic_mobile", ASSETS, COMP)
    assert [s["feature_type"] for s in slots] == ["organic"]


def test_owned_domain_is_owned():
    s = sf.classify([_item("organic", domain="mybiz.com", url="https://mybiz.com/x")],
                    "organic_mobile", ASSETS, COMP)[0]
    assert s["ownership_class"] == "owned" and s["client_mentioned"] is True


def test_competitor_and_unknown():
    assert sf.classify([_item("organic", domain="competitor.com")], "organic_mobile",
                       ASSETS, COMP)[0]["ownership_class"] == "competitor"
    assert sf.classify([_item("organic", domain="nobody.com")], "organic_mobile",
                       ASSETS, COMP)[0]["ownership_class"] == "unknown"


def test_place_id_makes_local_pack_controlled():
    s = sf.classify([_item("local_pack", url="https://maps.google.com/?cid=PLACE123")],
                    "local_finder", ASSETS, COMP, place_id="PLACE123")[0]
    assert s["feature_type"] == "local_pack" and s["ownership_class"] == "controlled"


def test_reddit_organic_reclassified_to_forum():
    s = sf.classify([_item("organic", domain="reddit.com", url="https://reddit.com/r/x")],
                    "organic_mobile", ASSETS, COMP)[0]
    assert s["feature_type"] == "discussions_and_forums_element"


def test_ai_surface_relabeled_by_lane():
    assert sf.classify([_item("ai_overview")], "organic_mobile", ASSETS, COMP)[0]["feature_type"] == "ai_overview"
    assert sf.classify([_item("ai_overview")], "ai_mode", ASSETS, COMP)[0]["feature_type"] == "ai_mode_response"


def test_ai_surface_scored_by_citation_not_appearance():
    # client cited among references -> influenced (NOT owned, even though the domain appears)
    s = sf.classify([_item("ai_overview", references=[{"domain": "mybiz.com"}, {"domain": "other.com"}])],
                    "organic_mobile", ASSETS, COMP)[0]
    assert s["ownership_class"] == "influenced" and s["client_cited"] is True
    # competitor cited, client not -> competitor
    s2 = sf.classify([_item("ai_overview", references=[{"domain": "competitor.com"}])],
                     "organic_mobile", ASSETS, COMP)[0]
    assert s2["ownership_class"] == "competitor" and s2["cited_competitors"] == ["competitor.com"]
    # nobody we know cited -> unknown
    s3 = sf.classify([_item("ai_overview", references=[{"domain": "stranger.com"}])],
                     "organic_mobile", ASSETS, COMP)[0]
    assert s3["ownership_class"] == "unknown"


def test_ai_citation_counts_influenced_tier_assets():
    # an INFLUENCED-tier asset cited in an AI surface is AI presence -> influenced, not unknown
    # (regression: citation check previously only saw owned+controlled tiers)
    s = sf.classify([_item("ai_overview", references=[{"domain": "partnerblog.com"}])],
                    "organic_mobile", ASSETS, COMP)[0]
    assert s["ownership_class"] == "influenced" and s["client_cited"] is True


def test_aggregator_domain_classified_distinctly():
    # yelp/angi/etc. are structural directories, NOT true competitors -> own class
    s = sf.classify([_item("organic", domain="yelp.com", url="https://yelp.com/biz/someone")],
                    "local_finder", ASSETS, COMP, aggregators=["yelp.com", "angi.com"])[0]
    assert s["ownership_class"] == "aggregator"


def test_client_listing_inside_aggregator_stays_owned_tier():
    # the client's OWN listing inside an aggregator wins as controlled (asset tiers beat the agg list)
    assets = {"owned": [], "controlled": ["yelp.com/biz/mybiz"], "influenced": []}
    s = sf.classify([_item("local_pack", url="https://yelp.com/biz/mybiz")],
                    "local_finder", assets, COMP, aggregators=["yelp.com"])[0]
    assert s["ownership_class"] == "controlled"


def test_controlled_and_influenced_tiers():
    assert sf.classify([_item("organic", domain="mybiz.gbp")], "organic_mobile",
                       ASSETS, COMP)[0]["ownership_class"] == "controlled"
    assert sf.classify([_item("organic", domain="partnerblog.com")], "organic_mobile",
                       ASSETS, COMP)[0]["ownership_class"] == "influenced"


def test_owned_token_shadows_competitor_token():
    # a slot whose haystack contains BOTH an owned token AND a competitor token -> owned wins,
    # because assets are checked before competitors (tier order: owned > ... > competitor).
    assets = {"owned": ["mybiz.com"], "controlled": [], "influenced": []}
    s = sf.classify([_item("organic", url="https://mybiz.com/we-beat-competitor.com")],
                    "organic_mobile", assets, ["competitor.com"])[0]
    assert s["ownership_class"] == "owned"


def test_substring_match_is_fragile_PINNED():
    # PIN the README's known tuning point: matching is SUBSTRING, so the owned token
    # 'youtube.com/@houseac' wrongly matches '@houseac2'. This documents today's behavior so a
    # future exact-match fix is a deliberate, visible change (this assertion should flip then).
    assets = {"owned": ["youtube.com/@houseac"], "controlled": [], "influenced": []}
    s = sf.classify([_item("organic", url="https://youtube.com/@houseac2/videos")],
                    "organic_mobile", assets, [])[0]
    assert s["ownership_class"] == "owned"   # FRAGILE false-positive, pinned on purpose
