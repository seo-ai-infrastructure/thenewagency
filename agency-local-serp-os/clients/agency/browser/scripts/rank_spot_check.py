"""CloakBrowser/Playwright workflow: deterministic Google SERP position check for a
domain + keyword, from a real (stealth, residential-proxied) browser.

READ ONLY: it observes positions; it never clicks ads, results, or interacts with the SERP.
The runner launches the profile and calls run(page, params). params: keyword, domain, location.
"""
import urllib.parse


def _host(url):
    try:
        h = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ""
    return h[4:] if h.startswith("www.") else h


def run(page, params):
    keyword = (params.get("keyword") or "").strip()
    location = (params.get("location") or "").strip()
    raw = (params.get("domain") or "").strip().lower()
    domain = _host("http://" + raw) if "/" in raw or "." in raw else raw   # normalize to bare host
    domain = domain[4:] if domain.startswith("www.") else domain

    q = (keyword + " " + location).strip()
    page.goto("https://www.google.com/search?" + urllib.parse.urlencode({"q": q, "num": "20", "hl": "en", "gl": "us"}),
              wait_until="domcontentloaded", timeout=45000)

    # Dismiss the EU/consent interstitial if present (common from residential exits).
    for sel in ("button#L2AGLb", "button:has-text('Accept all')", "button:has-text('Reject all')",
                "form[action*='consent'] button", "div[role='dialog'] button:has-text('Accept')"):
        try:
            b = page.query_selector(sel)
            if b:
                b.click(); page.wait_for_timeout(800); break
        except Exception:
            pass

    blocked = "/sorry/" in (page.url or "") or page.query_selector("form#captcha-form") is not None
    try:
        page.wait_for_selector("div#search, div#rso", timeout=15000)
    except Exception:
        pass

    # Organic rank = position among DISTINCT result domains (skip sitelinks/duplicates).
    organic_pos, matched_url, total, seen = None, None, 0, set()
    for a in page.query_selector_all("div#search a:has(h3), div#rso a:has(h3)"):
        href = a.get_attribute("href") or ""
        if not href.startswith("http"):
            continue
        host = _host(href)
        if not host or host in seen or "google." in host:
            continue
        seen.add(host); total += 1
        if domain and domain in host and organic_pos is None:
            organic_pos, matched_url = total, href

    local_pack_present = page.query_selector(
        "div.rllt__details, div[aria-label*='Local results'], div[jsname][data-hveid] g-more-link") is not None

    return {"keyword": keyword, "domain": domain, "location": location,
            "organic_position": organic_pos, "organic_results_scanned": total,
            "matched_url": matched_url, "local_pack_present": bool(local_pack_present),
            "blocked": bool(blocked), "note": "read-only observation"}
