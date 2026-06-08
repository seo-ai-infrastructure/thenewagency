"""Firecrawl scrape client. Crawls a URL AS a given AI crawler (user-agent spoof) and returns the
clean Markdown that crawler would ingest — the basis for the AEO crawlability audit. Live HTTP
needs FIRECRAWL_API_KEY in env; tests inject `post`. No local model anywhere — we just fetch the
page the way each AI bot would and measure what comes back.
"""
import os

API = "https://api.firecrawl.dev/v1/scrape"

# The AI crawler fleet we emulate. User-agent strings per vendor docs (Categories 1-3:
# training, search/retrieval, user-triggered). Opt-out tokens (Google-Extended, Applebot-Extended)
# are NOT crawlers and are intentionally excluded — they make no requests.
AI_BOTS = {
    "GPTBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)",
    "OAI-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot)",
    "ChatGPT-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ChatGPT-User/1.0; +https://openai.com/bot)",
    "ClaudeBot": "Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "Claude-SearchBot": "Mozilla/5.0 (compatible; Claude-SearchBot/1.0; +claudebot@anthropic.com)",
    "Claude-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0; +Claude-User@anthropic.com)",
    "PerplexityBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
    "Perplexity-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)",
    "Bingbot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Amazonbot": "Mozilla/5.0 (compatible; Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot)",
    "Meta-ExternalAgent": "meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)",
    "CCBot": "CCBot/2.0 (https://commoncrawl.org/faq/)",
    "Applebot": "Mozilla/5.0 (compatible; Applebot/0.1; +http://www.apple.com/go/applebot)",
    "DuckAssistBot": "Mozilla/5.0 (compatible; DuckAssistBot/1.0; +https://duckduckgo.com/duckassistbot)",
}


def scrape(url, bot=None, api_key=None, post=None, timeout=120):
    """Scrape `url` -> {markdown, status_code, blocked, bot}. If `bot` is given, send that crawler's
    user-agent so the fetch reflects what THAT AI bot would retrieve. blocked=True on a 4xx or an
    unsuccessful Firecrawl response (robots/blocked/paywalled)."""
    api_key = api_key or os.environ.get("FIRECRAWL_API_KEY")
    if post is None:
        import requests
        post = lambda u, h, b: requests.post(u, headers=h, json=b, timeout=timeout)
    body = {"url": url, "formats": ["markdown"], "onlyMainContent": False}
    if bot and bot in AI_BOTS:
        body["headers"] = {"User-Agent": AI_BOTS[bot]}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = post(API, headers, body)
    data = resp.json() if hasattr(resp, "json") else (resp or {})
    md = (data.get("data") or {}).get("markdown") or data.get("markdown") or ""
    sc = getattr(resp, "status_code", None) or data.get("status_code")
    blocked = bool(sc and sc >= 400) or (data.get("success") is False)
    return {"markdown": md, "status_code": sc, "blocked": blocked, "bot": bot}
