#!/usr/bin/env python3
"""Open a CloakBrowser profile headed for a ONE-TIME manual login, then auto-save when you're
signed in — no terminal keypress needed (unlike cloak_login.py). Polls for the platform auth
cookie and closes cleanly once detected, persisting cookies to the profile's user_data_dir so
automated runs reuse the session.

  python scripts/cloak_login_open.py <profile_id> [--client agency] [--url URL]
                                     [--cookie reddit_session] [--timeout 900]
"""
import sys, os, re, time, pathlib, yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()


def arg(n, d=None):
    return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d


if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
    raise SystemExit("usage: python scripts/cloak_login_open.py <profile_id> [--client c] [--url URL] [--cookie name] [--timeout s]")
pid = sys.argv[1]
client = arg("--client", "agency")
url = arg("--url", "https://www.reddit.com/login")
cookie_name = arg("--cookie", "reddit_session")
timeout = int(arg("--timeout", "900"))

profiles = yaml.safe_load((ROOT / "clients" / client / "browser" / "profiles.yaml").read_text())["profiles"]
prof = next((p for p in profiles if p["profile_id"] == pid), None)
if not prof:
    raise SystemExit(f"profile '{pid}' not found in clients/{client}/browser/profiles.yaml")

import cloakbrowser
udd = pathlib.Path(os.path.expanduser(prof["user_data_dir"])); udd.mkdir(parents=True, exist_ok=True)
ref = prof.get("proxy_ref")
proxy = os.environ.get(ref.upper()) if ref else None
if ref and not proxy:
    raise SystemExit(f"proxy_ref '{ref}' set but env {ref.upper()} is empty — add it to .env or clear proxy_ref")

print(f"[cloak-login] launching '{pid}' headed (proxy={ref or 'none'}, data_dir={udd})", flush=True)
kw = dict(user_data_dir=str(udd), proxy=proxy, humanize=True, headless=False)
try:
    ctx = cloakbrowser.launch_persistent_context(geoip=True, **kw)
except ImportError:
    ctx = cloakbrowser.launch_persistent_context(geoip=False, **kw)
page = ctx.pages[0] if ctx.pages else ctx.new_page()
try:
    page.goto(url)
except Exception as e:
    print(f"[cloak-login] nav warn: {e}", flush=True)

keep_open = "--keep-open" in sys.argv
deadline = time.time() + timeout
found = False
if keep_open:
    print(f"[cloak-login] BROWSER OPEN (keep-open) — browse/subscribe freely; cookies persist live. "
          f"Window holds up to {timeout}s, or until you close it.", flush=True)
    while time.time() < deadline:
        try:
            ctx.cookies()                 # liveness probe; raises once you close the window
        except Exception:
            print("[cloak-login] window closed — session persisted.", flush=True)
            break
        time.sleep(5)
else:
    print(f"[cloak-login] BROWSER OPEN — sign in to your account now. "
          f"Auto-saves when the '{cookie_name}' cookie appears (or after {timeout}s).", flush=True)
    while time.time() < deadline:
        try:
            names = {c.get("name") for c in ctx.cookies()}
        except Exception:
            names = set()
        if cookie_name in names:
            found = True
            break
        time.sleep(3)

# best-effort: read the logged-in username so the caller can set expected_account
username = ""
if found:
    try:
        mp = ctx.new_page()
        mp.goto("https://www.reddit.com/api/me.json", wait_until="domcontentloaded", timeout=20000)
        m = re.search(r'"name"\s*:\s*"([^"]+)"', mp.content() or "")
        if m:
            username = m.group(1)
        mp.close()
    except Exception:
        pass

try:
    ctx.close()
except Exception:
    pass

if found:
    print(f"[cloak-login] LOGIN DETECTED — session saved to {udd}", flush=True)
    print(f"[cloak-login] USERNAME={username}", flush=True)
else:
    print(f"[cloak-login] no '{cookie_name}' cookie before timeout — if you did sign in, the session "
          f"is still persisted in {udd}; otherwise re-run.", flush=True)
