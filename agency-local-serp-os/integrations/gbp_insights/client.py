"""GBP insights via the Zernio Performance API (location-level; per-post insights were deprecated
by Google). Returns the conversion signals the agency optimizes for: CALL CLICKS, website clicks,
direction requests, impressions. Auth = Bearer ZERNIO_API_KEY.

NOTE: Google returns 403 PERMISSION_DENIED until the connected GBP location is verified AND matched
to its Maps place (hasVoiceOfMerchant=true). The ingestion runner skips this source gracefully
until then. Data may also lag 2-3 days; up to 18 months of history is available."""
import os, requests

BASE = "https://zernio.com/api/v1"
_IMPRESSION_KEYS = ("BUSINESS_IMPRESSIONS_DESKTOP_MAPS", "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
                    "BUSINESS_IMPRESSIONS_MOBILE_MAPS", "BUSINESS_IMPRESSIONS_MOBILE_SEARCH")


def performance(account_id, start_date, end_date, token=None):
    """GET /analytics/googlebusiness/performance -> {calls, website_clicks, direction_requests,
    conversations, bookings, impressions, raw}."""
    token = token or os.environ["ZERNIO_API_KEY"]
    r = requests.get(f"{BASE}/analytics/googlebusiness/performance",
                     headers={"Authorization": f"Bearer {token}"},
                     params={"accountId": account_id, "startDate": start_date, "endDate": end_date},
                     timeout=30)
    r.raise_for_status()
    j = r.json()
    m = j.get("metrics") or (j.get("data") or {}).get("metrics") or {}

    def total(k):
        return (m.get(k) or {}).get("total")

    imp = sum(t for t in (total(k) for k in _IMPRESSION_KEYS) if isinstance(t, (int, float)))
    return {
        "calls": total("CALL_CLICKS"),
        "website_clicks": total("WEBSITE_CLICKS"),
        "direction_requests": total("BUSINESS_DIRECTION_REQUESTS"),
        "conversations": total("BUSINESS_CONVERSATIONS"),
        "bookings": total("BUSINESS_BOOKINGS"),
        "impressions": imp or None,
        "raw": m,
    }
