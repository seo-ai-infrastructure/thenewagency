#!/usr/bin/env python3
"""Bridge an APPROVED video_asset into a gated GBP post work order.

Chain: video-producer -> human approves video_asset -> THIS bridge -> zernio-publisher posts.
The human already reviewed the asset files, so the bridge routes (it does not create new
content): it maps the local asset to a public URL you host, emits a gbp_post_publish approval
with the SAME hashing the gate uses, and drops a typed work order into the zernio inbox.

GBP note: Google Business Profile posts do NOT support video (one image only). For a
googlebusiness target the STILL is posted as the image; the clip URL is recorded for social use.

  python scripts/bridge_asset_to_post.py <client> <scope> <period> \
      [--base-url https://cdn.example.com/assets] [--image-url URL] [--video-url URL] [--days 7]
You sync clients/<id>/rpa/assets/<draft_id>/ to {base-url}/<id>/<draft_id>/.
"""
import sys, json, pathlib, yaml
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from lib import approvals, notify

def arg(n, d=None): return sys.argv[sys.argv.index(n)+1] if n in sys.argv else d

client, scope, period = sys.argv[1], sys.argv[2], sys.argv[3]
base_url = arg("--base-url") or __import__("os").environ.get("ASSET_BASE_URL")
image_url_override = arg("--image-url"); video_url_override = arg("--video-url")
days = int(arg("--days", "7"))

rpa = ROOT/"clients"/client/"rpa"
asset_appr = rpa/"approvals"/"approved"/f"{scope}__video_asset__{period}.json"
if not asset_appr.exists():
    sys.exit(f"no approved video_asset at {asset_appr} — approve the asset first")
a = json.loads(asset_appr.read_text())
text = (a.get("content") or {}).get("text", "")
draft_id = (a.get("provenance") or {}).get("approved_from_draft")
if not draft_id:
    sys.exit("approved artifact has no source draft_id in provenance")

# locate the asset files the human approved
asset_dir = rpa/"assets"/draft_id
still = asset_dir/"still.png"; clip = asset_dir/"clip.mp4"

def url_for(filename):
    if not base_url: sys.exit("set --base-url or ASSET_BASE_URL (you host the files)")
    return f"{base_url.rstrip('/')}/{client}/{draft_id}/{filename}"

image_url = image_url_override or url_for("still.png")
video_url = video_url_override or (url_for("clip.mp4") if clip.exists() else None)

# resolve account_id + location_id for the GBP work order
gb = yaml.safe_load((rpa/"google_business.yaml").read_text()) if (rpa/"google_business.yaml").exists() else {}
account_id = gb.get("account_id", "REPLACE")
location_id = gb.get("default_location_id", "locations/REPLACE")
for loc in gb.get("locations", []) or []:
    if str(loc.get("id", "")).replace("/", "_") == scope:
        location_id = loc["id"]; break

# emit the gbp_post_publish approval (same hashing as the gate). GBP posts the STILL image.
content = {"text": text, "media_url": image_url, "video_url": video_url}
out, h = approvals.write_approval(ROOT, client, "rpa", scope, "gbp_post_publish", period, content,
            days=days, provenance={"bridged_from": "video_asset", "asset_draft_id": draft_id,
                                   "asset_approval": asset_appr.name})
# typed work order -> zernio inbox
inbox = ROOT/"automations"/"zernio-publisher"/"inbox"; inbox.mkdir(parents=True, exist_ok=True)
wo = {"work_order_id": f"wo_gbp_bridged_{period}_{scope}", "execution_method": "google_business_api",
      "client_id": client, "order_index": 0, "manual": True, "issued_by": "bridge",
      "profile_id": scope, "account_id": account_id, "location_id": location_id,
      "workflow_id": "gbp_post_publish", "period": period, "customer_facing": True,
      "approval_ref": str(out.relative_to(ROOT) if out.is_absolute() else out)}
wo["approval_ref"] = str(out)  # absolute path verify_approval expects
wo_out = inbox/f"{wo['work_order_id']}.json"
tmp = wo_out.with_suffix(".json.tmp"); tmp.write_text(json.dumps(wo, indent=2)); tmp.replace(wo_out)

print(f"bridged video_asset -> gbp_post_publish")
print(f"  approval: {out.name} (hash {h[:12]}…)")
print(f"  GBP image (still): {image_url}")
print(f"  clip URL (recorded, NOT posted to GBP — Google has no video posts): {video_url}")
print(f"  work order -> {wo_out.relative_to(ROOT)}")
notify.send(f"Queued GBP post (bridged video_asset) for {client} ({scope})", level="info")
