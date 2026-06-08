#!/usr/bin/env python3
"""Shared scheduler. Reads a client's subsystem config areas and drops work orders into the
inbox of the subsystem that owns each workflow's execution_method:
   duoplus_rpa         -> automations/duoplus-rpa-orchestrator/inbox
   google_business_api -> automations/zernio-publisher/inbox
   cloakbrowser        -> automations/cloakbrowser-runner/inbox
Areas: clients/<id>/rpa (phone + GBP) and clients/<id>/browser (cloakbrowser), if present.
  python scripts/gen_workorders.py --date YYYY-MM-DD [--client <id>]"""
import sys, json, datetime, pathlib, yaml
ROOT = pathlib.Path(__file__).resolve().parents[1]
CLIENT = sys.argv[sys.argv.index("--client")+1] if "--client" in sys.argv else "example-hvac-client"
DATESTR = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else None
date = datetime.date.fromisoformat(DATESTR) if DATESTR else datetime.date.today()
dow = date.strftime("%A").lower()
week = f"{date.isocalendar().year}-W{date.isocalendar().week:02d}"

INBOX = {"duoplus_rpa":         ROOT/"automations"/"duoplus-rpa-orchestrator"/"inbox",
         "google_business_api": ROOT/"automations"/"zernio-publisher"/"inbox",
         "cloakbrowser":        ROOT/"automations"/"cloakbrowser-runner"/"inbox",
         "wordpress_api":       ROOT/"automations"/"wordpress-publisher"/"inbox",
         "cloudflare_edge":     ROOT/"automations"/"edge-deployer"/"inbox",
         "castopod_api":        ROOT/"automations"/"podcast-publisher"/"inbox"}
n = {k: 0 for k in INBOX}
order = 0

def load(area, name):
    p = ROOT/"clients"/CLIENT/area/name
    return yaml.safe_load(p.read_text()) if p.exists() else None

def due(s):
    if not s.get("active", True): return False
    if s["frequency"] == "daily": return True
    if s["frequency"] == "weekly": return s.get("day_of_week", "monday").lower() == dow
    if s["frequency"] == "monthly": return date.day == s.get("day_of_month", 1)
    return False

def approval_ref(area, scope, wfid, period):
    return str(ROOT/"clients"/CLIENT/area/"approvals"/"approved"/f"{scope}__{wfid}__{period}.json")

def write(method, wo):
    INBOX[method].mkdir(parents=True, exist_ok=True)
    (INBOX[method]/f"{wo['work_order_id']}.json").write_text(json.dumps(wo, indent=2))
    n[method] += 1

# --- rpa area: phone (duoplus_rpa) + GBP (google_business_api) ---
rpa_sched = load("rpa", "schedules.yaml")
if rpa_sched:
    wfs = {w["workflow_id"]: w for w in load("rpa", "workflows.yaml")["workflows"]}
    profiles = {p["profile_id"]: p for p in load("rpa", "profiles.yaml")["profiles"]}
    gb = load("rpa", "google_business.yaml") or {}
    for s in rpa_sched["schedules"]:
        if not due(s): continue
        wf = wfs[s["workflow_id"]]; method = wf.get("execution_method", "duoplus_rpa")
        period = week if s["frequency"] != "daily" else date.isoformat()
        if method == "duoplus_rpa":
            for pid in s.get("profiles", []):
                prof = profiles.get(pid, {})
                write(method, {"work_order_id": f"wo_dp_{date:%Y%m%d}_{s['schedule_id']}_{pid}",
                    "execution_method": method, "order_index": order, "client_id": CLIENT, "profile_id": pid,
                    "phone_id": prof.get("phone_id", "phone_unknown"), "workflow_id": s["workflow_id"],
                    "period": period, "customer_facing": wf.get("customer_facing", False),
                    "approval_ref": approval_ref("rpa", pid, s["workflow_id"], period) if wf.get("approval_required") else None,
                    "task_params": s.get("task_params", {})})
                order += 1
        elif method == "google_business_api":
            acct = gb.get("account_id", "REPLACE")
            for loc in s.get("gbp_locations", [gb.get("default_location_id", "locations/REPLACE")]):
                scope = str(loc).replace("/", "_")
                write(method, {"work_order_id": f"wo_gbp_{date:%Y%m%d}_{s['schedule_id']}_{scope}",
                    "execution_method": method, "order_index": order, "client_id": CLIENT, "profile_id": scope,
                    "account_id": acct, "location_id": loc, "workflow_id": s["workflow_id"],
                    "period": period, "customer_facing": wf.get("customer_facing", True),
                    "approval_ref": approval_ref("rpa", scope, s["workflow_id"], period) if wf.get("approval_required") else None})
                order += 1

# --- browser area: cloakbrowser ---
br_sched = load("browser", "schedules.yaml")
if br_sched:
    wfs = {w["workflow_id"]: w for w in load("browser", "workflows.yaml")["workflows"]}
    for s in br_sched["schedules"]:
        if not due(s): continue
        wf = wfs[s["workflow_id"]]; period = date.isoformat()
        for pid in s.get("profiles", []):
            write("cloakbrowser", {"work_order_id": f"wo_br_{date:%Y%m%d}_{s['schedule_id']}_{pid}",
                "execution_method": "cloakbrowser", "order_index": order, "client_id": CLIENT, "profile_id": pid,
                "workflow_id": s["workflow_id"], "period": period,
                "customer_facing": wf.get("customer_facing", False),
                "approval_ref": approval_ref("browser", pid, s["workflow_id"], period) if wf.get("approval_required") else None,
                "task_params": s.get("task_params", {})})
            order += 1

# --- web area: API content publishers (wordpress_api / cloudflare_edge / castopod_api) ---
# Content-driven (not profile-driven): a schedule names target scopes (slugs) to publish this period.
web_sched = load("web", "schedules.yaml")
if web_sched:
    wfs = {w["workflow_id"]: w for w in load("web", "workflows.yaml")["workflows"]}
    for s in web_sched["schedules"]:
        if not due(s): continue
        wf = wfs[s["workflow_id"]]; method = wf["execution_method"]; period = date.isoformat()
        for scope in s.get("targets", []):
            write(method, {"work_order_id": f"wo_web_{date:%Y%m%d}_{s['schedule_id']}_{scope}",
                "execution_method": method, "order_index": order, "client_id": CLIENT, "profile_id": scope,
                "workflow_id": s["workflow_id"], "period": period,
                "customer_facing": wf.get("customer_facing", True),
                "approval_ref": approval_ref("web", scope, s["workflow_id"], period) if wf.get("approval_required") else None,
                "task_params": s.get("task_params", {})})
            order += 1

print(f"[scheduler] {CLIENT} {date} ({dow}, {week})")
for m in INBOX: print(f"  -> {m:20s}: {n[m]} work order(s)")
