#!/usr/bin/env python3
"""Cloudflare edge deployer — ship approved HTML + Schema.org JSON-LD to a Worker (AIO-speed).
Area: clients/<id>/web. Gated: only deploys a hashed, human-approved artifact.
  python run.py [--dry-run] [--client <id>]"""
import sys, os, json, pathlib, yaml
HERE = pathlib.Path(__file__).resolve().parent
def root(s):
    for d in [s, *s.parents]:
        if (d/"lib").exists(): return d
    raise SystemExit("root not found")
ROOT = root(HERE); sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()
from lib.rate_limiter import RateLimiter
from lib.orchestration import WorkOrderRunner
from lib import policy as pol
from integrations.cloudflare.client import CloudflareClient

DRY    = "--dry-run" in sys.argv
CLIENT = sys.argv[sys.argv.index("--client")+1] if "--client" in sys.argv else "example-hvac-client"
WEB    = ROOT/"clients"/CLIENT/"web"
POLICY = pol.load(WEB)
WFS = {w["workflow_id"]: w for w in yaml.safe_load((WEB/"workflows.yaml").read_text())["workflows"]}
RL = RateLimiter(ROOT/".cloudflare_rate_state", min_interval=0.5, fake=DRY)
CF = CloudflareClient(RL, fake=DRY)
R  = WorkOrderRunner(HERE, ROOT, WEB, POLICY, notify=not DRY)

def process(wo_path):
    wo = json.loads(wo_path.read_text())
    if wo.get("execution_method") != "cloudflare_edge": return     # not ours
    working = R.claim(wo_path)
    if not working: return
    wid = wo["work_order_id"]; wf = WFS[wo["workflow_id"]]
    rep = {"work_order_id": wid, "scope_id": wo["profile_id"], "workflow_id": wo["workflow_id"],
           "execution": "cloudflare_edge"}
    try:
        ok, key, approval_path = R.gate(wo, wf, working, rep, None)
        if not ok: return
        content = {}
        if approval_path:
            content = json.loads(pathlib.Path(approval_path).read_text()).get("content") or {}
        html = content.get("text", "")
        script_name = content.get("slug") or wo["profile_id"]
        account_id = os.environ.get("CF_ACCOUNT_ID", ""); token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
        ev_before = R.evidence(wo, "before")
        if not DRY and not (account_id and token and html):
            R.finish(working, "failed", {**rep, "reason": "Cloudflare creds (CF_ACCOUNT_ID / "
                     "CLOUDFLARE_API_TOKEN) or HTML missing", "stage": "config", "evidence": [ev_before]})
            print(f"  {wid}: CF creds/html missing -> failed"); return
        landed, resp = CF.deploy_html(account_id or "acct", token or "tok", script_name, html or "<!--empty-->")
        if not landed:
            why = (resp.get("errors") or [{}])[0].get("message", "not landed") if isinstance(resp, dict) else "not landed"
            R.finish(working, "failed", {**rep, "reason": why, "stage": "execute", "evidence": [ev_before]})
            print(f"  {wid}: edge deploy did not land -> failed ({why})"); return
        ev_after = R.evidence(wo, "after"); R.mark_processed(key)
        if approval_path: R.consume_approval(approval_path)
        print(f"  {wid}: {wo['workflow_id']} via Cloudflare -> DONE (worker {script_name})")
        R.finish(working, "done", {**rep, "landed": True, "script": script_name,
                 "evidence": [ev_before, ev_after], "task_report": resp})
    except Exception as e:    # never leave a claimed work order stuck in working/
        if working.exists():
            R.finish(working, "failed", {**rep, "reason": f"unexpected error: {type(e).__name__}: {e}",
                     "stage": "exception"})
        print(f"  {wid}: unexpected error -> failed ({type(e).__name__}: {e})")

def main():
    print(f"[edge-deployer] client={CLIENT} dry={DRY} | "
          f"kill_switch={'ON' if pol.kill_switch_active(POLICY) else 'off'}")
    wos = R.inbox()
    if not wos: print("  inbox empty — run scripts/gen_workorders.py first")
    for wo_path in wos: process(wo_path)
    print("[edge-deployer] done")

if __name__ == "__main__": main()
