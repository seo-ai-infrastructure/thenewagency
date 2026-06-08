#!/usr/bin/env python3
"""DuoPlus RPA orchestrator — phone-based in-app automation ONLY.
Zernio/API publishing lives in automations/zernio-publisher (separate subsystem).
  python run.py [--dry-run] [--date YYYY-MM-DD] [--client <id>]"""
import sys, os, json, time, random, pathlib, yaml
HERE = pathlib.Path(__file__).resolve().parent
def root(s):
    for d in [s, *s.parents]:
        if (d/"lib").exists(): return d
    raise SystemExit("root not found")
ROOT = root(HERE); sys.path.insert(0, str(ROOT))
from lib.rate_limiter import RateLimiter
from lib.orchestration import WorkOrderRunner
from lib import policy as pol
from integrations.duoplus.client import DuoPlusClient

DRY    = "--dry-run" in sys.argv
CLIENT = sys.argv[sys.argv.index("--client")+1] if "--client" in sys.argv else "example-hvac-client"
RPA    = ROOT/"clients"/CLIENT/"rpa"
LOCKS  = HERE/"state"/"locks"
POLICY = pol.load(RPA)
PROFILES = {p["profile_id"]: p for p in yaml.safe_load((RPA/"profiles.yaml").read_text())["profiles"]}
WFS = {w["workflow_id"]: w for w in yaml.safe_load((RPA/"workflows.yaml").read_text())["workflows"]}
# phone_id (local label) -> duoplus_image_id (the real DuoPlus id, e.g. "j6UjF"). Falls back
# to the label if phones.yaml is absent or the image id is still a placeholder.
def _image_id(p):
    iid = (p.get("duoplus_image_id") or "").strip()
    return iid if iid.strip("_") else p["phone_id"]
_phones_f = RPA/"phones.yaml"
PHONES = {p["phone_id"]: _image_id(p)
          for p in (yaml.safe_load(_phones_f.read_text()).get("phones", []) if _phones_f.exists() else [])}
if os.environ.get("REDIS_HOST") and not DRY:        # dry-run stays offline (file locks, no network)
    from lib.redis_backends import get_redis, RedisRateLimiter, RedisLock
    _RC = get_redis(); RL = RedisRateLimiter(_RC, max_per_sec=1, key="duoplus:ratelimit"); _LOCK = RedisLock(_RC)
else:
    RL = RateLimiter(ROOT/".duoplus_rate_state", min_interval=1.0, fake=DRY); _LOCK = None
DEV = DuoPlusClient(RL, fake=DRY)
R = WorkOrderRunner(HERE, ROOT, RPA, POLICY, notify=not DRY)

def lock(name):
    if _LOCK: return _LOCK.acquire(name)
    LOCKS.mkdir(parents=True, exist_ok=True); p = LOCKS/f"{name}.lock"
    try: fd = os.open(str(p), os.O_CREAT|os.O_EXCL|os.O_WRONLY); os.close(fd); return p
    except FileExistsError: return None
def unlock(p):
    if not p: return
    if isinstance(p, tuple) and p[0] == "redis": _LOCK.release(p); return
    p.unlink(missing_ok=True)

def process(wo_path):
    wo = json.loads(wo_path.read_text())
    if wo.get("execution_method", "duoplus_rpa") != "duoplus_rpa": return   # not ours
    working = R.claim(wo_path)
    if not working: return
    wid = wo["work_order_id"]; pid = wo["profile_id"]; wf = WFS[wo["workflow_id"]]
    profile = PROFILES.get(pid, {})
    image_id = PHONES.get(wo["phone_id"], wo["phone_id"])          # local label -> real DuoPlus id
    rep = {"work_order_id": wid, "profile_id": pid, "workflow_id": wo["workflow_id"]}
    ok, key, approval_path = R.gate(wo, wf, working, rep, profile)
    if not ok: return
    plock = lock(f"phone_{wo['phone_id']}")
    if not plock:
        R.requeue(working); print(f"  {wid}: phone busy — requeued"); return
    prlock = lock(f"profile_{pid}")
    if not prlock:                                  # profile in use elsewhere — do NOT proceed
        unlock(plock); R.requeue(working); print(f"  {wid}: profile busy — requeued"); return
    try:
        DEV.phone_status(image_id); DEV.power_on(image_id)
        bind = DEV.bind_proxy_location(profile, profile.get("proxy", {}), profile.get("location", {}))
        print(f"  {wid}: proxy/location bound via API -> {bind['location']}")
        DEV.switch_profile(image_id, pid)
        if not DEV.verify_profile(image_id, profile):
            print(f"  {wid}: VERIFY FAILED — abort (wrong-account guard)")
            R.finish(working, "failed", {**rep, "reason": "profile verify failed", "stage": "verify"}); return
        if not DRY:
            lo, hi = POLICY["defaults"]["intra_workflow_jitter_seconds"]; time.sleep(random.randint(lo, hi))
        ev_before = R.evidence(wo, "before")
        landed, report = DEV.run_workflow(image_id, wf.get("duoplus_template_id"), profile, wo.get("task_params"))
        if not landed:
            print(f"  {wid}: workflow did not land -> failed (no blind retry)")
            R.finish(working, "failed", {**rep, "reason": "did not land", "stage": "execute", "evidence": [ev_before]}); return
        ev_after = R.evidence(wo, "after"); R.mark_processed(key)
        if approval_path: R.consume_approval(approval_path)
        print(f"  {wid}: {wo['workflow_id']} -> DONE (confirmed{', approval consumed' if approval_path else ''})")
        R.finish(working, "done", {**rep, "landed": True, "evidence": [ev_before, ev_after], "task_report": report})
    except Exception as e:                                   # one bad API call must not kill the batch
        print(f"  {wid}: ERROR — {type(e).__name__}: {e}")
        R.finish(working, "failed", {**rep, "reason": f"{type(e).__name__}: {e}", "stage": "execute"})
    finally:
        unlock(prlock); unlock(plock)

def main():
    d = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else "today"
    print(f"[duoplus-rpa] client={CLIENT} date={d} dry={DRY} | kill_switch={'ON' if pol.kill_switch_active(POLICY) else 'off'}")
    wos = R.inbox()
    if not wos: print("  inbox empty — run scripts/gen_workorders.py first")
    for wo_path in wos: process(wo_path)
    print("[duoplus-rpa] done")

if __name__ == "__main__": main()
