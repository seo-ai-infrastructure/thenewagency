#!/usr/bin/env python3
"""Multi-engine AI brand-visibility probe.

Asks each consumer AI engine (ChatGPT, Claude) the client's tracked queries as a real homeowner
would, then detects whether the client is recommended/cited and captures how it's framed. Writes
clients/<id>/signals/ai_visibility.json for the AI Search tab. Google AI Mode visibility is
measured separately by the DataForSEO tracker and folded in by the dashboard.

  python run.py [--client example-hvac-client] [--engines chatgpt,claude]
"""
import sys, json, re, datetime, pathlib, yaml
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]; sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()
from integrations.ai_engines.client import ENGINES

CITY = "Fort Lauderdale, FL"


def _prompt(kw):
    return (f"I'm a homeowner near {CITY}. {kw.capitalize()}? Recommend specific local companies "
            f"and include their website domains.")


def _tokens(assets):
    toks = []
    for tier in ("owned", "controlled", "influenced"):
        toks += [str(t).lower() for t in (assets.get(tier) or [])]
    return [t for t in toks if t]


def _snippet(answer, toks):
    for sent in re.split(r"(?<=[.!?])\s+", answer):
        if any(t in sent.lower() for t in toks):
            return sent.strip()[:300]
    return None


def main():
    a = sys.argv
    client = a[a.index("--client") + 1] if "--client" in a else "example-hvac-client"
    engines = (a[a.index("--engines") + 1].split(",") if "--engines" in a else list(ENGINES))
    facts = ROOT / "clients" / client / "facts"
    terms = yaml.safe_load((facts / "targeted-search-terms.yaml").read_text())
    kws = [t["keyword"] for t in terms["rank_tracking"]["organic_mobile_terms"]]
    assets = yaml.safe_load((facts / "owned-assets.yaml").read_text())
    toks = _tokens(assets)

    results = []
    for kw in kws:
        for eng in engines:
            label, fn = ENGINES[eng]
            try:
                ans = fn(_prompt(kw))
            except Exception as e:
                print(f"  [skip] {eng} / {kw}: {type(e).__name__}: {str(e)[:120]}")
                continue
            low = ans.lower()
            mentioned = any(t in low for t in toks)
            results.append({"keyword": kw, "engine": eng, "engine_label": label,
                            "mentioned": mentioned, "snippet": _snippet(ans, toks) if mentioned else None,
                            "answer_chars": len(ans)})
            print(f"  {eng:8} {'✓' if mentioned else '·'} {kw}")

    out = {"client": client, "city": CITY, "brand_tokens": toks,
           "pulled": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "engines": engines, "results": results}
    p = ROOT / "clients" / client / "signals" / "ai_visibility.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2))
    hits = sum(1 for r in results if r["mentioned"])
    print(f"[ai-visibility] {client}: {hits}/{len(results)} mentions across {len(engines)} engines "
          f"-> clients/{client}/signals/ai_visibility.json")


if __name__ == "__main__":
    main()
