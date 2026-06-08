#!/usr/bin/env python3
"""article-writer: draft long-form content (WordPress article / LinkedIn Pulse / Quora answer)
into a pending human-review artifact in the right area. DRAFTS ONLY — never publishes.
  python run.py --kind wp|linkedin|quora --client <id> --topic "..." [--slug ...] [--dry-run]"""
import sys, json, datetime, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent
def root(s):
    for d in [s, *s.parents]:
        if (d/"integrations"/"llm").exists(): return d
    raise SystemExit("root not found")
ROOT = root(HERE); sys.path.insert(0, str(ROOT))
from integrations.llm.gate import generate
from lib import notify

# kind -> (area, workflow_id, prompt file)
KINDS = {
    "wp":       ("web",     "wp_article_publish", "wp_article.md"),
    "linkedin": ("browser", "linkedin_post",      "linkedin_pulse.md"),
    "quora":    ("browser", "quora_answer_post",  "quora_answer.md"),
    "facebook": ("browser", "facebook_post",      "social_post.md"),
    "reddit":   ("browser", "reddit_post",        "social_post.md"),
    "nextdoor": ("browser", "nextdoor_post",      "social_post.md"),
    "patch":    ("browser", "patch_article",      "patch_article.md"),
}

def arg(name, default=None):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv else default

def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60] or "article"

def parse_facts(text):
    out = {}
    for line in text.splitlines():
        line = line.strip().lstrip("-").strip()
        if ":" in line:
            k, _, v = line.partition(":"); out[k.strip().lower()] = v.strip()
    return out

def main():
    kind = arg("--kind", "wp")
    if kind not in KINDS:
        raise SystemExit(f"--kind must be one of {list(KINDS)}")
    area, workflow, promptfile = KINDS[kind]
    client = arg("--client", "example-hvac-client")
    topic = arg("--topic", "Local service guide")
    slug = arg("--slug") or slugify(topic)
    dry = "--dry-run" in sys.argv
    facts_path = ROOT/"clients"/client/"facts"/"business_entity.md"
    facts = facts_path.read_text() if facts_path.exists() else ""
    fv = parse_facts(facts)
    variables = {"facts": facts, "name": fv.get("name", ""), "phone": fv.get("phone", ""),
                 "service_area": fv.get("service_area", ""), "topic": topic, "title": topic}
    body, model = generate(str(HERE/"prompts"/promptfile), variables, kind=kind, max_tokens=2000, fake=dry)

    # web content is scoped to its slug; social posts are scoped to the persona profile
    # <client>-cb-agent so the work order's profile_id matches the approval (like GBP -> location).
    scope = f"{client}-cb-agent" if area == "browser" else slug
    content = {"title": topic, "text": body, "slug": slug,
               "kind": f"{kind}_article" if kind == "wp" else f"{kind}_post"}
    if kind == "wp":
        content["status"] = "publish"
    draft = {"draft_id": "draft_"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
             "client_id": client, "kind": content["kind"], "workflow_id": workflow, "scope_id": scope,
             "status": "pending_human_review",
             "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "source": {"topic": topic}, "content": content,
             "provenance": {"generated_by": model, "facts_used": bool(facts), "area": area},
             "note": "Review/edit, then scripts/approve_draft.py to emit a hashed approved artifact."}
    pend = ROOT/"clients"/client/area/"approvals"/"pending"; pend.mkdir(parents=True, exist_ok=True)
    out = pend/f"{scope}__{workflow}__draft.json"; out.write_text(json.dumps(draft, indent=2))
    print(f"[article-writer] {kind} draft ({model}) -> {out.relative_to(ROOT)}")
    if not dry:
        notify.send(f"Needs approval: {kind} article '{topic}' for {client} — open the board", level="approval")
    print("  ", body[:160] + ("…" if len(body) > 160 else ""))

if __name__ == "__main__":
    main()
