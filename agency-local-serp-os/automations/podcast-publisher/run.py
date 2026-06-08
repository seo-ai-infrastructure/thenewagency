#!/usr/bin/env python3
"""Castopod podcast publisher — publish an approved episode; Castopod emits the RSS that
Spotify/Apple/YouTube subscribe to. Area: clients/<id>/web. Gated.
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
from integrations.castopod.client import CastopodClient

DRY    = "--dry-run" in sys.argv
CLIENT = sys.argv[sys.argv.index("--client")+1] if "--client" in sys.argv else "example-hvac-client"
WEB    = ROOT/"clients"/CLIENT/"web"
POLICY = pol.load(WEB)
WFS = {w["workflow_id"]: w for w in yaml.safe_load((WEB/"workflows.yaml").read_text())["workflows"]}
_cfg = ROOT/"clients"/CLIENT/"config"/"castopod.yaml"
CASTCFG = yaml.safe_load(_cfg.read_text()) if _cfg.exists() else {}
RL = RateLimiter(ROOT/".castopod_rate_state", min_interval=0.5, fake=DRY)
CAST = CastopodClient(RL, fake=DRY)
R  = WorkOrderRunner(HERE, ROOT, WEB, POLICY, notify=not DRY)

def process(wo_path):
    wo = json.loads(wo_path.read_text())
    if wo.get("execution_method") != "castopod_api": return        # not ours
    working = R.claim(wo_path)
    if not working: return
    wid = wo["work_order_id"]; wf = WFS[wo["workflow_id"]]
    rep = {"work_order_id": wid, "scope_id": wo["profile_id"], "workflow_id": wo["workflow_id"],
           "execution": "castopod_api"}
    try:
        ok, key, approval_path = R.gate(wo, wf, working, rep, None)
        if not ok: return
        content = {}
        if approval_path:
            content = json.loads(pathlib.Path(approval_path).read_text()).get("content") or {}
        title = content.get("title") or "Episode"
        audio_url = content.get("audio_url", "")
        desc = content.get("description") or content.get("text", "")
        base = os.environ.get("CASTOPOD_API_BASE", ""); token = os.environ.get("CASTOPOD_API_TOKEN", "")
        podcast_id = CASTCFG.get("podcast_id", "")
        ev_before = R.evidence(wo, "before")
        if not DRY and not (base and token and podcast_id and audio_url):
            R.finish(working, "failed", {**rep, "reason": "Castopod config/creds (CASTOPOD_API_BASE/"
                     "TOKEN, config/castopod.yaml podcast_id) or audio_url missing", "stage": "config",
                     "evidence": [ev_before]})
            print(f"  {wid}: Castopod config/creds/audio missing -> failed"); return
        landed, resp = CAST.create_episode(base or "https://fake.local", token or "tok",
                                           podcast_id or "pod", title, audio_url or "https://fake.local/a.mp3",
                                           description=desc)
        if not landed:
            why = resp.get("error") or "not landed" if isinstance(resp, dict) else "not landed"
            R.finish(working, "failed", {**rep, "reason": why, "stage": "execute", "evidence": [ev_before]})
            print(f"  {wid}: podcast publish did not land -> failed ({why})"); return
        ev_after = R.evidence(wo, "after"); R.mark_processed(key)
        if approval_path: R.consume_approval(approval_path)
        print(f"  {wid}: {wo['workflow_id']} via Castopod -> DONE (episode {resp.get('id')})")
        R.finish(working, "done", {**rep, "landed": True, "episode_id": resp.get("id"),
                 "evidence": [ev_before, ev_after], "task_report": resp})
    except Exception as e:    # never leave a claimed work order stuck in working/
        if working.exists():
            R.finish(working, "failed", {**rep, "reason": f"unexpected error: {type(e).__name__}: {e}",
                     "stage": "exception"})
        print(f"  {wid}: unexpected error -> failed ({type(e).__name__}: {e})")

def main():
    print(f"[podcast-publisher] client={CLIENT} dry={DRY} | "
          f"kill_switch={'ON' if pol.kill_switch_active(POLICY) else 'off'}")
    wos = R.inbox()
    if not wos: print("  inbox empty — run scripts/gen_workorders.py first")
    for wo_path in wos: process(wo_path)
    print("[podcast-publisher] done")

if __name__ == "__main__": main()
