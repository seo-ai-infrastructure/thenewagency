#!/usr/bin/env python3
"""CloakBrowser runner — persistent fingerprinted browser identities (desktop web).
Separate subsystem from DuoPlus RPA and Zernio. Shares only lib/.
  python run.py [--dry-run] [--client <id>]   (default client: agency)"""
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
from integrations.cloakbrowser.client import CloakBrowserClient

DRY    = "--dry-run" in sys.argv
CLIENT = sys.argv[sys.argv.index("--client")+1] if "--client" in sys.argv else "agency"
DATA   = ROOT/"clients"/CLIENT/"browser"          # per-subsystem client data (approvals/logs here)
LOCKS  = HERE/"state"/"locks"
POLICY = pol.load(DATA)
PROFILES = {p["profile_id"]: p for p in yaml.safe_load((DATA/"profiles.yaml").read_text())["profiles"]}
WFS = {w["workflow_id"]: w for w in yaml.safe_load((DATA/"workflows.yaml").read_text())["workflows"]}
if os.environ.get("REDIS_HOST") and not DRY:        # dry-run stays offline (file locks, no network)
    from lib.redis_backends import get_redis, RedisRateLimiter, RedisLock
    _RC = get_redis(); RL = RedisRateLimiter(_RC, max_per_sec=2, key="cloak:ratelimit"); _LOCK = RedisLock(_RC)
else:
    RL = RateLimiter(ROOT/".cloak_rate_state", min_interval=0.5, fake=DRY); _LOCK = None
BROWSER = CloakBrowserClient(RL, fake=DRY)
R = WorkOrderRunner(HERE, ROOT, DATA, POLICY, notify=not DRY)

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
    if wo.get("execution_method") != "cloakbrowser": return     # not ours
    working = R.claim(wo_path)
    if not working: return
    wid = wo["work_order_id"]; pid = wo["profile_id"]; wf = WFS[wo["workflow_id"]]
    profile = PROFILES.get(pid)
    if profile is not None:
        profile = {**profile, "client_id": CLIENT, "browser_data_dir": str(DATA)}
    rep = {"work_order_id": wid, "profile_id": pid, "workflow_id": wo["workflow_id"], "surface": "cloakbrowser"}
    if profile is None:
        R.finish(working, "failed", {**rep, "reason": f"profile {pid} not found", "stage": "config"})
        print(f"  {wid}: profile {pid} not found -> failed")
        return
    ok, key, approval_path = R.gate(wo, wf, working, rep, profile)
    if not ok: return
    plock = lock(f"browser_{pid}")                              # one context per profile
    if not plock:
        R.requeue(working); print(f"  {wid}: {pid} busy — requeued"); return
    ctx = None
    try:
        ctx = BROWSER.launch(profile)
        print(f"  {wid}: launched {pid} (proxy={profile.get('proxy_ref')}, persistent session)")
        if not BROWSER.verify_profile(ctx, profile):
            print(f"  {wid}: VERIFY FAILED — abort (wrong-account guard)")
            R.finish(working, "failed", {**rep, "reason": "profile verify failed", "stage": "verify"}); return
        if not DRY:
            lo, hi = POLICY["defaults"]["intra_workflow_jitter_seconds"]; time.sleep(random.randint(lo, hi))
        ev_before = R.evidence(wo, "before")
        params = wo.get("task_params", {})
        if approval_path:                                       # gated action: use approved text
            params = {**params, **(json.loads(pathlib.Path(approval_path).read_text()).get("content") or {})}
        if wf.get("kind") == "agent_task":
            needs_confirm = bool(wf.get("customer_facing") or approval_path)
            landed, report = BROWSER.run_agent_task(ctx, wf.get("agent_goal", ""), params,
                                                    require_success=needs_confirm)
        else:
            script_abs = str(DATA/wf["script"]) if wf.get("script") else ""   # resolve under client browser dir
            landed, report = BROWSER.run_script(ctx, script_abs, params)
        if not landed:
            print(f"  {wid}: task did not complete -> failed (no blind retry)")
            R.finish(working, "failed", {**rep, "reason": "did not complete", "stage": "execute", "evidence": [ev_before]}); return
        ev_after = R.evidence(wo, "after"); R.mark_processed(key)
        if approval_path: R.consume_approval(approval_path)
        print(f"  {wid}: {wo['workflow_id']} -> DONE ({wf.get('kind')}{', approval consumed' if approval_path else ''})")
        R.finish(working, "done", {**rep, "landed": True, "evidence": [ev_before, ev_after], "task_report": report})
    except Exception as e:    # launch/verify can raise -> never leave the work order stuck in working/
        if working.exists():
            R.finish(working, "failed", {**rep, "reason": f"unexpected error: {type(e).__name__}: {e}",
                                         "stage": "exception"})
        print(f"  {wid}: unexpected error -> failed ({type(e).__name__}: {e})")
    finally:
        if ctx is not None: BROWSER.close(ctx)
        unlock(plock)

def main():
    print(f"[cloakbrowser] client={CLIENT} dry={DRY} | kill_switch={'ON' if pol.kill_switch_active(POLICY) else 'off'}")
    wos = R.inbox()
    if not wos: print("  inbox empty — enqueue with scripts/run_browser_task.py or scripts/gen_workorders.py")
    for wo_path in wos: process(wo_path)
    print("[cloakbrowser] done")

if __name__ == "__main__": main()
