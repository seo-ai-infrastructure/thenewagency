#!/usr/bin/env python3
"""gen_edge_html: draft static HTML + Schema.org JSON-LD for a Cloudflare edge worker.
The AI-Overview / speed tactic: schema-rich static HTML at the edge. DRAFTS ONLY -> pending
approval in the web area (edge_deploy). The body is LLM-written; the script wraps it in a full
HTML doc with LocalBusiness + WebPage JSON-LD built from the client's facts.
  python scripts/gen_edge_html.py --client <id> --topic "..." [--slug ...] [--dry-run]"""
import sys, json, html, datetime, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()
from integrations.llm.gate import generate
from lib import notify

def arg(name, default=None):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv else default

def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60] or "edge"

def parse_facts(text):
    out = {}
    for line in text.splitlines():
        line = line.strip().lstrip("-").strip()
        if ":" in line:
            k, _, v = line.partition(":"); out[k.strip().lower()] = v.strip()
    return out

def build_doc(title, body_html, fv):
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": title,
          "about": {"@type": "LocalBusiness", "name": fv.get("name", ""),
                    "telephone": fv.get("phone", ""), "areaServed": fv.get("service_area", "")}}
    t = html.escape(title)
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{t}</title>"
            f"<script type=\"application/ld+json\">{json.dumps(ld)}</script>"
            f"</head><body><main><h1>{t}</h1>\n{body_html}\n</main></body></html>")

def main():
    client = arg("--client", "example-hvac-client")
    topic = arg("--topic", "Local service answer")
    slug = arg("--slug") or slugify(topic)
    dry = "--dry-run" in sys.argv
    facts_path = ROOT/"clients"/client/"facts"/"business_entity.md"
    facts = facts_path.read_text() if facts_path.exists() else ""
    fv = parse_facts(facts)
    variables = {"facts": facts, "name": fv.get("name", ""), "phone": fv.get("phone", ""),
                 "service_area": fv.get("service_area", ""), "topic": topic, "title": topic}
    body, model = generate(str(ROOT/"automations"/"article-writer"/"prompts"/"wp_article.md"),
                           variables, kind="edge", max_tokens=2000, fake=dry)
    doc = build_doc(topic, body, fv)
    content = {"title": topic, "text": doc, "slug": slug, "kind": "edge_html"}
    draft = {"draft_id": "draft_"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
             "client_id": client, "kind": "edge_html", "workflow_id": "edge_deploy", "scope_id": slug,
             "status": "pending_human_review",
             "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "source": {"topic": topic}, "content": content,
             "provenance": {"generated_by": model, "facts_used": bool(facts), "area": "web"},
             "note": "Review/edit, then scripts/approve_draft.py -> deploys to Cloudflare via edge-deployer."}
    pend = ROOT/"clients"/client/"web"/"approvals"/"pending"; pend.mkdir(parents=True, exist_ok=True)
    out = pend/f"{slug}__edge_deploy__draft.json"; out.write_text(json.dumps(draft, indent=2))
    print(f"[gen_edge_html] edge_html draft ({model}, {len(doc)} bytes) -> {out.relative_to(ROOT)}")
    if not dry:
        notify.send(f"Needs approval: edge HTML '{topic}' for {client} — open the board", level="approval")

if __name__ == "__main__":
    main()
