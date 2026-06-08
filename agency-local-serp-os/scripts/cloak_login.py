#!/usr/bin/env python3
"""Log a CloakBrowser profile into its account(s) ONCE, headed, so automated runs reuse the
persistent session (no re-login). Launches the profile's stealth browser through its proxy,
waits while you sign in, then saves cookies into the profile's user_data_dir.

  python scripts/cloak_login.py <profile_id> [--client agency] [--url https://...]
"""
import sys, os, pathlib, yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()

if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
    raise SystemExit("usage: python scripts/cloak_login.py <profile_id> [--client agency] [--url URL]")
pid = sys.argv[1]
client = sys.argv[sys.argv.index("--client")+1] if "--client" in sys.argv else "agency"
url = sys.argv[sys.argv.index("--url")+1] if "--url" in sys.argv else "about:blank"

profiles = yaml.safe_load((ROOT/"clients"/client/"browser"/"profiles.yaml").read_text())["profiles"]
prof = next((p for p in profiles if p["profile_id"] == pid), None)
if not prof:
    raise SystemExit(f"profile '{pid}' not found in clients/{client}/browser/profiles.yaml")

import cloakbrowser
udd = pathlib.Path(os.path.expanduser(prof["user_data_dir"])); udd.mkdir(parents=True, exist_ok=True)
ref = prof.get("proxy_ref")
proxy = os.environ.get(ref.upper()) if ref else None
if ref and not proxy:
    raise SystemExit(f"proxy_ref '{ref}' set but env {ref.upper()} is empty — add it to .env")

print(f"Launching '{pid}' headed (proxy={ref}, data_dir={udd}). Log in, then return here.")
kw = dict(user_data_dir=str(udd), proxy=proxy, humanize=True, headless=False)
try:
    ctx = cloakbrowser.launch_persistent_context(geoip=True, **kw)
except ImportError:
    ctx = cloakbrowser.launch_persistent_context(geoip=False, **kw)
(ctx.pages[0] if ctx.pages else ctx.new_page()).goto(url)
input("\n>> Sign in to the account(s) in the browser window, then press Enter here to save & close... ")
ctx.close()
print(f"Session saved to {udd}. Automated runs for '{pid}' will reuse it.")
