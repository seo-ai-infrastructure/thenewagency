"""Tests that validate AEO audit documents against shared_schemas/aeo_audit.schema.json
via the lib.schema constant AEO_AUDIT. TDD: written before the constant exists."""
import jsonschema
import pytest
from lib import aeo_audit, aeo_evaluator, schema


ENT = {"service": ["ac repair"], "price": [r"\$\d"]}


def _build_doc():
    crawl = aeo_audit.audit(
        "# AC repair\n$99 service.",
        ENT,
        llms_txt_present=True,
        bots=[{"bot": "GPTBot", "accessible": True, "blocked_by_robots": False}],
    )
    ev = aeo_evaluator.evaluate(
        "# AC repair\n$99 service.",
        {"rival.com": "ac repair"},
        ENT,
    )
    return {
        "run_id": "aeo_test",
        "generated_at": "2026-06-07T00:00:00Z",
        "client": "c1",
        "crawlability": crawl,
        "evaluation": ev,
    }


def test_aeo_audit_doc_validates_against_schema():
    doc = _build_doc()
    schema.validate(doc, schema.AEO_AUDIT)  # must not raise


def test_aeo_audit_schema_rejects_missing_crawlability():
    with pytest.raises(jsonschema.ValidationError):
        schema.validate({"run_id": "x", "generated_at": "y", "client": "c1"}, schema.AEO_AUDIT)
