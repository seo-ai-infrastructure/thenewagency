"""Unit tests for ownership-weighted estate scoring (lib/estate_scoring) — the repo's headline
deliverable. Locks in the weight tables + the 'never blend lanes' rule. Pure logic; no network."""
from lib import estate_scoring as es


def _rec(own, kw="k", loc="L", os_="mobile", lead="high", qc="organic_mobile"):
    return {"ownership_class": own, "keyword": kw, "location_name": loc, "os": os_,
            "lead_value": lead, "query_class": qc}


def test_estate_share_is_ownership_weighted():
    recs = [_rec("owned"), _rec("controlled"), _rec("competitor"), _rec("unknown")]
    assert es.estate_share(recs) == 0.4625      # (1.0 + 0.85 + 0 + 0) / 4


def test_estate_share_empty_is_zero():
    assert es.estate_share([]) == 0.0


def test_score_lane_weights_each_query_by_lead_value():
    # high-value query fully owned (share 1.0); low-value query unowned (share 0.0)
    recs = [_rec("owned", kw="hi", lead="high"), _rec("competitor", kw="lo", lead="low")]
    out = es.score_lane(recs)
    assert out["lane_score"] == round(1.0 / 1.3, 4)   # (1.0*1.0 + 0.0*0.3) / (1.0 + 0.3)
    assert len(out["queries"]) == 2
    lo = [q for q in out["queries"] if q["keyword"] == "lo"][0]
    assert lo["competitor_slots"] == 1 and lo["estate_share"] == 0.0


def test_score_all_keeps_lanes_separate_no_blend():
    recs = [_rec("owned", qc="organic_mobile"), _rec("competitor", qc="local_finder")]
    out = es.score_all(recs)
    assert set(out) == {"organic_mobile", "local_finder"}
    assert out["organic_mobile"]["lane_score"] == 1.0
    assert out["local_finder"]["lane_score"] == 0.0


def test_estate_share_extremes():
    assert es.estate_share([_rec("owned"), _rec("owned")]) == 1.0          # all owned
    assert es.estate_share([_rec("competitor"), _rec("competitor")]) == 0.0  # all competitor


def test_estate_share_mixed_three_records():
    # [(owned),(unknown),(competitor)] -> (1.0 + 0 + 0) / 3
    assert es.estate_share([_rec("owned"), _rec("unknown"), _rec("competitor")]) == round(1.0 / 3, 4)


def test_score_lane_groups_by_keyword_location_os_not_query_class():
    # same keyword + location, DIFFERENT os -> two distinct groups (grouping key includes os)
    recs = [_rec("owned", os_="ios"), _rec("competitor", os_="android")]
    out = es.score_lane(recs)
    assert len(out["queries"]) == 2
    assert {q["os"] for q in out["queries"]} == {"ios", "android"}


def test_lead_value_invariant_within_group_is_honored():        # #13
    recs = [_rec("owned", lead="high"), _rec("competitor", lead="high")]   # one group (same kw/loc/os)
    out = es.score_lane(recs)
    assert len(out["queries"]) == 1 and out["queries"][0]["lead_value"] == "high"


def test_weights_are_env_overridable():                          # #14
    import os
    os.environ["ESTATE_W_INFLUENCED"] = "0.30"
    try:
        w = es._weights({"influenced": 0.45, "owned": 1.0}, "ESTATE_W_")
        assert w["influenced"] == 0.30 and w["owned"] == 1.0
    finally:
        del os.environ["ESTATE_W_INFLUENCED"]


def _slot(own, rank, lane="local_finder", kw="k", lead="high"):
    return {"ownership_class": own, "rank_absolute": rank, "query_class": lane,
            "keyword": kw, "location_name": "L", "os": "ios", "lead_value": lead}


def test_position_weight_curve():
    assert es.position_weight(1) == 1.0
    assert es.position_weight(5) == 0.3        # the anchors from the spec
    assert es.position_weight(11) == 0.05      # deep results barely count
    assert es.position_weight(None) == 0.0     # AI surfaces (no rank) don't contribute


def test_sov_is_position_and_lead_weighted_share():
    out = es.sov_score([_slot("owned", 1), _slot("competitor", 2)])["local_finder"]
    assert out["sov"] == round(1.0 / 1.6, 4)              # client pos1 / (pos1 + comp pos2)
    assert out["competitor_share"] == round(0.6 / 1.6, 4)


def test_sov_tracks_aggregator_share_separately():
    out = es.sov_score([_slot("owned", 1), _slot("aggregator", 3)])["local_finder"]
    assert out["aggregator_share"] == round(0.45 / 1.45, 4)   # real estate lost to directories, not rivals


def test_sov_never_blends_lanes():
    out = es.sov_score([_slot("owned", 1, lane="local_finder"),
                        _slot("competitor", 1, lane="organic_mobile")])
    assert set(out) == {"local_finder", "organic_mobile"}
    assert out["local_finder"]["sov"] == 1.0 and out["organic_mobile"]["sov"] == 0.0


def test_low_confidence_flag_and_sample_count():                 # #15
    small = es.score_lane([_rec("owned"), _rec("competitor", os_="android")])
    assert small["samples"] == 2 and small["low_confidence"] is True
    big = es.score_lane([_rec("owned", kw=f"k{i}") for i in range(es.MIN_CONFIDENT_SAMPLES + 1)])
    assert big["low_confidence"] is False
