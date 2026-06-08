#!/usr/bin/env python3
"""Ad-hoc: enqueue a browser task for one agent. (The mostly-on-demand path.)
  python scripts/run_browser_task.py <client> <profile_id> <workflow_id> [--param k=v ...]
Then execute: python automations/cloakbrowser-runner/run.py [--dry-run]"""
import sys, json, datetime, pathlib, yaml
ROOT = pathlib.Path(__file__).resolve().parents[1]
client, profile_id, workflow_id = sys.argv[1], sys.argv[2], sys.argv[3]
params = {}
for i, a in enumerate(sys.argv):
    if a == "--param" and i+1 < len(sys.argv):
        k, _, v = sys.argv[i+1].partition("="); params[k] = v
DATA = ROOT/"clients"/client/"browser"
wfs = {w["workflow_id"]: w for w in yaml.safe_load((DATA/"workflows.yaml").read_text())["workflows"]}
wf = wfs[workflow_id]
period = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
inbox = ROOT/"automations"/"cloakbrowser-runner"/"inbox"; inbox.mkdir(parents=True, exist_ok=True)
approval_ref = None
if wf.get("approval_required"):
    approval_ref = str(DATA/"approvals"/"approved"/f"{profile_id}__{workflow_id}__{period}.json")
wo = {"work_order_id": f"wo_br_adhoc_{period}_{profile_id}", "execution_method": "cloakbrowser", "client_id": client,
      "order_index": 0, "profile_id": profile_id, "workflow_id": workflow_id, "period": period,
      "customer_facing": wf.get("customer_facing", False), "approval_ref": approval_ref,
      "task_params": params}
out = inbox/f"{wo['work_order_id']}.json"; out.write_text(json.dumps(wo, indent=2))
print(f"enqueued {out.name} -> cloakbrowser-runner/inbox  (params: {params or 'none'})")
if approval_ref: print(f"  NOTE: gated workflow — will be HELD until approval exists at\n        {approval_ref}")
