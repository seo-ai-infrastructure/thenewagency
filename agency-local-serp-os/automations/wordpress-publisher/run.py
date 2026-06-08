#!/usr/bin/env python3
"""WordPress publisher — REST API + Application Password (self-hosted, ~1 site per client).
Area: clients/<id>/web. Like zernio-publisher but for owned long-form content. Gated: only
publishes a hashed, human-approved article artifact; never alters approved copy.
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
from integrations.wordpress.client import WordPressClient

DRY    = "--dry-run" in sys.argv
CLIENT = sys.argv[sys.argv.index("--client")+1] if "--client" in sys.argv else "example-hvac-client"
WEB    = ROOT/"clients"/CLIENT/"web"
POLICY = pol.load(WEB)
WFS = {w["workflow_id"]: w for w in yaml.safe_load((WEB/"workflows.yaml").read_text())["workflows"]}
_cfg = ROOT/"clients"/CLIENT/"config"/"wordpress.yaml"
WPCFG = yaml.safe_load(_cfg.read_text()) if _cfg.exists() else {}
RL = RateLimiter(ROOT/".wordpress_rate_state", min_interval=0.5, fake=DRY)
WP = WordPressClient(RL, fake=DRY)
R  = WorkOrderRunner(HERE, ROOT, WEB, POLICY, notify=not DRY)

def process(wo_path):
    wo = json.loads(wo_path.read_text())
    if wo.get("execution_method") != "wordpress_api": return     # not ours
    working = R.claim(wo_path)
    if not working: return
    wid = wo["work_order_id"]; wf = WFS[wo["workflow_id"]]
    rep = {"work_order_id": wid, "scope_id": wo["profile_id"], "workflow_id": wo["workflow_id"],
           "execution": "wordpress_api"}
    try:
        ok, key, approval_path = R.gate(wo, wf, working, rep, None)   # no profile for API
        if not ok: return
        content = {}
        if approval_path:
            content = json.loads(pathlib.Path(approval_path).read_text()).get("content") or {}
        title  = content.get("title") or (content.get("text", "")[:60] or "Untitled")
        body   = content.get("text", "")
        status = content.get("status") or WPCFG.get("default_status", "publish")
        api_url, username = WPCFG.get("api_url"), WPCFG.get("username")
        app_password = os.environ.get(WPCFG.get("app_password_env", ""), "")
        ev_before = R.evidence(wo, "before")
        if not DRY and not (api_url and username and app_password):
            miss = WPCFG.get("app_password_env", "WP_APP_PASSWORD_*")
            R.finish(working, "failed", {**rep, "reason": f"WordPress config/credential missing "
                     f"(config/wordpress.yaml + env {miss})", "stage": "config", "evidence": [ev_before]})
            print(f"  {wid}: WP config/creds missing -> failed"); return
        landed, resp = WP.create_post(api_url or "https://fake.local", username or "fake",
                                      app_password or "fake", title=title, content=body, status=status,
                                      slug=content.get("slug"), excerpt=content.get("excerpt"),
                                      categories=content.get("categories"), tags=content.get("tags"),
                                      meta=content.get("meta"))
        if not landed:
            why = resp.get("message") or resp.get("code") or "not landed"
            R.finish(working, "failed", {**rep, "reason": why, "stage": "execute", "evidence": [ev_before]})
            print(f"  {wid}: WP publish did not land -> failed ({why})"); return
        ev_after = R.evidence(wo, "after"); R.mark_processed(key)
        if approval_path: R.consume_approval(approval_path)
        print(f"  {wid}: {wo['workflow_id']} via WordPress -> DONE (post {resp.get('id')})")
        R.finish(working, "done", {**rep, "landed": True, "post_id": resp.get("id"),
                 "link": resp.get("link"), "evidence": [ev_before, ev_after], "task_report": resp})
    except Exception as e:    # never leave a claimed work order stuck in working/
        if working.exists():
            R.finish(working, "failed", {**rep, "reason": f"unexpected error: {type(e).__name__}: {e}",
                     "stage": "exception"})
        print(f"  {wid}: unexpected error -> failed ({type(e).__name__}: {e})")

def main():
    print(f"[wordpress-publisher] client={CLIENT} dry={DRY} | "
          f"kill_switch={'ON' if pol.kill_switch_active(POLICY) else 'off'}")
    wos = R.inbox()
    if not wos: print("  inbox empty — run scripts/gen_workorders.py first")
    for wo_path in wos: process(wo_path)
    print("[wordpress-publisher] done")

if __name__ == "__main__": main()
