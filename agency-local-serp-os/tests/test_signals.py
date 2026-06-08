from lib.signals import build_snapshot


def test_build_snapshot_merges_and_derives():
    snap = build_snapshot(
        client="example-hvac-client", date="2026-06-06",
        gsc=[{"query": "ac repair fort lauderdale", "page": "/", "clicks": 14,
              "impressions": 230, "ctr": 0.06, "position": 7.2}],
        bing=[{"query": "ac repair", "impressions": 50, "clicks": 2,
               "avg_impression_position": 20, "avg_click_position": 8}],
        gbp={"calls": 42, "direction_requests": 18, "website_clicks": 30, "views": 1200},
        ga4=[{"sessionDefaultChannelGroup": "Organic Search", "sessions": "320", "conversions": "11"}],
        clarity={"RageClickCount": {"subTotal": "12"}, "DeadClickCount": {"subTotal": "5"}},
    )
    assert snap["client"] == "example-hvac-client" and snap["date"] == "2026-06-06"
    assert snap["search"]["gsc"][0]["clicks"] == 14
    assert snap["local"]["gbp"]["calls"] == 42
    assert snap["derived"]["gbp_calls"] == 42
    assert snap["derived"]["organic_conversions"] == 11
    assert snap["derived"]["cro_flags"]["rage_clicks"] == 12
