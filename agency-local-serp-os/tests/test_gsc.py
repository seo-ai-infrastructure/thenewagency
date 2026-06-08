from unittest.mock import patch, MagicMock
from integrations.gsc import client as gsc


def test_search_analytics_normalizes_rows():
    fake = {"rows": [
        {"keys": ["ac repair fort lauderdale", "https://houseacrepair.com/"],
         "clicks": 14, "impressions": 230, "ctr": 0.06, "position": 7.2},
    ]}
    resp = MagicMock(status_code=200); resp.json.return_value = fake; resp.raise_for_status.return_value = None
    with patch.object(gsc, "bearer_token", return_value="TOK"), \
         patch.object(gsc.requests, "post", return_value=resp) as p:
        rows = gsc.search_analytics("https://houseacrepair.com/", "2026-05-01", "2026-05-28")
    assert rows[0] == {"query": "ac repair fort lauderdale", "page": "https://houseacrepair.com/",
                       "clicks": 14, "impressions": 230, "ctr": 0.06, "position": 7.2}
    assert p.call_args.kwargs["headers"]["Authorization"] == "Bearer TOK"
