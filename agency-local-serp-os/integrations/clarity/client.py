"""Microsoft Clarity Data Export API (read-only). Auth = Bearer MICROSOFT_CLARITY_API_TOKEN.
Returns CRO behavior signals: sessions, scroll depth, rage/dead clicks, etc.
NOTE: Clarity allows numOfDays in 1..3 and ~10 requests/day per project."""
import os, requests

URL = "https://www.clarity.ms/export-data/api/v1/project-live-insights"


def live_insights(token=None, num_days=3):
    """-> {metricName: information[0]} dict (first info row per metric)."""
    token = token or os.environ["MICROSOFT_CLARITY_API_TOKEN"]
    r = requests.get(URL, headers={"Authorization": f"Bearer {token}"},
                     params={"numOfDays": num_days}, timeout=30)
    r.raise_for_status()
    out = {}
    for m in (r.json() or []):
        info = m.get("information") or [{}]
        out[m.get("metricName")] = info[0] if info else {}
    return out
