"""Google Search Console — Search Analytics API (read-only)."""
import urllib.parse, requests
from integrations.google_auth import bearer_token

SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def search_analytics(site_url, start_date, end_date, dimensions=("query", "page"), row_limit=250):
    tok = bearer_token([SCOPE])
    enc = urllib.parse.quote(site_url, safe="")
    r = requests.post(
        f"https://www.googleapis.com/webmasters/v3/sites/{enc}/searchAnalytics/query",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
        json={"startDate": start_date, "endDate": end_date,
              "dimensions": list(dimensions), "rowLimit": row_limit}, timeout=60)
    r.raise_for_status()
    out = []
    for row in (r.json().get("rows") or []):
        rec = dict(zip(dimensions, row.get("keys", [])))
        rec.update({"clicks": row.get("clicks"), "impressions": row.get("impressions"),
                    "ctr": row.get("ctr"), "position": row.get("position")})
        out.append(rec)
    return out
