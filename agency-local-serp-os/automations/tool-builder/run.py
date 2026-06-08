#!/usr/bin/env python3
"""tool-builder: generate a self-contained interactive widget/tool (HTML + inline JS/CSS) for
the client — e.g. an AC-size calculator, quote estimator, savings tool. These are link-worthy
assets that earn backlinks + dwell time. DRAFTS ONLY -> pending approval (web area, edge_deploy);
the edge-deployer ships the approved tool to Cloudflare.
  python run.py --client <id> --tool "AC size calculator" [--slug ...] [--dry-run]"""
import sys, json, datetime, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent
def root(s):
    for d in [s, *s.parents]:
        if (d/"integrations"/"llm").exists(): return d
    raise SystemExit("root not found")
ROOT = root(HERE); sys.path.insert(0, str(ROOT))
from integrations.llm.gate import generate
from lib import notify

def arg(name, default=None):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv else default

def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60] or "tool"

def parse_facts(text):
    out = {}
    for line in text.splitlines():
        line = line.strip().lstrip("-").strip()
        if ":" in line:
            k, _, v = line.partition(":"); out[k.strip().lower()] = v.strip()
    return out

def main():
    client = arg("--client", "example-hvac-client")
    tool = arg("--tool", "Service cost calculator")
    slug = arg("--slug") or slugify(tool)
    dry = "--dry-run" in sys.argv
    facts_path = ROOT/"clients"/client/"facts"/"business_entity.md"
    facts = facts_path.read_text() if facts_path.exists() else ""
    fv = parse_facts(facts)
    variables = {"facts": facts, "name": fv.get("name", ""), "phone": fv.get("phone", ""),
                 "service_area": fv.get("service_area", ""), "tool": tool, "topic": tool, "title": tool}
    code, model = generate(str(HERE/"prompts"/"code_tool.md"), variables, kind="code", max_tokens=3000, fake=dry)

    content = {"title": tool, "text": code, "slug": slug, "kind": "code_tool"}
    draft = {"draft_id": "draft_"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
             "client_id": client, "kind": "code_tool", "workflow_id": "edge_deploy", "scope_id": slug,
             "status": "pending_human_review",
             "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "source": {"tool": tool}, "content": content,
             "provenance": {"generated_by": model, "facts_used": bool(facts), "area": "web"},
             "note": "Review/test the widget, then approve_draft.py -> edge-deployer ships it to Cloudflare."}
    pend = ROOT/"clients"/client/"web"/"approvals"/"pending"; pend.mkdir(parents=True, exist_ok=True)
    out = pend/f"{slug}__edge_deploy__draft.json"; out.write_text(json.dumps(draft, indent=2))
    print(f"[tool-builder] code_tool draft ({model}, {len(code)} bytes) -> {out.relative_to(ROOT)}")
    if not dry:
        notify.send(f"Needs approval: tool '{tool}' for {client} — open the board", level="approval")

if __name__ == "__main__":
    main()
