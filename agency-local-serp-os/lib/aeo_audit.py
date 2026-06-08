"""Deterministic crawlability / AEO analysis (no LLM, no network).

Given the Markdown an AI crawler would retrieve for a page, measure how usable it is as model
context: Markdown Purity (signal vs nav/footer boilerplate), Entity Clarity (are Service /
Location / Price / Hours / Guarantee explicitly present), and assemble the audit doc that the
ai-crawl-simulator writes and the AEO tab renders. The crawl itself (per AI bot user-agent) and
the llms.txt fetch are done upstream and injected here, so this stays pure and testable.
"""
import re

BOILERPLATE = ("skip to content", "menu", "privacy policy", "terms of service",
               "all rights reserved", "copyright", "©", "cookie", "subscribe", "sign up",
               "log in", "sign in", "follow us", "back to top", "navigation", "footer", "header")
_LINK_ONLY = re.compile(r"^[-*]?\s*\[.*\]\(.*\)\s*$")


def _is_boilerplate(line):
    s = line.strip().lower()
    if any(m in s for m in BOILERPLATE):
        return True
    if _LINK_ONLY.match(line.strip()):     # a bare nav/link line
        return True
    return len(s) <= 3                      # stray separators / tiny fragments


def markdown_purity(md):
    """Share of content (by chars) that is NOT nav/footer boilerplate. Higher = cleaner context."""
    nonempty = [l for l in (md or "").splitlines() if l.strip()]
    total = sum(len(l) for l in nonempty) or 1
    boiler = [l for l in nonempty if _is_boilerplate(l)]
    boiler_chars = sum(len(l) for l in boiler)
    return {"purity": round((total - boiler_chars) / total, 4),
            "content_lines": len(nonempty) - len(boiler),
            "boilerplate_lines": len(boiler),
            "total_chars": total}


def entity_clarity(md, entities):
    """For each required entity (name -> [regex/substring patterns]), is it explicitly present?"""
    text = (md or "").lower()
    found = {name: any(re.search(p.lower(), text) for p in (pats or []))
             for name, pats in (entities or {}).items()}
    n = len(found) or 1
    return {"entities": found, "found": sum(found.values()), "total": len(found),
            "clarity": round(sum(found.values()) / n, 4),
            "missing": [k for k, v in found.items() if not v]}


def audit(markdown, entities, llms_txt_present=False, bots=None):
    """Assemble the full crawlability report for one page."""
    return {"markdown_purity": markdown_purity(markdown),
            "entity_clarity": entity_clarity(markdown, entities),
            "llms_txt_present": bool(llms_txt_present),
            "bots": bots or []}
