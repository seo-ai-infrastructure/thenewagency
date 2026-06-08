"""Unit tests for competitor review mining (lib/review_mining) — deterministic, no LLM.
Normalizes an Outscraper Google-reviews export, isolates negative (1-3 star) reviews, extracts
recurring complaint THEMES via a lexicon, and turns a competitor's dominant weakness into a
counter-positioning recommendation for the client. Public reviews only; no personal/employee data."""
from lib import review_mining as rm


ROWS = [
    {"name": "Air Magic", "place_id": "p1", "review_rating": 1, "review_datetime_utc": "12/19/2023",
     "review_text": "Hidden fees! The price went up, way more than quoted. $100 service call."},
    {"name": "Air Magic", "place_id": "p1", "review_rating": 1, "review_datetime_utc": "01/05/2024",
     "review_text": "They never showed up and didn't call back. Waited all day."},
    {"name": "Air Magic", "place_id": "p1", "review_rating": 5, "review_datetime_utc": "02/01/2024",
     "review_text": "Great service, very happy!"},
    {"name": "Air Anytime", "place_id": "p2", "review_rating": 2, "review_datetime_utc": "03/01/2024",
     "review_text": "Overpriced and the technician was rude and unprofessional."},
    {"name": "Air Anytime", "place_id": "p2", "review_rating": 1, "review_text": ""},   # empty -> skipped
]


def test_normalize_skips_empty_text():
    recs = rm.normalize_outscraper(ROWS)
    assert len(recs) == 4
    assert {r["business"] for r in recs} == {"Air Magic", "Air Anytime"}
    assert all(r["text"] for r in recs)


def test_negative_reviews_filters_1_to_3_star():
    neg = rm.negative_reviews(rm.normalize_outscraper(ROWS))
    assert len(neg) == 3 and all(r["rating"] <= 3 for r in neg)


def test_extract_themes_detects_complaint_categories():
    assert "hidden_fees" in rm.extract_themes("hidden fees, way more than quoted, surprise $100 service call")
    assert "no_show_late" in rm.extract_themes("they never showed up and waited all day")
    assert rm.extract_themes("great friendly service") == []


def test_competitor_pain_report_aggregates_dominant_themes():
    rep = rm.competitor_pain_report(rm.normalize_outscraper(ROWS))
    am = rep["Air Magic"]
    assert am["n_negative"] == 2
    assert "hidden_fees" in am["themes"] and "no_show_late" in am["themes"]
    aa = rep["Air Anytime"]
    assert "overpriced" in aa["themes"] and "rude_unprofessional" in aa["themes"]


def test_positioning_recs_counter_the_weakness():
    rep = rm.competitor_pain_report(rm.normalize_outscraper(ROWS))
    recs = rm.positioning_recs(rep, "c1", min_mentions=1)
    assert recs and all(r["area"] == "web" and r["kind"] == "review_counter_positioning" for r in recs)
    assert all(r["recommendation_id"].startswith("rec_") for r in recs)
    hidden = [r for r in recs if r["gap"]["theme"] == "hidden_fees"][0]
    assert "Air Magic" == hidden["gap"]["competitor"]
    assert hidden["gap"]["counter_hook"]                       # a concrete counter-positioning message
    assert hidden["gap"]["evidence"]                           # sample quote(s) from the reviews
