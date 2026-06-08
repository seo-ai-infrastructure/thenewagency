"""Unit tests for the PAA Velocity Trap (lib/paa_velocity). Compares People-Also-Ask questions
across tracker runs to catch NEW questions and RISERS (a question climbing the PAA box), then emits
a PAA-hijack Q&A recommendation. Deterministic; pure logic."""
from lib import paa_velocity as pv


def _paa(kw, q, pos, ft="people_also_ask_element"):
    return {"feature_type": ft, "keyword": kw, "title": q, "rank_group": pos}


def test_paa_questions_extracts_titles_skips_empty():
    recs = [_paa("ac", "how much to fix ac", 1), {"feature_type": "people_also_ask", "keyword": "ac", "title": ""},
            {"feature_type": "organic", "keyword": "ac", "title": "not a PAA"}]
    qs = pv.paa_questions(recs)
    assert len(qs) == 1 and qs[0]["question"] == "how much to fix ac" and qs[0]["position"] == 1


def test_detect_velocity_finds_new_and_risers():
    runs = [
        ("r1", [_paa("ac", "how much to fix ac", 4), _paa("ac", "stable q", 3)]),
        ("r2", [_paa("ac", "how much to fix ac", 1), _paa("ac", "stable q", 3), _paa("ac", "brand new q", 2)]),
    ]
    events = pv.detect_velocity(runs)
    kinds = {(e["question"], e["kind"]) for e in events}
    assert ("brand new q", "new") in kinds
    assert ("how much to fix ac", "riser") in kinds
    assert all(e["question"] != "stable q" for e in events)          # unchanged -> no event
    riser = next(e for e in events if e["kind"] == "riser")
    assert riser["from_position"] == 4 and riser["to_position"] == 1


def test_detect_velocity_single_run_has_no_history():
    # one run = everything is technically "new"; with no prior window we still surface them as new
    events = pv.detect_velocity([("r1", [_paa("ac", "q1", 1)])])
    assert [e["kind"] for e in events] == ["new"]


def test_velocity_recs_emit_paa_hijack_with_qa_block():
    events = pv.detect_velocity([
        ("r1", [_paa("ac", "how much to fix ac", 4)]),
        ("r2", [_paa("ac", "how much to fix ac", 1)]),
    ])
    recs = pv.velocity_recs(events, "c1")
    assert len(recs) == 1
    r = recs[0]
    assert r["area"] == "web" and r["kind"] == "paa_hijack"
    assert r["recommendation_id"].startswith("rec_")
    assert "how much to fix ac" in r["content"]                      # the Q&A markdown block
