"""Unit tests for the Ghost-Asset Cannibalization Alarm (lib/cannibalization). Flags when a
'controlled'/'influenced' asset outranks the 'owned' core domain for a transactional query, and
emits a [De-optimization] work-order recommendation. Deterministic; pure logic."""
from lib import cannibalization as cz


def _slot(own, rank, kw="ac repair", lead="high", domain="x.com", qc="organic_mobile"):
    return {"ownership_class": own, "rank_absolute": rank, "keyword": kw, "lead_value": lead,
            "domain": domain, "feature_type": "organic", "location_name": "L", "os": "ios",
            "query_class": qc}


def test_flags_ghost_outranking_core_on_transactional():
    recs = [_slot("controlled", 1, domain="youtube.com/@biz"), _slot("owned", 4, domain="biz.com")]
    flags = cz.detect_cannibalization(recs)
    assert len(flags) == 1
    f = flags[0]
    assert f["ghost_rank"] == 1 and f["owned_rank"] == 4 and f["ghost_ownership"] == "controlled"


def test_not_flagged_when_core_outranks_ghost():
    recs = [_slot("owned", 1, domain="biz.com"), _slot("controlled", 3, domain="youtube.com/@biz")]
    assert cz.detect_cannibalization(recs) == []


def test_not_flagged_for_non_transactional_keyword():
    recs = [_slot("controlled", 1, lead="low"), _slot("owned", 4, lead="low")]
    assert cz.detect_cannibalization(recs) == []


def test_needs_both_owned_and_ghost_present():
    assert cz.detect_cannibalization([_slot("controlled", 1)]) == []     # no owned slot
    assert cz.detect_cannibalization([_slot("owned", 2)]) == []          # no ghost slot


def test_cannibalization_recs_are_deoptimization_work_orders():
    flags = cz.detect_cannibalization([_slot("influenced", 2, domain="medium.com/biz"),
                                       _slot("owned", 6, domain="biz.com")])
    recs = cz.cannibalization_recs(flags, "c1")
    assert len(recs) == 1
    r = recs[0]
    assert r["area"] == "web" and r["kind"] == "structural_cannibalization"
    assert r["recommendation_id"].startswith("rec_")
    assert "De-optimization" in r["suggested_action"]
