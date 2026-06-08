#!/usr/bin/env python3
"""event-writer: draft a local Eventbrite event from a brief -> pending approval (browser area).
DRAFTS ONLY. The approved event is created on Eventbrite by the CloakBrowser eventbrite_create
workflow (verbatim title/description/when/where) on the client's <client>-cb-agent profile.
  python run.py --client <id> --brief "<event concept + date/time + location>" [--dry-run]"""
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
            k, _, v = line.partition(":"); out[k.strip().lower()] = v.strip()
    return out

def _parse_json(raw):
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw or "", re.S)
        if m:
            try: return json.loads(m.group(0))
            except Exception: return {}
        return {}

def main():
    client = arg("--client", "example-hvac-client")
    brief = arg("--brief", "A free local workshop — include the date, time, and location")
    dry = "--dry-run" in sys.argv
    facts_path = ROOT/"clients"/client/"facts"/"business_entity.md"
    facts = facts_path.read_text() if facts_path.exists() else ""
    fv = parse_facts(facts)
    variables = {"facts": facts, "name": fv.get("name", ""), "phone": fv.get("phone", ""),
                 "service_area": fv.get("service_area", ""), "brief": brief}
    raw, model = generate(str(HERE/"prompts"/"event.md"), variables, kind="event", max_tokens=700, fake=dry)
    obj = _parse_json(raw)

    scope = f"{client}-cb-agent"; workflow = "eventbrite_create"
    content = {"text": obj.get("description") or raw, "title": obj.get("title") or brief[:60],
               "startDateTime": obj.get("startDateTime", ""), "endDateTime": obj.get("endDateTime", ""),
               "location": obj.get("location", ""), "kind": "eventbrite_event"}
    draft = {"draft_id": "draft_"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
             "client_id": client, "kind": "eventbrite_event", "workflow_id": workflow, "scope_id": scope,
             "status": "pending_human_review",
             "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "source": {"brief": brief}, "content": content,
             "provenance": {"generated_by": model, "area": "browser"},
             "note": "Review/edit the event (esp. date/time/location), then approve_draft.py -> created on Eventbrite."}
    pend = ROOT/"clients"/client/"browser"/"approvals"/"pending"; pend.mkdir(parents=True, exist_ok=True)
    out = pend/f"{scope}__{workflow}__draft.json"; out.write_text(json.dumps(draft, indent=2))
    print(f"[event-writer] Eventbrite draft ({model}) -> {out.relative_to(ROOT)}")
    if not dry:
        notify.send(f"Needs approval: Eventbrite event for {client} — review date/time/location", level="approval")
    print("  ", (content["title"] or "")[:80])

if __name__ == "__main__":
    main()
