"""Query consumer AI engines (ChatGPT / Claude) to measure brand visibility in AI answers.

Used by the ai-visibility automation to ask each engine the client's queries and detect whether
the client is recommended/cited and how it is framed. Models are env-overridable so they can be
bumped without a code change. stdlib `requests` only."""
import os
import requests

OPENAI_MODEL = os.environ.get("AI_VIS_OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_MODEL = os.environ.get("AI_VIS_ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")


def ask_openai(prompt, model=None, timeout=90):
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"},
        json={"model": model or OPENAI_MODEL, "temperature": 0,
              "messages": [{"role": "user", "content": prompt}]}, timeout=timeout)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def ask_anthropic(prompt, model=None, timeout=90):
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
        json={"model": model or ANTHROPIC_MODEL, "max_tokens": 1024,
              "messages": [{"role": "user", "content": prompt}]}, timeout=timeout)
    r.raise_for_status()
    return "".join(p.get("text", "") for p in (r.json().get("content") or []) if p.get("type") == "text")


# engine key -> (label, fn). 'google_ai' is measured separately via the DataForSEO ai_mode tracker.
ENGINES = {"chatgpt": ("ChatGPT", ask_openai), "claude": ("Claude", ask_anthropic)}
