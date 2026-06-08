from unittest.mock import patch, MagicMock
from integrations.clarity.client import live_insights

def test_live_insights_indexes_by_metric():
    fake = [
        {"metricName": "Traffic", "information": [{"totalSessionCount": "200", "distinctUserCount": "150"}]},
        {"metricName": "RageClickCount", "information": [{"subTotal": "12"}]},
        {"metricName": "DeadClickCount", "information": [{"subTotal": "5"}]},
        {"metricName": "ScrollDepth", "information": [{"averageScrollDepth": 41.2}]},
    ]
    resp = MagicMock(status_code=200); resp.json.return_value = fake; resp.raise_for_status.return_value = None
    with patch("integrations.clarity.client.requests.get", return_value=resp) as g:
        m = live_insights(token="JWT", num_days=3)
    assert m["Traffic"]["totalSessionCount"] == "200"
    assert m["RageClickCount"]["subTotal"] == "12"
    assert g.call_args.kwargs["headers"]["Authorization"] == "Bearer JWT"
    assert g.call_args.kwargs["params"]["numOfDays"] == 3
