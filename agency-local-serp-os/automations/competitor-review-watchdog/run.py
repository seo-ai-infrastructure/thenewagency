#!/usr/bin/env python3
"""Competitor Review Watchdog — mines competitor Google reviews (an Outscraper export) into
counter-positioning recommendations for the client. Deterministic, no LLM, PUBLIC reviews only
(no employee/personal data, no outreach).

Filters negative (1-3 star) reviews, extracts recurring complaint themes (lib/review_mining), and
for each dominant competitor weakness writes a human-gated rec_*.json (web/wordpress) proposing the
client's counter-signal (e.g. competitor hammered for 'hidden fees' -> "transparent pricing"). Also
archives the raw reviews per competitor and writes a run history doc.

  python automations/competitor-review-watchdog/run.py --input <outscraper.json> [--client <id>] [--min-mentions N]
"""
import sys, json, datetime, pathlib


def _root(start):
    for d in [start, *start.parents]:
        if (d / "lib" / "review_mining.py").exists():
            return d
    raise RuntimeError("repo root not found")


HERE = pathlib.Path(__file__).resolve().parent
ROOT = _root(HERE); sys.path.insert(0, str(ROOT))
from lib import review_mining as rm
from lib import aeo_recs


def _arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv) else default


def main():
    inp = _arg("--input")
    if not inp:
        sys.exit("usage: run.py --input <outscraper.json> [--client <id>] [--min-mentions N]")
    client = _arg("--client", "example-hvac-client")
    min_mentions = int(_arg("--min-mentions", "2"))

    raw = json.loads(pathlib.Path(inp).read_text(encoding="utf-8"))
    rows = raw.get("data") if isinstance(raw, dict) else raw
    if isinstance(rows, dict):
        rows = next(iter(rows.values()))

    reviews = rm.normalize_outscraper(rows)
    report = rm.competitor_pain_report(reviews)
    rm.archive_raw(ROOT, client, report, rows)
    recs = rm.positioning_recs(report, client, min_mentions=min_mentions)
    aeo_recs.write_recs(ROOT, recs)

    now = datetime.datetime.now(datetime.timezone.utc)
    run_id = "reviews_" + now.strftime("%Y%m%dT%H%M%SZ")
    doc = {"run_id": run_id, "generated_at": now.isoformat(), "client": client,
           "n_reviews": len(reviews), "n_negative": len(rm.negative_reviews(reviews)),
           "competitors": report, "n_recs": len(recs)}
    hist = HERE / "history"; hist.mkdir(exist_ok=True)
    (hist / f"{run_id}.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")

    print(f"[reviews] {len(reviews)} reviews, {doc['n_negative']} negative across "
          f"{len(report)} competitors -> {len(recs)} counter-positioning rec(s)")
    for biz, e in report.items():
        top = ", ".join(f"{t}({e['themes'][t]})" for t in e["top_themes"][:4]) or "—"
        print(f"    {biz[:34]:<34} {e['n_negative']} neg · avg {e['avg_rating']} · {top}")


if __name__ == "__main__":
    main()
