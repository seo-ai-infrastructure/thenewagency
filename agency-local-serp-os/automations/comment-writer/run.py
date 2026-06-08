#!/usr/bin/env python3
"""comment-writer: draft a short, on-brand comment/reply for a SPECIFIC target (Reddit thread,
Facebook post/group, LinkedIn post, YouTube video) -> pending approval (browser area). DRAFTS ONLY.
The approved comment is posted VERBATIM to params.target by the CloakBrowser <kind>_comment workflow.
  python run.py --kind reddit|facebook|linkedin|youtube --client <id> --target <url> --brief "..." [--dry-run]"""
import sys, json, datetime, pathlib
HERE = pathlib.Path(__file__).resolve().parent
def root(s):
    for d in [s, *s.parents]:
        if (d/"integrations"/"llm").exists(): return d
    raise SystemExit("root not found")
ROOT = root(HERE); sys.path.insert(0, str(ROOT))
from integrations.llm.gate import generate
from lib import notify

KINDS = {"reddit": "reddit_comment", "facebook": "facebook_comment",
         "linkedin": "linkedin_comment", "youtube": "youtube_comment"}

def arg(name, default=None):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv else default

def parse_facts(text):
    out = {}
    for line in text.splitlines():
        line = line.strip().lstrip("-").strip()
        if ":" in line:
            k, _, v = line.partition(":"); out[k.strip().lower()] = v.strip()
    return out

def main():
    kind = arg("--kind", "reddit")
    if kind not in KINDS:
        raise SystemExit(f"--kind must be one of {list(KINDS)}")
    workflow = KINDS[kind]
    client = arg("--client", "example-hvac-client")
    target = arg("--target", "")
    brief = arg("--brief", "Add a genuinely helpful, on-brand comment")
    dry = "--dry-run" in sys.argv
    if not target.strip():
        raise SystemExit("--target URL is required so the publisher knows where to comment")
    target = target.strip()
    facts_path = ROOT/"clients"/client/"facts"/"business_entity.md"
    facts = facts_path.read_text() if facts_path.exists() else ""
    fv = parse_facts(facts)
    variables = {"facts": facts, "name": fv.get("name", ""), "phone": fv.get("phone", ""),
                 "service_area": fv.get("service_area", ""), "platform": kind, "target": target, "brief": brief}
    text, model = generate(str(HERE/"prompts"/"comment.md"), variables, kind="comment", max_tokens=400, fake=dry)

    scope = f"{client}-cb-agent"
    content = {"text": text, "target": target, "kind": workflow}
    draft = {"draft_id": "draft_"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
             "client_id": client, "kind": workflow, "workflow_id": workflow, "scope_id": scope,
             "status": "pending_human_review",
             "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "source": {"brief": brief, "target": target}, "content": content,
             "provenance": {"generated_by": model, "area": "browser"},
             "note": "Review/edit the comment, then approve_draft.py -> posted VERBATIM to the target URL."}
    pend = ROOT/"clients"/client/"browser"/"approvals"/"pending"; pend.mkdir(parents=True, exist_ok=True)
    out = pend/f"{scope}__{workflow}__draft.json"; out.write_text(json.dumps(draft, indent=2))
    print(f"[comment-writer] {kind} comment draft ({model}) -> {out.relative_to(ROOT)}")
    if not dry:
        notify.send(f"Needs approval: {kind} comment for {client} on {target[:50]} — open the board", level="approval")
    print("  ", text[:140] + ("…" if len(text) > 140 else ""))

if __name__ == "__main__":
    main()
