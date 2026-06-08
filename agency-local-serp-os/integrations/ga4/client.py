"""Google Analytics 4 — Data API runReport (read-only). Track conversions/calls by channel/page."""
import requests
from integrations.google_auth import bearer_token

SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


def run_report(property_id, start_date, end_date, dimensions, metrics):
    tok = bearer_token([SCOPE])
    r = requests.post(
        f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
        json={"dateRanges": [{"startDate": start_date, "endDate": end_date}],
              "dimensions": [{"name": d} for d in dimensions],
              "metrics": [{"name": m} for m in metrics]}, timeout=60)
    r.raise_for_status()
    out = []
    for row in (r.json().get("rows") or []):
        rec = {d: dv.get("value") for d, dv in zip(dimensions, row.get("dimensionValues", []))}
        rec.update({m: mv.get("value") for m, mv in zip(metrics, row.get("metricValues", []))})
        out.append(rec)
    return out
