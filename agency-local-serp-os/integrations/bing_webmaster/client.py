"""Bing Webmaster Tools API (read-only). Auth = apikey query param (BING_WEBMASTER_API_KEY)."""
import os, requests

BASE = "https://ssl.bing.com/webmaster/api.svc/json"


def query_stats(site_url, api_key=None):
    """GetQueryStats -> normalized rows [{query, impressions, clicks, avg_impression_position, avg_click_position}]."""
    api_key = api_key or os.environ["BING_WEBMASTER_API_KEY"]
    r = requests.get(f"{BASE}/GetQueryStats",
                     params={"apikey": api_key, "siteUrl": site_url}, timeout=30)
    r.raise_for_status()
    out = []
    for d in (r.json().get("d") or []):
        out.append({
            "query": d.get("Query"),
            "impressions": d.get("Impressions"),
            "clicks": d.get("Clicks"),
            "avg_impression_position": d.get("AvgImpressionPosition"),
            "avg_click_position": d.get("AvgClickPosition"),
        })
    return out
