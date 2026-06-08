#!/usr/bin/env python3
"""Daily GBP poster — publish the ONE approved post scheduled for today (period = date) through the
gated Zernio publisher. Idempotent: at most one GBP post per profile per day. Run once a day.

  python scripts/post_daily_gbp.py --client example-hvac-client [--date YYYY-MM-DD] [--dry-run]
"""
import sys, os, json, datetime, subprocess, pathlib, yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()


def main():
    def arg(n, d): return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
    client = arg("--client", "example-hvac-client")
    date = arg("--date", datetime.date.today().isoformat())
    dry = "--dry-run" in sys.argv

    gb = yaml.safe_load((ROOT / "clients" / client / "rpa" / "google_business.yaml").read_text())
    account_id = gb["account_id"]; location_id = str(gb["default_location_id"]); scope = location_id.replace("/", "_")
    approved = ROOT / "clients" / client / "rpa" / "approvals" / "approved" / f"{scope}__gbp_post_publish__{date}.json"
    if not approved.exists():
        print(f"[post_daily_gbp] no approved GBP post scheduled for {date} — nothing to post.")
        return

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    wo = {"execution_method": "google_business_api", "client_id": client, "profile_id": scope,
          "account_id": account_id, "location_id": location_id, "workflow_id": "gbp_post_publish",
          "period": date, "order_index": 0, "customer_facing": True, "manual": True, "issued_by": "daily",
          "work_order_id": f"wo_gbp_{ts}_{scope}", "approval_ref": str(approved)}
    inbox = ROOT / "automations" / "zernio-publisher" / "inbox"; inbox.mkdir(parents=True, exist_ok=True)
    wop = inbox / (wo["work_order_id"] + ".json")
    tmp = wop.with_suffix(".json.tmp"); tmp.write_text(json.dumps(wo, indent=2)); tmp.replace(wop)

    print(f"[post_daily_gbp] queued {date} post -> running publisher{' (dry-run)' if dry else ' LIVE'}")
    cmd = [sys.executable, str(ROOT / "automations" / "zernio-publisher" / "run.py"), "--client", client]
    if dry:
        cmd.append("--dry-run")
    env = dict(os.environ); env["REDIS_HOST"] = ""        # file limiter, no Redis dependency for the post
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0:                                 # surface a crashed publisher to the caller/cron
        print(f"[post_daily_gbp] publisher exited {r.returncode} — check zernio-publisher/failed/ + history")
        sys.exit(r.returncode)


if __name__ == "__main__":
    main()
