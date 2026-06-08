#!/usr/bin/env python3
"""podcast-producer: LLM script -> ElevenLabs voice -> audio file + show notes -> pending
approval (web area, podcast_publish). DRAFTS ONLY — never publishes. The podcast-publisher
ships the approved episode to Castopod.
  python run.py --client <id> --topic "..." [--slug ...] [--dry-run]"""
import sys, os, json, datetime, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent
def root(s):
    for d in [s, *s.parents]:
        if (d/"lib").exists(): return d
    raise SystemExit("root not found")
ROOT = root(HERE); sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()
from lib.rate_limiter import RateLimiter
from integrations.llm.gate import generate
from integrations.elevenlabs.client import ElevenLabsClient
from lib import notify

def arg(name, default=None):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv else default

def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60] or "episode"

def parse_facts(text):
    out = {}
    for line in text.splitlines():
        line = line.strip().lstrip("-").strip()
        if ":" in line:
            k, _, v = line.partition(":"); out[k.strip().lower()] = v.strip()
    return out

def main():
    client = arg("--client", "example-hvac-client")
    topic = arg("--topic", "Local service episode")
    slug = arg("--slug") or slugify(topic)
    dry = "--dry-run" in sys.argv
    facts_path = ROOT/"clients"/client/"facts"/"business_entity.md"
    facts = facts_path.read_text() if facts_path.exists() else ""
    fv = parse_facts(facts)
    variables = {"facts": facts, "name": fv.get("name", ""), "phone": fv.get("phone", ""),
                 "service_area": fv.get("service_area", ""), "topic": topic}

    # 1) script
    script_text, model = generate(str(HERE/"prompts"/"podcast_script.md"),
                                  variables, kind="podcast", max_tokens=2500, fake=dry)
    # 2) voice (ElevenLabs)
    RL = RateLimiter(ROOT/".elevenlabs_rate_state", min_interval=0.5, fake=dry)
    el = ElevenLabsClient(RL, fake=dry)
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "default-voice")
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if dry or api_key:
        ok, audio = el.tts(script_text, voice_id, api_key or "fake")
    else:
        ok, audio = False, {"error": "ELEVENLABS_API_KEY not set — script drafted, audio skipped"}
    audio_dir = ROOT/"clients"/client/"content"/"audio"; audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir/f"{slug}.mp3"
    if ok and isinstance(audio, bytes):
        audio_path.write_bytes(audio)

    # 3) draft (show notes + audio reference)
    notes = (script_text or "")[:600]
    asset_base = os.environ.get("ASSET_BASE_URL", "")
    audio_url = (f"{asset_base.rstrip('/')}/{client}/audio/{slug}.mp3" if asset_base else "")
    content = {"title": topic, "text": notes, "description": notes, "audio_url": audio_url,
               "audio_path": str(audio_path.relative_to(ROOT)) if audio_path.exists() else "",
               "kind": "podcast", "script": script_text}
    draft = {"draft_id": "draft_"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
             "client_id": client, "kind": "podcast", "workflow_id": "podcast_publish", "scope_id": slug,
             "status": "pending_human_review",
             "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "source": {"topic": topic}, "content": content,
             "provenance": {"generated_by": model, "voice": voice_id if ok else "none",
                            "audio_synthesized": bool(ok), "area": "web"},
             "note": "Host the audio (set ASSET_BASE_URL/audio_url), review, then approve_draft.py "
                     "-> podcast-publisher ships it to Castopod."}
    pend = ROOT/"clients"/client/"web"/"approvals"/"pending"; pend.mkdir(parents=True, exist_ok=True)
    out = pend/f"{slug}__podcast_publish__draft.json"; out.write_text(json.dumps(draft, indent=2))
    print(f"[podcast-producer] script ({model}) + audio({'ok' if ok else 'skipped'}) -> {out.relative_to(ROOT)}")
    if not dry:
        notify.send(f"Needs approval: podcast '{topic}' for {client} — open the board", level="approval")

if __name__ == "__main__":
    main()
