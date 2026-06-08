from unittest.mock import patch, MagicMock
from integrations.cloudflare import client as cf


class _RL:
    def acquire(self): pass


def test_deploy_html_wraps_into_worker_and_puts():
    c = cf.CloudflareClient(_RL())
    resp = MagicMock(); resp.json.return_value = {"success": True, "result": {"id": "hvac-aio"}}
    with patch.object(cf.requests, "put", return_value=resp) as put:
        landed, res = c.deploy_html("ACC", "TOK", "hvac-aio", "<h1>AC Repair</h1>")
    assert landed is True
    args, kwargs = put.call_args
    assert "accounts/ACC/workers/scripts/hvac-aio" in args[0]
    assert kwargs["headers"]["Authorization"] == "Bearer TOK"
    body = kwargs["data"].decode()
    assert "<h1>AC Repair</h1>" in body and "addEventListener" in body   # html embedded in a worker


def test_deploy_reports_cf_success_false():
    c = cf.CloudflareClient(_RL())
    resp = MagicMock(); resp.json.return_value = {"success": False, "errors": [{"message": "bad token"}]}
    with patch.object(cf.requests, "put", return_value=resp):
        landed, res = c.deploy_worker("A", "T", "s", "js")
    assert landed is False and res["success"] is False


def test_fake_mode_no_network():
    c = cf.CloudflareClient(_RL(), fake=True)
    with patch.object(cf.requests, "put", side_effect=AssertionError("network in fake")):
        landed, res = c.deploy_html("A", "T", "s", "<p>x</p>")
    assert landed is True and res["result"]["_fake"] is True
