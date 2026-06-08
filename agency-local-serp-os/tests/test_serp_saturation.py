"""Unit tests for SERP saturation / multi-presence (lib/serp_saturation).
The strategic goal: occupy the SAME SERP 4-6+ times across ALL features. These tests pin
the presence count, the goal bands, and the unclaimed-feature opportunity list. Pure logic."""
from lib import serp_saturation as ss


def _slot(own, feature, kw="ac repair", loc="Fort Lauderdale, FL", os_="ios",
          qc="local_finder", lead="high"):
    return {"ownership_class": own, "feature_type": feature, "keyword": kw,
            "location_name": loc, "os": os_, "query_class": qc, "lead_value": lead}


def test_presence_counts_only_client_held_slots():
    recs = [_slot("owned", "organic"), _slot("controlled", "local_pack"),
            _slot("influenced", "ai_overview"), _slot("competitor", "organic"),
            _slot("unknown", "images")]
    s = ss.saturate_serp(recs)
    assert s["presence_count"] == 3        # owned + controlled + influenced (NOT competitor/unknown)
    assert s["features_held"] == ["ai_overview", "local_pack", "organic"]
    assert s["distinct_features_held"] == 3


def test_meets_goal_at_four_placements():
    recs = [_slot(o, f) for o, f in [("owned", "organic"), ("owned", "organic_video"),
            ("controlled", "local_pack"), ("influenced", "people_also_ask")]]
    s = ss.saturate_serp(recs)
    assert s["presence_count"] == 4
    assert s["meets_goal"] is True and s["goal_band"] == "in_band" and s["gap_to_goal"] == 0


def test_below_goal_lists_unclaimed_features_as_opportunity():
    recs = [_slot("owned", "organic"), _slot("competitor", "local_pack"),
            _slot("unknown", "images"), _slot("competitor", "ai_overview")]
    s = ss.saturate_serp(recs)
    assert s["presence_count"] == 1 and s["meets_goal"] is False and s["gap_to_goal"] == 3
    # features on the SERP the client does NOT hold -> the action list
    assert s["features_unclaimed"] == ["ai_overview", "images", "local_pack"]
    assert s["competitor_features"] == ["ai_overview", "local_pack"]
    assert s["total_features_on_serp"] == 4


def test_above_stretch_goal_band():
    recs = [_slot("owned", f"organic{i}") for i in range(7)]
    s = ss.saturate_serp(recs)
    assert s["presence_count"] == 7 and s["goal_band"] == "above"


def test_saturation_groups_by_serp_and_sorts_biggest_gap_first():
    recs = [_slot("owned", "organic", kw="good"), _slot("owned", "local_pack", kw="good"),
            _slot("owned", "images", kw="good"), _slot("owned", "ai_overview", kw="good"),
            _slot("competitor", "organic", kw="bad")]
    serps = ss.saturation(recs)
    assert [s["keyword"] for s in serps] == ["bad", "good"]   # biggest gap first = action queue
    assert serps[0]["gap_to_goal"] == 4 and serps[1]["meets_goal"] is True


def test_same_keyword_different_os_are_separate_serps():
    recs = [_slot("owned", "organic", os_="ios"), _slot("competitor", "organic", os_="android")]
    serps = ss.saturation(recs)
    assert len(serps) == 2 and {s["os"] for s in serps} == {"ios", "android"}


def test_summary_rolls_up_goal_attainment():
    recs = [*[_slot("owned", f"f{i}", kw="win") for i in range(4)],            # meets goal
            _slot("owned", "organic", kw="lose"), _slot("competitor", "local_pack", kw="lose")]
    out = ss.summary(recs)
    assert out["n_serps"] == 2 and out["n_meeting_goal"] == 1
    assert out["pct_meeting_goal"] == 0.5
    assert out["avg_presence"] == 2.5                          # (4 + 1) / 2
    assert [s["keyword"] for s in out["below_goal"]] == ["lose"]


def test_ai_overview_cited_twice_counts_as_two_appearances():
    # The takeover count reads the page as the operator does: an AI Overview that cites the client
    # twice + an organic listing = 3 appearances, even though it's only 2 distinct feature types.
    recs = [{"ownership_class": "influenced", "feature_type": "ai_overview", "client_citation_count": 2,
             "keyword": "ac coil repair cost", "location_name": "Fort Lauderdale, FL", "os": "android",
             "query_class": "organic_mobile", "lead_value": "high"},
            {"ownership_class": "owned", "feature_type": "organic", "url": "https://houseacrepair.com/",
             "keyword": "ac coil repair cost", "location_name": "Fort Lauderdale, FL", "os": "android",
             "query_class": "organic_mobile", "lead_value": "high"}]
    s = ss.saturate_serp(recs)
    assert s["presence_count"] == 3            # AIO(2 citations) + organic(1)
    assert s["distinct_features_held"] == 2     # but only 2 distinct surfaces


def test_same_listing_in_two_lanes_counts_once():
    # a local_pack returned by BOTH the local_finder and organic lanes is one placement, not two.
    recs = [{"ownership_class": "controlled", "feature_type": "local_pack", "url": "maps.google/cid=1",
             "keyword": "ac repair", "location_name": "FTL", "os": "ios", "query_class": ln, "lead_value": "high"}
            for ln in ("local_finder", "organic_mobile")]
    s = ss.saturate_serp(recs)
    assert s["presence_count"] == 1


def test_goal_is_env_overridable():
    import os
    os.environ["SATURATION_GOAL_MIN"] = "6"
    try:
        recs = [_slot("owned", f"f{i}") for i in range(5)]     # 5 placements, goal now 6
        s = ss.saturate_serp(recs)
        assert s["goal_min"] == 6 and s["meets_goal"] is False and s["gap_to_goal"] == 1
    finally:
        del os.environ["SATURATION_GOAL_MIN"]


def test_saturation_document_matches_schema():
    from lib import schema
    recs = ([_slot("owned", f"f{i}", kw="win") for i in range(4)]
            + [_slot("competitor", "organic", kw="lose")])
    doc = {"run_id": "sat_test", "generated_at": "2026-06-07T00:00:00Z", **ss.summary(recs)}
    schema.validate(doc, schema.SATURATION)        # written-doc shape must validate (no raise)


def test_saturation_schema_rejects_missing_fields():
    import jsonschema, pytest
    from lib import schema
    with pytest.raises(jsonschema.ValidationError):
        schema.validate({"run_id": "x"}, schema.SATURATION)
