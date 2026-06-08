#!/usr/bin/env python3
"""Zernio publisher — API posting to Google Business Profile + social platforms.
Separate subsystem from DuoPlus RPA. No phones, no device locks. Shares only lib/.
  python run.py [--dry-run] [--date YYYY-MM-DD] [--client <id>]"""
import sys, os, json, pathlib, yaml
HERE = pathlib.Path(__file__).resolve().parent
def root(s):
    for d in [s, *s.parents]:
        if (d/"lib").exists(): return d
    raise SystemExit("root not found")
ROOT = root(HERE); sys.path.insert(0, str(ROOT))
from lib.rate_limiter import RateLimiter
from lib.orchestration import WorkOrderRunner
from lib import policy as pol
from integrations.google_business.client import ZernioGBPClient

DRY    = "--dry-run" in sys.argv
CLIENT = sys.argv[sys.argv.index("--client")+1] if "--client" in sys.argv else "example-hvac-client"
RPA    = ROOT/"clients"/CLIENT/"rpa"
POLICY = pol.load(RPA)
WFS = {w["workflow_id"]: w for w in yaml.safe_load((RPA/"workflows.yaml").read_text())["workflows"]}
if os.environ.get("REDIS_HOST") and not DRY:        # dry-run stays offline (no network)
    from lib.redis_backends import get_redis, RedisRateLimiter
    RL = RedisRateLimiter(get_redis(), max_per_sec=5, key="zernio:ratelimit")
else:
    RL = RateLimiter(ROOT/".zernio_rate_state", min_interval=0.5, fake=DRY)
GBP = ZernioGBPClient(RL, fake=DRY)
R = WorkOrderRunner(HERE, ROOT, RPA, POLICY, notify=not DRY)

def process(wo_path):
    wo = json.loads(wo_path.read_text())
    if wo.get("execution_method") != "google_business_api": return    # not ours
    working = R.claim(wo_path)
    if not working: return
    wid = wo["work_order_id"]; wf = WFS[wo["workflow_id"]]
    rep = {"work_order_id": wid, "scope_id": wo["profile_id"], "workflow_id": wo["workflow_id"],
           "execution": "google_business_api"}
    try:
        ok, key, approval_path = R.gate(wo, wf, working, rep, None)   # no phone profile for API
        if not ok: return
        content_obj = {}
        if approval_path:
            content_obj = json.loads(pathlib.Path(approval_path).read_text()).get("content") or {}
        content = content_obj.get("text", ""); media_url = content_obj.get("media_url")
        cta = content_obj.get("cta")                 # {type, url} CTA button (optional) — Zernio key is `type`
        topic_type = content_obj.get("topic_type", "STANDARD")   # STANDARD | EVENT | OFFER
        event = content_obj.get("event"); offer = content_obj.get("offer")
        # SAFETY: EVENT/OFFER require their structured payload (Google rejects otherwise) -> if it's
        # missing, post as a STANDARD update with the text rather than fail or publish a broken post.
        if topic_type == "EVENT" and not event: topic_type = "STANDARD"
        if topic_type == "OFFER" and not offer: topic_type = "STANDARD"
        ev_before = R.evidence(wo, "before"); ac = wf.get("action_class")
        if ac == "gbp_post_publish":
            landed, resp = GBP.create_local_post(wo["account_id"], content, media_url=media_url,
                                                 location_id=wo.get("location_id"), call_to_action=cta,
                                                 topic_type=topic_type, event=event, offer=offer)
        elif ac == "gbp_photo_upload":
            landed, resp = GBP.create_media(wo["account_id"], media_url or content, category="ADDITIONAL")
        elif ac == "gbp_review_reply":
            review_id = content_obj.get("review_id") or wo.get("review_id", "")
            landed, resp = GBP.reply_to_review(wo["account_id"], review_id, content)
        else:
            landed, resp = False, {"error": f"no API mapping for action_class {ac}"}
        if not landed:
            print(f"  {wid}: Zernio call did not land -> failed ({resp.get('error','')})")
            R.finish(working, "failed", {**rep, "reason": resp.get("error", "not landed"),
                                         "stage": "execute", "evidence": [ev_before]}); return
        ev_after = R.evidence(wo, "after"); R.mark_processed(key)
        if approval_path: R.consume_approval(approval_path)
        print(f"  {wid}: {wo['workflow_id']} via Zernio -> DONE (confirmed, approval consumed)")
        R.finish(working, "done", {**rep, "landed": True, "evidence": [ev_before, ev_after], "task_report": resp})
    except Exception as e:    # never leave a claimed work order stuck in working/
        if working.exists():
            R.finish(working, "failed", {**rep, "reason": f"unexpected error: {type(e).__name__}: {e}",
                                         "stage": "exception"})
        print(f"  {wid}: unexpected error -> failed ({type(e).__name__}: {e})")

def main():
    d = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else "today"
    print(f"[zernio-publisher] client={CLIENT} date={d} dry={DRY} | kill_switch={'ON' if pol.kill_switch_active(POLICY) else 'off'}")
    wos = R.inbox()
    if not wos: print("  inbox empty — run scripts/gen_workorders.py first")
    for wo_path in wos: process(wo_path)
    print("[zernio-publisher] done")

if __name__ == "__main__": main()
