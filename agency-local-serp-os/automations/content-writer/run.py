#!/usr/bin/env python3
"""content-writer: draft GBP posts (update / event / offer) + review replies -> pending artifact."""
import sys, re, json, datetime, pathlib

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

def parse_facts(text):
    out = {}
    for line in text.splitlines():
        line = line.strip().lstrip("-").strip()
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip().lower()] = v.strip()
    return out

def _parse_json(raw):
    """Pull a JSON object out of an LLM reply (it may wrap it in prose/fences). {} if none."""
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw or "", re.S)
        if m:
            try: return json.loads(m.group(0))
            except Exception: return {}
        return {}

def main():
    kind = arg("--kind", "post")
    client = arg("--client", "example-hvac-client")
    location = arg("--location", "locations/REPLACE")
    dry = "--dry-run" in sys.argv
    media_url = arg("--media-url")
    review_id = arg("--review-id", "")       # which Google review the reply targets (Zernio reply path)
    rpa = ROOT/"clients"/client/"rpa"
    facts_path = ROOT/"clients"/client/"facts"/"business_entity.md"
    facts = facts_path.read_text() if facts_path.exists() else ""
    fv = parse_facts(facts)
    base = {"facts": facts, "name": fv.get("name",""), "phone": fv.get("phone",""),
            "service_area": fv.get("service_area","")}

    topic_type = event = offer = None
    if kind == "review_reply":
        prompt = HERE/"prompts"/"review_reply.md"; workflow = "gbp_review_reply"
        base.update({"review": arg("--review",""), "rating": arg("--rating","5")})
        text, model = generate(str(prompt), base, kind=kind, fake=dry)
    elif kind in ("event", "offer"):
        prompt = HERE/"prompts"/f"gbp_{kind}.md"; workflow = "gbp_post_publish"
        base.update({"brief": arg("--brief", f"A GBP {kind} — include the dates/terms in the brief")})
        raw, model = generate(str(prompt), base, kind=kind, max_tokens=700, fake=dry)
        obj = _parse_json(raw); topic_type = kind.upper()
        text = obj.get("text") or raw
        if kind == "event": event = obj.get("event")
        else: offer = obj.get("offer")
    else:
        prompt = HERE/"prompts"/"gbp_post.md"; workflow = "gbp_post_publish"
        base.update({"brief": arg("--brief","Seasonal update")})
        text, model = generate(str(prompt), base, kind=kind, fake=dry)
    scope = str(location).replace("/", "_")
    pend = rpa/"approvals"/"pending"; pend.mkdir(parents=True, exist_ok=True)
    content = {"text": text}
    if media_url: content["media_url"] = media_url
    if review_id: content["review_id"] = review_id      # gbp_review_reply: the review to reply to
    if topic_type: content["topic_type"] = topic_type   # STANDARD|EVENT|OFFER (zernio-publisher reads it)
    if event: content["event"] = event
    if offer: content["offer"] = offer
    draft = {"draft_id": "draft_"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
             "client_id": client, "kind": kind, "workflow_id": workflow, "scope_id": scope,
             "status": "pending_human_review", "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "source": {k: base[k] for k in ("brief","review","rating") if k in base},
             "content": content, "provenance": {"generated_by": model, "facts_used": bool(facts)},
             "note": "Review/edit, then scripts/approve_draft.py to emit a hashed approved artifact."}
    out = pend/f"{scope}__{workflow}__draft.json"; out.write_text(json.dumps(draft, indent=2))
    print(f"[content-writer] {kind} draft ({model}) -> {out.relative_to(ROOT)}")
    if not dry:
        notify.send(f"Needs approval: {kind} · {workflow} for {client} ({scope}) — open the board", level="approval")
    print("  ", text[:160] + ("…" if len(text) > 160 else ""))

if __name__ == "__main__":
    main()
