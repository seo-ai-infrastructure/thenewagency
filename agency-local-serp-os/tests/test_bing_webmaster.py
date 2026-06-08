from unittest.mock import patch, MagicMock
from integrations.bing_webmaster.client import query_stats

def test_query_stats_parses_rows():
    fake = {"d": [
        {"Query": "ac repair fort lauderdale", "Impressions": 120, "Clicks": 9,
         "AvgImpressionPosition": 18, "AvgClickPosition": 6},
        {"Query": "ac tune up", "Impressions": 60, "Clicks": 2,
         "AvgImpressionPosition": 25, "AvgClickPosition": 11},
    ]}
    resp = MagicMock(status_code=200); resp.json.return_value = fake; resp.raise_for_status.return_value = None
    with patch("integrations.bing_webmaster.client.requests.get", return_value=resp) as g:
        rows = query_stats("https://houseacrepair.com/", api_key="K")
    assert rows[0] == {"query": "ac repair fort lauderdale", "impressions": 120,
                       "clicks": 9, "avg_impression_position": 18, "avg_click_position": 6}
    assert len(rows) == 2
    assert g.call_args.kwargs["params"]["apikey"] == "K"
    assert g.call_args.kwargs["params"]["siteUrl"] == "https://houseacrepair.com/"
