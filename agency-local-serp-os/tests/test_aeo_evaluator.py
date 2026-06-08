"""Unit tests for the AEO evaluator (lib/aeo_evaluator) — deterministic, NO local model.
Pits the client's crawled Markdown against competitors' on explicit entity coverage, yielding a
win-rate, the client's missing entities, and the per-entity conquest list (entities a competitor
states that the client does not). Pure logic; the crawl is injected upstream."""
from lib import aeo_evaluator

ENTITIES = {"service": ["ac repair", "hvac"], "price": [r"\$\d", "pricing"],
            "hours": ["24/7", "open 24"], "guarantee": ["guarantee", "warranty"]}


def test_client_losing_lists_missing_and_conquest():
    client_md = "AC repair with transparent pricing."                     # has service + price
    comps = {"rival.com": "24/7 AC repair, $99, satisfaction guarantee."}  # has all four
    ev = aeo_evaluator.evaluate(client_md, comps, ENTITIES)
    assert ev["client_coverage"] == round(2 / 4, 4)
    assert set(ev["missing_entities"]) == {"hours", "guarantee"}
    assert ev["win_rate"] == 0.0                                          # 0.5 < 1.0 -> loses
    assert ev["entity_conquest"]["hours"] == ["rival.com"]
    assert ev["entity_conquest"]["guarantee"] == ["rival.com"]


def test_client_winning_has_no_conquest():
    client_md = "24/7 AC repair, $99, lifetime warranty, transparent pricing."
    comps = {"rival.com": "AC repair only."}
    ev = aeo_evaluator.evaluate(client_md, comps, ENTITIES)
    assert ev["win_rate"] == 1.0 and ev["entity_conquest"] == {}
    assert ev["missing_entities"] == []


def test_win_rate_is_fraction_of_competitors_beaten_or_tied():
    client_md = "AC repair, $99."                                         # coverage 0.5
    comps = {"a.com": "AC repair.",                                       # 0.25 -> client wins
             "b.com": "24/7 AC repair, $1, lifetime warranty."}          # 0.75 -> client loses
    ev = aeo_evaluator.evaluate(client_md, comps, ENTITIES)
    assert ev["win_rate"] == 0.5


def test_no_competitors_is_graceful():
    ev = aeo_evaluator.evaluate("AC repair $99", {}, ENTITIES)
    assert ev["win_rate"] is None and ev["competitors"] == {}
