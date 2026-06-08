"""Tier-3 LLM generation gate. Drafts text from a prompt template + variables.
DRAFTS ONLY — it never posts. Output goes to a pending human-review artifact, which a
human approves (hashed) before the pipeline publishes it. fake=True or no ANTHROPIC_API_KEY
returns a deterministic stub so dry-runs work offline."""
import os, string, pathlib

def _stub(kind, v):
    if kind == "review_reply":
        return (f"Thank you for the {v.get('rating','')}-star review. We appreciate your "
                f"feedback and your trust in {v.get('name','our team')}. Please reach out "
                f"at {v.get('phone','our office')} if we can help further.")[:340]
    return (f"{v.get('brief','Update')} — {v.get('name','')} proudly serving "
            f"{v.get('service_area','your area')}. Call {v.get('phone','us')} today.")[:1490]

def generate(prompt_path, variables, kind="post", max_tokens=1000, fake=False):
    tmpl = pathlib.Path(prompt_path).read_text()
    prompt = string.Template(tmpl).safe_substitute({k: str(v) for k, v in variables.items()})
    if fake or not os.environ.get("ANTHROPIC_API_KEY"):
        return _stub(kind, variables), "stub"
    import requests
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")   # set to your current model
    r = requests.post("https://api.anthropic.com/v1/messages",
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                 "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}, timeout=60)
    r.raise_for_status()
    data = r.json()
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
    return text, model
