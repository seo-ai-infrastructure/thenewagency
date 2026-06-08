"""Unit tests for Nextdoor community-recommendation mining (lib/nextdoor_mining) — deterministic,
no LLM. Community threads are word-of-mouth: who neighbors recommend (Share of Recommendation) and
what attributes they demand (honest/affordable/family-owned). Negative competitor mentions + the
desired attributes both drive positioning recs. Sentence-level sentiment so one block can credit
the praised company and fault the criticized one separately."""
from lib import nextdoor_mining as nm

TEXT = """Amy C.
We just had our AC replaced with Air Magic. They are friendly, trustworthy, affordable, and did a great job! Highly recommend.

Bob S.
all year cooling sucks and they dont stand behind their product. Call Air Magic, they saved me.

Todd S.
Lindstrom - high costs for cheap AC units, installation was poorly executed. Steer clear.
"""
COMPANIES = ["Air Magic", "All Year Cooling", "Lindstrom"]


def test_share_of_recommendation_separates_praise_from_criticism():
    sor = nm.analyze(TEXT, COMPANIES)["share_of_recommendation"]
    assert sor["Air Magic"]["positive"] >= 2
    assert sor["All Year Cooling"]["negative"] >= 1
    assert sor["Lindstrom"]["negative"] >= 1


def test_desired_attributes_extracted():
    d = nm.analyze(TEXT, COMPANIES)["desired_attributes"]
    assert "affordable" in d and "trustworthy" in d


def test_recs_include_positioning_and_competitor_signal():
    a = nm.analyze(TEXT, COMPANIES)
    recs = nm.nextdoor_recs(a, "c1", min_attr=1)
    kinds = {r["kind"] for r in recs}
    assert "nextdoor_positioning" in kinds
    assert "nextdoor_competitor_signal" in kinds
    assert all(r["area"] == "web" and r["recommendation_id"].startswith("rec_") for r in recs)


def test_neutral_when_no_sentiment_words():
    s = nm.classify_sentiment("Air Magic")
    assert s == "neutral"
