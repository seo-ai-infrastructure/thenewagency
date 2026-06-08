#!/usr/bin/env python3
"""Weekly GBP post batch — generate N (default 5) Google Business Profile posts (text + CTA link)
for the upcoming week, ONE per posting day, themed across the client's content clusters. Each post
becomes a hashed, scoped, expiring APPROVED artifact (period = its post date) so the daily poster
can publish it, and the batch is written to a reviewable calendar.

  python scripts/gen_gbp_posts.py --client example-hvac-client [--count 5] [--start YYYY-MM-DD]
      [--site https://houseacrepair.com] [--review]

--review emits PENDING drafts (for board sign-off) instead of approved artifacts.
Needs ANTHROPIC_API_KEY. Posts are built from the strategy clusters + facts (no fabricated NAP).
"""
import sys, os, re, json, datetime, pathlib, yaml
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()
from lib import approvals
import requests

try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # emoji-safe console on Windows
except Exception: pass

ANGLES = [
    "a seasonal South-Florida AC tip", "a 24/7 emergency-service highlight",
    "a common AC problem + how you fix it", "a money-saving maintenance reminder",
    "a nearby service-area spotlight", "a transparent-pricing / honest-diagnosis note",
    "a why-choose-us trust note (licensed, fast, local)",
]


def _claude(prompt, max_tokens=400):
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
    r = requests.post("https://api.anthropic.com/v1/messages",
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}, timeout=120)
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text").strip()


def gen_one(args):
    i, cluster, site = args
    angle = ANGLES[i % len(ANGLES)]
    prompt = (
        'Write ONE Google Business Profile post for "House AC Repair", a residential HVAC / AC repair '
        'company serving Fort Lauderdale & Broward County, FL. '
        f'Angle: {angle}. Content theme: {cluster["cluster"]}. '
        'Rules: 350-650 characters, warm and local, ONE clear soft call-to-action at the end, '
        'NO fabricated phone numbers / prices / guarantees / awards, no markdown, plain text, at most '
        '1-2 emoji. Return ONLY the post text.')
    text = _claude(prompt)[:1490]
    return {"cluster": cluster["cluster"], "angle": angle, "text": text,
            "cta": ({"type": "LEARN_MORE", "url": site} if site else None)}   # Zernio GBP CTA = {type, url}


def main():
    def arg(n, d): return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
    client = arg("--client", "example-hvac-client")
    count = int(arg("--count", "5"))
    site = arg("--site", "https://houseacrepair.com")
    review = "--review" in sys.argv
    start = arg("--start", None)
    start_date = datetime.date.fromisoformat(start) if start else datetime.date.today() + datetime.timedelta(days=1)

    gb = yaml.safe_load((ROOT / "clients" / client / "rpa" / "google_business.yaml").read_text())
    location_id = str(gb["default_location_id"]); scope = location_id.replace("/", "_")
    clusters = json.loads((ROOT / "clients" / client / "strategy" / "keyword-clusters.json").read_text())["clusters"]
    picks = [clusters[i % len(clusters)] for i in range(count)]
    posts = list(ThreadPoolExecutor(max_workers=5).map(gen_one, [(i, picks[i], site) for i in range(count)]))

    cal = []
    for i, p in enumerate(posts):
        d = (start_date + datetime.timedelta(days=i)).isoformat()
        content = {"text": p["text"], **({"cta": p["cta"]} if p["cta"] else {})}
        if review:
            base = ROOT / "clients" / client / "rpa" / "approvals" / "pending"; base.mkdir(parents=True, exist_ok=True)
            f = base / f"{scope}__gbp_post_publish__{d}__draft.json"
            f.write_text(json.dumps({"scope_id": scope, "workflow_id": "gbp_post_publish", "kind": "gbp_post",
                "period": d,    # the board reads this so approve targets the right post date (not the ISO week)
                "created": datetime.datetime.now(datetime.timezone.utc).isoformat(), "status": "pending_human_review",
                "content": content, "provenance": {"cluster": p["cluster"], "angle": p["angle"]}}, indent=2))
            ref = f.name
        else:
            out, h = approvals.write_approval(str(ROOT), client, "rpa", scope, "gbp_post_publish", d,
                content, provenance={"source": "gen_gbp_posts", "cluster": p["cluster"], "angle": p["angle"]})
            ref = out.name
        cal.append({"date": d, "cluster": p["cluster"], "angle": p["angle"], "text": p["text"], "cta": p["cta"], "artifact": ref})
        print(f"  {d}  [{p['cluster'][:22]:22}] {p['text'][:58]}...")

    wk = start_date.isocalendar(); week = f"{wk[0]}-W{wk[1]:02d}"
    caldir = ROOT / "clients" / client / "content" / "gbp_calendar"; caldir.mkdir(parents=True, exist_ok=True)
    (caldir / f"{week}.json").write_text(json.dumps(
        {"client": client, "week": week, "location_id": location_id, "site": site,
         "mode": "review-pending" if review else "approved", "posts": cal}, indent=2))
    print(f"[gen_gbp_posts] {len(cal)} posts ({'PENDING review' if review else 'APPROVED'}) "
          f"-> clients/{client}/content/gbp_calendar/{week}.json")
    print(f"  daily drip: python scripts/post_daily_gbp.py --client {client}   (1/day, idempotent)")


if __name__ == "__main__":
    main()
