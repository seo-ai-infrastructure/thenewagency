from unittest.mock import patch, MagicMock
from integrations.gbp_insights import client as gbp


def test_performance_normalizes_conversion_metrics():
    fake = {"metrics": {
        "CALL_CLICKS": {"total": 7, "values": []},
        "WEBSITE_CLICKS": {"total": 42, "values": []},
        "BUSINESS_DIRECTION_REQUESTS": {"total": 18},
        "BUSINESS_IMPRESSIONS_MOBILE_SEARCH": {"total": 1000},
        "BUSINESS_IMPRESSIONS_MOBILE_MAPS": {"total": 500},
    }}
    resp = MagicMock(status_code=200); resp.json.return_value = fake; resp.raise_for_status.return_value = None
    with patch.object(gbp.requests, "get", return_value=resp) as g:
        m = gbp.performance("ACCT", "2026-05-01", "2026-06-06", token="T")
    assert m["calls"] == 7 and m["website_clicks"] == 42 and m["direction_requests"] == 18
    assert m["impressions"] == 1500
    assert g.call_args.kwargs["params"]["accountId"] == "ACCT"
    assert g.call_args.kwargs["headers"]["Authorization"] == "Bearer T"
