#!/usr/bin/env python3
"""video-producer: brief -> image prompt + motion prompt (LLM gate) -> Higgsfield still
(GPT Image 2) -> Higgsfield image-to-video (Seedance) -> PENDING draft for human approval.
Never publishes. Media generation is Higgsfield-only (no Google Cloud)."""
import sys, os, json, datetime, pathlib
HERE = pathlib.Path(__file__).resolve().parent
def root(s):
    for d in [s, *s.parents]:
        if (d/"lib").exists(): return d
    raise SystemExit("root not found")
ROOT = root(HERE); sys.path.insert(0, str(ROOT))
from integrations.llm.gate import generate
from lib import notify

def media_client(fake):
    """Image/video via the Higgsfield CLI only (GPT Image 2 still, Seedance image-to-video)."""
    from integrations.higgsfield_media.client import HiggsfieldMediaClient
    return HiggsfieldMediaClient(fake=fake)

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
    client = arg("--client", "example-hvac-client")
    location = arg("--location", "locations/REPLACE")
    brief = arg("--brief", "Short brand reel")
    workflow = arg("--workflow", "video_asset")      # e.g. youtube_upload to feed the YouTube publisher
    area = arg("--area", "rpa")                       # area the draft lands in (rpa | browser)
    scope = arg("--scope") or str(location).replace("/", "_")
    title = arg("--title")
    link = arg("--link")                              # destination link (e.g. a Pinterest pin)
    still_only = "--still-only" in sys.argv
    dry = "--dry-run" in sys.argv
    rpa = ROOT/"clients"/client/"rpa"
    facts_path = ROOT/"clients"/client/"facts"/"business_entity.md"
    facts = facts_path.read_text() if facts_path.exists() else ""
    fv = parse_facts(facts)
    base = {"facts": facts, "service_area": fv.get("service_area", ""), "brief": brief}

    # 1) LLM gate drafts the prompts (generate-only)
    image_prompt, m1 = generate(str(HERE/"prompts"/"image_prompt.md"), base, kind="post", fake=dry)
    motion_prompt, m2 = generate(str(HERE/"prompts"/"motion_prompt.md"),
                                 {**base, "image_prompt": image_prompt}, kind="post", fake=dry)

    draft_id = "draft_"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    assets = rpa/"assets"/draft_id; assets.mkdir(parents=True, exist_ok=True)
    media = media_client(fake=dry)

    # 2) Nano Banana still
    img_path = assets/"still.png"
    ok, img_meta = media.generate_image(image_prompt, img_path)
    if not ok:
        print(f"[video-producer] image failed: {img_meta}"); sys.exit(1)
    print(f"[video-producer] still ({img_meta['model']}) -> {img_path.relative_to(ROOT)}")

    # 3) Veo image-to-video
    vid_rel = None
    if not still_only:
        vid_path = assets/"clip.mp4"
        ok, vid_meta = media.animate_image(img_path, motion_prompt, vid_path)
        if not ok:
            print(f"[video-producer] video failed: {vid_meta} (still kept)")
        else:
            vid_rel = str(vid_path.relative_to(ROOT))
            print(f"[video-producer] clip ({vid_meta['model']}) -> {vid_path.relative_to(ROOT)}")

    # 4) pending draft (paths to the real assets; human reviews files, then approve_draft.py)
    pend = ROOT/"clients"/client/area/"approvals"/"pending"; pend.mkdir(parents=True, exist_ok=True)
    content = {"text": brief, "image_path": str(img_path.relative_to(ROOT)),
               "video_path": vid_rel, "image_prompt": image_prompt, "motion_prompt": motion_prompt}
    if title: content["title"] = title         # used as the YouTube title when workflow=youtube_upload
    if link: content["link"] = link            # destination link for a Pinterest pin
    asset_base = os.environ.get("ASSET_BASE_URL", "")
    if asset_base:                              # public URL for the still (GBP photo upload / hosted media)
        content["media_url"] = f"{asset_base.rstrip('/')}/{client}/{draft_id}/still.png"
    draft = {"draft_id": draft_id, "client_id": client, "kind": "video_asset",
             "workflow_id": workflow, "scope_id": scope, "status": "pending_human_review",
             "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "source": {"brief": brief}, "content": content,
             "provenance": {"prompt_model": m1, "image_model": img_meta.get("model"),
                            "facts_used": bool(facts)},
             "note": "Review the asset files, then scripts/approve_draft.py to emit a hashed approval."}
    out = pend/f"{scope}__{workflow}__draft.json"; out.write_text(json.dumps(draft, indent=2))
    print(f"[video-producer] pending draft -> {out.relative_to(ROOT)}")
    if not dry:
        notify.send(f"Needs approval: video_asset for {client} ({scope}) — review the still+clip", level="approval")

if __name__ == "__main__": main()
