#!/usr/bin/env python3
"""Pull date-dimensioned GSC daily clicks/impressions (up to ~16 months in one call) into
clients/<id>/signals/gsc_daily.json, which drives the Daily Performance Trends chart
(with algorithm-update markers + anomaly flags) on the Search Intelligence tab.

  python run.py [--client example-hvac-client] [--days 365]
"""
import sys, json, datetime, pathlib, yaml
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]; sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()
from integrations.gsc.client import search_analytics


def main():
    a = sys.argv
    client = a[a.index("--client") + 1] if "--client" in a else "example-hvac-client"
    days = int(a[a.index("--days") + 1]) if "--days" in a else 365
    sources = yaml.safe_load((ROOT / "clients" / client / "config" / "sources.yaml").read_text())
    site = (sources.get("gsc") or {}).get("site_url")
    if not site:
        sys.exit("no gsc.site_url configured for this client")
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)
    rows = search_analytics(site, start.isoformat(), end.isoformat(),
                            dimensions=("date",), row_limit=500)
    rows = sorted(rows, key=lambda r: r.get("date", ""))
    out = {"client": client, "site": site,
           "pulled": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "days": [{"date": r.get("date"), "clicks": r.get("clicks"),
                     "impressions": r.get("impressions"), "ctr": r.get("ctr"),
                     "position": r.get("position")} for r in rows]}
    p = ROOT / "clients" / client / "signals" / "gsc_daily.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2))
    print(f"[gsc-daily] {client}: {len(out['days'])} days {start}..{end} "
          f"-> clients/{client}/signals/gsc_daily.json")


if __name__ == "__main__":
    main()
