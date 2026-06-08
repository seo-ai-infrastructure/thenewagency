#!/usr/bin/env python3
"""Phase 0: provision a per-client CloakBrowser persona profile `<client>-cb-agent`.

Registers it in clients/<id>/browser/profiles.yaml (creating the browser area + seeding
workflows.yaml/policy.yaml/upload-scripts from the example client if absent) and creates the
persistent user_data_dir. After this, log in ONCE per platform via the CloakBrowser Manager GUI;
cookies persist so tasks never re-login.

  python scripts/provision_cb_profile.py --client <id> [--proxy-ref proxy_xxx]
"""
import sys, os, shutil, pathlib, yaml
ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT/"clients"/"example-hvac-client"/"browser"
SOCIAL_WFS = ["facebook_post", "reddit_post", "quora_answer_post", "linkedin_post",
              "tiktok_upload", "youtube_upload",
              "reddit_comment", "facebook_comment", "linkedin_comment", "youtube_comment",
              "pinterest_pin", "eventbrite_create", "patch_article", "nextdoor_post"]

def arg(name, default=None):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv else default

def provision(client, proxy_ref=None, root=ROOT):
    root = pathlib.Path(root)
    template = root/"clients"/"example-hvac-client"/"browser"
    proxy_ref = proxy_ref or f"proxy_{client.replace('-', '_')}_01"
    pid = f"{client}-cb-agent"
    browser = root/"clients"/client/"browser"
    for d in ("approvals/pending", "approvals/approved", "approvals/consumed",
              "approvals/rejected", "logs", "scripts"):
        (browser/d).mkdir(parents=True, exist_ok=True)
    # seed config + upload scripts from the template client if this one has none
    for rel in ("workflows.yaml", "policy.yaml", "scripts/tiktok_upload.py", "scripts/youtube_upload.py"):
        dst = browser/rel
        if not dst.exists() and (template/rel).exists() and template != browser:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(template/rel, dst)

    prof_path = browser/"profiles.yaml"
    data = yaml.safe_load(prof_path.read_text()) if prof_path.exists() else {"version": 1, "profiles": []}
    profiles = data.setdefault("profiles", [])
    if any(p.get("profile_id") == pid for p in profiles):
        return pid, False, f"{pid} already registered"
    profiles.append({"profile_id": pid, "fingerprint_id": f"cloak_fp_{pid}",
                     "user_data_dir": f"~/cloak-profiles/{pid}", "proxy_ref": proxy_ref,
                     "expected_account": "REPLACE-after-first-login",
                     "verify_url": "https://www.facebook.com/",
                     "allowed_workflows": list(SOCIAL_WFS), "paused": False})
    prof_path.write_text(yaml.safe_dump(data, sort_keys=False))
    return pid, True, f"registered {pid}"

def main():
    client = arg("--client")
    if not client:
        raise SystemExit("--client <id> required")
    pid, created, msg = provision(client, arg("--proxy-ref"))
    print(f"[provision] {msg} -> clients/{client}/browser/profiles.yaml")
    if created:
        udd = pathlib.Path(os.path.expanduser(f"~/cloak-profiles/{pid}")); udd.mkdir(parents=True, exist_ok=True)
        print(f"  user_data_dir: {udd}")
        print(f"  NEXT: set the proxy env var in .env, then log in ONCE to Facebook/Reddit/TikTok/"
              f"Quora/LinkedIn/YouTube via the CloakBrowser Manager GUI; then set expected_account "
              f"+ verify_url in profiles.yaml so the wrong-account guard can confirm identity.")

if __name__ == "__main__":
    main()
