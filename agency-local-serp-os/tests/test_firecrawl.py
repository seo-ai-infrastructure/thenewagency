"""Unit tests for the Firecrawl client (integrations/firecrawl). Crawls a URL AS a given AI bot
(user-agent spoof) and returns clean Markdown. HTTP is injected — no network, no key needed."""
from integrations.firecrawl import client as fc


class _Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status
    def json(self):
        return self._p


def test_scrape_returns_markdown_and_sends_bot_user_agent():
    captured = {}
    def post(url, headers, body):
        captured["body"] = body
        return _Resp({"success": True, "data": {"markdown": "# AC Repair\nclean content"}})
    out = fc.scrape("https://ex.com", bot="GPTBot", api_key="k", post=post)
    assert out["markdown"].startswith("# AC Repair") and out["blocked"] is False
    assert "GPTBot" in captured["body"]["headers"]["User-Agent"]


def test_scrape_flags_blocked_on_4xx():
    out = fc.scrape("https://ex.com", bot="ClaudeBot", api_key="k",
                    post=lambda u, h, b: _Resp({"success": False}, status=403))
    assert out["blocked"] is True and out["bot"] == "ClaudeBot"


def test_ai_bots_registry_has_major_crawlers():
    assert {"GPTBot", "ClaudeBot", "PerplexityBot", "OAI-SearchBot", "Bingbot"} <= set(fc.AI_BOTS)
