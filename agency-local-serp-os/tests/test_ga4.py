from unittest.mock import patch, MagicMock
from integrations.ga4 import client as ga4


def test_run_report_normalizes_conversions():
    fake = {"rows": [
        {"dimensionValues": [{"value": "google / organic"}],
         "metricValues": [{"value": "320"}, {"value": "11"}]},
    ], "rowCount": 1}
    resp = MagicMock(status_code=200); resp.json.return_value = fake; resp.raise_for_status.return_value = None
    with patch.object(ga4, "bearer_token", return_value="TOK"), \
         patch.object(ga4.requests, "post", return_value=resp) as p:
        rows = ga4.run_report("123456", "2026-05-01", "2026-05-28",
                              dimensions=["sessionDefaultChannelGroup"],
                              metrics=["sessions", "conversions"])
    assert rows[0] == {"sessionDefaultChannelGroup": "google / organic",
                       "sessions": "320", "conversions": "11"}
    assert "properties/123456:runReport" in p.call_args.args[0]
