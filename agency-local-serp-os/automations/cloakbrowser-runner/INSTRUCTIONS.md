# cloakbrowser-runner (desktop-web execution surface). SEPARATE from DuoPlus RPA & Zernio.

Runs tasks as one of N persistent, fingerprinted browser identities via CloakBrowser
(stealth Chromium, drop-in Playwright). Each profile keeps its own cookies/logins in a
persistent user_data_dir, so agents never re-login. Shares only lib/ (policy, approval gate,
idempotency, evidence, rate limiter, locks) with the other subsystems.

Two workflow kinds:
  - playwright_script : deterministic .py in clients/<id>/browser/scripts (run(page, params))
  - agent_task        : Tier-4 AI browser agent (browser-use / computer use) with a goal

Read-only recon (rank_spot_check, social_scan) needs no approval. Any public ACTION
(social_reply, action_class social_posting) is HELD until a hashed approval exists.

Ad-hoc:   python scripts/run_browser_task.py agency agent_01 rank_spot_check --param keyword="emergency ac repair" --param domain=houseacrepair.com --param location="Fort Lauderdale"
Then run: python automations/cloakbrowser-runner/run.py --dry-run
Scheduled tasks are issued by scripts/gen_workorders.py (routes cloakbrowser -> this inbox).

One context per profile at a time (profile lock). Different profiles may run in parallel,
bounded by RAM. BYO proxies (one sticky proxy per profile). humanize=True for natural input.
