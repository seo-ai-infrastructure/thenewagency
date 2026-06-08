#!/usr/bin/env python3
"""Perfect content template generator (SERP-driven).

For a keyword, pull the real top-ranking organic pages (DataForSEO), drop directories/aggregators,
fetch each competitor page, use an LLM to extract the content SUBTOPICS each covers, then synthesize
ONE "perfect" content template = the full union of subtopics + the unique differentiators only a few
rank-holders cover + at least one genuinely NEW highly-relevant subtopic none of them cover.

Output: a markdown outline + structured JSON saved under clients/<id>/content/.

  python scripts/content_template.py "ac repair fort lauderdale" \
      --client example-hvac-client --location "Fort Lauderdale,Florida,United States" [--max 15]

Needs DATAFORSEO_LOGIN/PASSWORD (SERP) and ANTHROPIC_API_KEY (LLM) in .env.
"""
import sys, os, re, json, html, base64, datetime, pathlib
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()
import requests

DIRECTORY_DOMAINS = (
    "yelp.", "yellowpages.", "angi.", "angieslist.", "thumbtack.", "bbb.org", "mapquest.",
    "nextdoor.", "reddit.", "facebook.", "houzz.", "porch.", "homeadvisor.", "homeguide.",
    "expertise.com", "threebestrated.", "birdeye.", "manta.", "chamberofcommerce.", "justdial.",
    "superpages.", "citysearch.", "foursquare.", "trustpilot.", "indeed.", "glassdoor.",
    "yellowbook.", "local.com", "ezlocal.", "cylex", "hotfrog", "brownbook", "wikipedia.",
    "youtube.", "pinterest.", "tiktok.", "instagram.",
)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


# ---------- SERP source: tracker history (preferred) ----------
def urls_from_history(keyword, max_n, include_owned=False):
    """Ranking organic URLs already captured by the SERP estate tracker (no re-fetch / no cost).
    Skips the client's own 'owned' pages by default (we analyze competitors) + directories."""
    import glob
    files = sorted(glob.glob(str(ROOT / "automations" / "local-mobile-serp-feature-tracker" / "history" / "*.jsonl")))
    if not files:
        return []
    recs = [json.loads(l) for l in open(files[-1], encoding="utf-8") if l.strip()]
    kw = keyword.lower()
    cand = [r for r in recs if r.get("query_class") == "organic_mobile" and r.get("url")
            and (kw in (r.get("keyword") or "").lower() or (r.get("keyword") or "").lower() in kw)]
    cand.sort(key=lambda r: r.get("rank_absolute") or 999)
    seen, out = set(), []
    for r in cand:
        dom = (r.get("domain") or "").lower()
        if (not include_owned and r.get("ownership_class") == "owned") or not dom or dom in seen \
           or any(d in dom for d in DIRECTORY_DOMAINS):
            continue
        seen.add(dom)
        out.append({"rank": r.get("rank_absolute"), "url": r["url"], "domain": dom})
        if len(out) >= max_n:
            break
    return out


# ---------- SERP source: live DataForSEO (fallback) ----------
def top_ranking_urls(keyword, location, max_n):
    from integrations.dataforseo import client as dfs
    endpoint = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    task = {"keyword": keyword, "location_name": location, "language_code": "en",
            "device": "desktop", "depth": 40}
    items = dfs.call(endpoint, task)
    seen, out = set(), []
    for it in items:
        if it.get("type") != "organic":
            continue
        url, dom = it.get("url") or "", (it.get("domain") or "").lower()
        if not url or dom in seen or any(d in dom for d in DIRECTORY_DOMAINS):
            continue
        seen.add(dom)
        out.append({"rank": it.get("rank_group"), "url": url, "domain": dom})
        if len(out) >= max_n:
            break
    return out


# ---------- fetch + extract ----------
def fetch_page(url):
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        if r.status_code != 200 or not r.text:
            return None
        doc = r.text
        heads = [html.unescape(re.sub(r"<[^>]+>", " ", x)).strip()
                 for x in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", doc, re.I | re.S)]
        heads = [h for h in heads if h][:60]
        mt = re.search(r"<title[^>]*>(.*?)</title>", doc, re.I | re.S)
        title = html.unescape(re.sub(r"<[^>]+>", " ", mt.group(1))).strip() if mt else ""
        body = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", doc, flags=re.I | re.S)
        body = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body))).strip()[:5000]
        return {"url": url, "title": title, "headings": heads, "body": body}
    except Exception:
        return None


def _claude(prompt, max_tokens=1500):
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
    r = requests.post("https://api.anthropic.com/v1/messages",
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}, timeout=120)
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")


def _parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        return json.loads(m.group(1)) if m else None


def subtopics_for(page, keyword):
    prompt = (f'Analyze this web page as content targeting the keyword "{keyword}" '
              f'(home / residential HVAC AC repair service).\n'
              f'TITLE: {page["title"]}\nHEADINGS: {page["headings"]}\n'
              f'BODY (excerpt): {page["body"][:3500]}\n\n'
              'Return ONLY a JSON array of the distinct content SUBTOPICS this page covers, as short '
              'canonical labels, e.g. ["Emergency / 24-7 service","Financing options","Brands serviced",'
              '"Service area / cities","Warranties & guarantees","Common AC problems"]. No prose, JSON only. '
              'If this is an automotive (car) AC page, return [].')
    return _parse_json(_claude(prompt, max_tokens=500)) or []


def synthesize(keyword, target, corpus, n):
    prompt = (f'You are an elite local-SEO content strategist. Subtopics covered by {n} of the top-RANKING '
              f'pages for "{keyword}", per page:\n\n{json.dumps(corpus, indent=1)}\n\n'
              f'Build the PERFECT content template for a page targeting "{keyword}" for {target}.\n'
              '1. Semantically MERGE equivalent subtopics into canonical sections; coverage = how many of '
              f'the {n} pages cover each.\n'
              '2. Include EVERY distinct subtopic (full union) — miss nothing.\n'
              '3. Classify: "core" (most pages, table stakes) vs "unique" (only 1-2 pages, a differentiator).\n'
              '4. Propose AT LEAST 1-2 genuinely NEW, highly-relevant subtopics NO page covers but that would '
              'help this page win (real gaps) — classification "new".\n'
              '5. Order into a logical H2/H3 outline for a high-converting local service page.\n'
              '6. One line of guidance per section.\n\n'
              'Return ONLY JSON: {"page_title":str, "sections":[{"heading":str,"level":"H2|H3",'
              '"classification":"core|unique|new","coverage":int,"guidance":str}], '
              '"new_subtopics":[{"label":str,"rationale":str}], "markdown":str}. '
              'In "markdown" use ## / ### with a one-line note under each heading and tag '
              f'[CORE]/[UNIQUE]/[NEW] + coverage like (7/{n}).')
    return _parse_json(_claude(prompt, max_tokens=4000))


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        raise SystemExit('usage: python scripts/content_template.py "<keyword>" [--client id] '
                         '[--location "City,State,United States"] [--max 15]')
    keyword = sys.argv[1]
    def arg(n, d): return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
    client = arg("--client", "example-hvac-client")
    location = arg("--location", "Fort Lauderdale,Florida,United States")
    max_n = int(arg("--max", "15"))
    target = arg("--target", f"a residential HVAC / AC repair company ({client})")

    print(f"[content-template] '{keyword}' @ {location} ...")
    ranked = [] if "--live" in sys.argv else urls_from_history(keyword, max_n)
    if ranked:
        print(f"  {len(ranked)} ranking pages from SERP-takeover history (no re-fetch)")
    else:
        print("  no history match -> live DataForSEO SERP")
        ranked = top_ranking_urls(keyword, location, max_n)
        print(f"  {len(ranked)} non-directory ranking pages")
    pages = [p for p in ThreadPoolExecutor(max_workers=8).map(fetch_page, [r["url"] for r in ranked]) if p]
    print(f"  fetched {len(pages)}/{len(ranked)} pages")
    if not pages:
        raise SystemExit("no pages could be fetched")

    def _st(p): return {"url": p["url"], "subtopics": subtopics_for(p, keyword)}
    corpus = [c for c in ThreadPoolExecutor(max_workers=6).map(_st, pages) if c["subtopics"]]
    print(f"  extracted subtopics from {len(corpus)} pages")

    tmpl = synthesize(keyword, target, corpus, len(corpus))
    if not tmpl:
        raise SystemExit("synthesis failed")

    slug = re.sub(r"[^a-z0-9]+", "-", keyword.lower()).strip("-")
    outdir = ROOT / "clients" / client / "content"; outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"{slug}__template.json").write_text(json.dumps(
        {"keyword": keyword, "location": location, "pages_analyzed": len(corpus),
         "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "ranked": ranked, "corpus": corpus, "template": tmpl}, indent=2))
    md = (f"# Content template — {tmpl.get('page_title') or keyword}\n\n"
          f"> keyword: **{keyword}** · {len(corpus)} ranking pages analyzed · "
          f"{datetime.datetime.now().strftime('%Y-%m-%d')}\n\n" + (tmpl.get("markdown") or ""))
    (outdir / f"{slug}__template.md").write_text(md, encoding="utf-8")
    print(f"[content-template] -> clients/{client}/content/{slug}__template.md")
    nt = tmpl.get("new_subtopics") or []
    if nt:
        print("  NEW gap subtopics: " + "; ".join(x.get("label", "") for x in nt))


if __name__ == "__main__":
    main()
