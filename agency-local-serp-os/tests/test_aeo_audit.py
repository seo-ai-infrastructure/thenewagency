"""Unit tests for the deterministic crawlability/AEO analysis (lib/aeo_audit) — Markdown purity,
entity clarity, and the assembled audit doc. No network; the crawl/fetch is injected upstream."""
from lib import aeo_audit


def test_markdown_purity_penalizes_boilerplate():
    md = ("# AC Repair in Fort Lauderdale\n"
          "We fix air conditioners fast with transparent pricing and a satisfaction guarantee.\n"
          "[Home](/)\n[Menu](/menu)\n"
          "Privacy Policy\n© 2026 All rights reserved\n")
    p = aeo_audit.markdown_purity(md)
    assert 0.0 < p["purity"] < 1.0
    assert p["boilerplate_lines"] >= 3 and p["content_lines"] >= 2


def test_entity_clarity_flags_missing_entities():
    md = "Emergency AC repair. Call now. Service from $150 dispatch."
    entities = {"price": [r"\$\d", "pricing"], "hours": ["24/7", "open 24"], "service": ["ac repair", "hvac"]}
    e = aeo_audit.entity_clarity(md, entities)
    assert e["entities"]["price"] is True and e["entities"]["service"] is True
    assert e["entities"]["hours"] is False
    assert e["missing"] == ["hours"] and e["clarity"] == round(2 / 3, 4)


def test_audit_assembles_full_report():
    rep = aeo_audit.audit("# Title\nGreat content here about AC repair.", {"service": ["ac repair"]},
                          llms_txt_present=True,
                          bots=[{"bot": "GPTBot", "accessible": True, "blocked_by_robots": False}])
    assert rep["llms_txt_present"] is True
    assert rep["entity_clarity"]["entities"]["service"] is True
    assert rep["markdown_purity"]["purity"] > 0
    assert rep["bots"][0]["bot"] == "GPTBot"


def test_empty_markdown_is_graceful():
    p = aeo_audit.markdown_purity("")
    assert p["purity"] in (0.0, 1.0) and p["content_lines"] == 0
    e = aeo_audit.entity_clarity("", {"x": ["y"]})
    assert e["found"] == 0 and e["missing"] == ["x"]
