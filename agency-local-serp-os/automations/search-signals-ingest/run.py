#!/usr/bin/env python3
"""Pull every configured search-data source for a client+date into one Signals snapshot.
Each source is optional: a missing key/config (or a permission 403) is skipped (logged), not fatal.
GBP insights use the Zernio Performance API (CALL_CLICKS etc.), which 403s until the GBP location
is verified + matched to its Maps place — handled gracefully.

  python scripts/ingest_signals.py --client example-hvac-client [--date YYYY-MM-DD]"""
import sys, datetime, pathlib, yaml
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]; sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()
from lib.signals import build_snapshot, write_snapshot
from integrations.bing_webmaster.client import query_stats as bing_query_stats
from integrations.clarity.client import live_insights as clarity_live_insights
from integrations.gsc.client import search_analytics as gsc_search_analytics
from integrations.ga4.client import run_report as ga4_run_report
from integrations.gbp_insights.client import performance as gbp_performance


def _safe(label, fn, default):
    try:
        return fn()
    except Exception as e:
        print(f"  [skip] {label}: {type(e).__name__}: {e}")
        return default


def ingest(client, date, sources, root=None):
    root = root or str(ROOT)
    start = (datetime.date.fromisoformat(date) - datetime.timedelta(days=28)).isoformat()
    gsc = bing = gbp = ga4 = clarity = None
    if sources.get("gsc", {}).get("site_url"):
        gsc = _safe("gsc", lambda: gsc_search_analytics(sources["gsc"]["site_url"], start, date), [])
    if sources.get("bing", {}).get("site_url"):
        bing = _safe("bing", lambda: bing_query_stats(sources["bing"]["site_url"]), [])
    if sources.get("gbp_insights", {}).get("zernio_account_id"):
        gbp = _safe("gbp", lambda: gbp_performance(sources["gbp_insights"]["zernio_account_id"], start, date), {})
    if str(sources.get("ga4", {}).get("property_id", "")).isdigit():
        ga4 = _safe("ga4", lambda: ga4_run_report(sources["ga4"]["property_id"], start, date,
                    ["sessionDefaultChannelGroup"], ["sessions", "conversions"]), [])
    if sources.get("clarity", {}).get("enabled"):
        clarity = _safe("clarity", lambda: clarity_live_insights(), {})
    snap = build_snapshot(client, date, gsc=gsc, bing=bing, gbp=gbp, ga4=ga4, clarity=clarity)
    write_snapshot(root, snap)
    return snap


def main():
    a = sys.argv
    client = a[a.index("--client") + 1] if "--client" in a else "example-hvac-client"
    date = a[a.index("--date") + 1] if "--date" in a else datetime.date.today().isoformat()
    sources = yaml.safe_load((ROOT / "clients" / client / "config" / "sources.yaml").read_text())
    snap = ingest(client, date, sources)
    d = snap["derived"]
    print(f"[signals] {client} {date}: gbp_calls={d['gbp_calls']} organic_conversions={d['organic_conversions']} "
          f"rage_clicks={d['cro_flags']['rage_clicks']} -> clients/{client}/signals/{date}.json")


if __name__ == "__main__":
    main()
