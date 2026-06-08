# agency-local-serp-os — Setup & Run Runbook

A file-backed local-SEO automation OS. Everything is **gated**: generators only ever write
*drafts*; nothing reaches a real platform without a hashed human approval. Windows-first
(PowerShell), but the Python is cross-platform.

---

## 0. The mental model (read this once)

```
MEASURE            CREATE                 APPROVE            PUBLISH              TRACK
SERP tracker  →    creators (drafts) →    human signs   →   publishers     →    board + signals
Signals ingest     board "+ Add"          off on board      drain inboxes        re-ingest
```

- **State lives in files** under `clients/<id>/…` and `automations/<runner>/{inbox,working,done,failed}`. The board is a read-only *projection* of those files — it never owns state.
- **Two things "run":** (1) the **board** (the UI you click) and (2) the **runners/cadence** (which actually execute approved work orders). They're decoupled.
- **The gate** (`lib/orchestration.py` + `lib/approvals.py` + `lib/policy.py`) sits in front of every publish: idempotency → policy/kill-switch → approval hash/scope/expiry → evidence → history.

---

## 1. Prerequisites

| Need | Why | Install |
|------|-----|---------|
| **Python 3.12** | everything | python.org |
| **Node + npm** | Higgsfield CLI (images/video) | nodejs.org |
| **Higgsfield CLI** | image/video/Pinterest/GBP-image | `npm i -g higgsfield` then `higgsfield auth login` |
| **(optional) Redis** | multi-machine coordination only | single machine uses file locks |

---

## 2. Install

```powershell
# from the repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1            # (bash: source .venv/bin/activate)
pip install -r requirements.txt          # requests pyyaml jsonschema google-auth redis cloakbrowser[geoip] browser-use
# cloakbrowser fetches its stealth Chromium to ~/.cloakbrowser/ on first launch; pre-fetch with:
#   python -c "import cloakbrowser; cloakbrowser.ensure_binary()"
```

Verify the install is healthy (offline, no keys needed):

```powershell
python -m pytest -q                      # 83 tests, all should pass
python run_all_dry.py                    # SERP tracker -> estate scoring on fixtures
```

---

## 3. Credentials — `.env` at the repo root

**Put secrets in `.env` at the repo root.** `lib/env.py` auto-loads it on import and accepts the
`export `-prefixed, quoted lines verbatim — so you can literally `Copy-Item secrets.env.example .env`
and fill it in. Real environment variables always win over the file. `.env` is **gitignored** —
never commit it. (On Unix, `source secrets.env` inside a launchd/cron wrapper is the equivalent.)
Fill in only the keys for the lanes you actually use.

```ini
# ── LLM (drafting + judging) ─────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-5            # not secret; set to your real model id

# ── SERP estate tracker (DataForSEO, Basic auth) ─────────
DATAFORSEO_LOGIN=...
DATAFORSEO_PASSWORD=...
# DATAFORSEO_TRIES=3   DATAFORSEO_COOLDOWN_SEC=300   (retry/circuit tuning, optional)

# ── GBP + social API publishing (Zernio) ─────────────────
ZERNIO_API_KEY=...

# ── Phone RPA (DuoPlus) ──────────────────────────────────
DUOPLUS_API_KEY=...

# ── WordPress (per client; site url+user live in clients/<id>/config/wordpress.yaml) ──
WP_APP_PASSWORD_EXAMPLE_HVAC=xxxx xxxx xxxx xxxx

# ── Cloudflare edge / Castopod podcast / ElevenLabs voice ─
CLOUDFLARE_API_TOKEN=...      CF_ACCOUNT_ID=...
CASTOPOD_API_BASE=https://podcast.your-instance.com   CASTOPOD_API_TOKEN=...
ELEVENLABS_API_KEY=...        ELEVENLABS_VOICE_ID=...

# ── Search signals ingestion ─────────────────────────────
GSC_GA4_CREDENTIALS=/abs/path/service-account.json     # read-only GSC + GA4

# ── CloakBrowser proxies (one sticky proxy per profile) ──
PROXY_HVAC_01=http://user:pass@host:port

# ── Media hosting (GBP photo / podcast audio / video need a PUBLIC url) ──
ASSET_BASE_URL=https://cdn.example.com/assets

# ── Notifications (optional) ─────────────────────────────
TELEGRAM_BOT_TOKEN=...  TELEGRAM_CHAT_ID=...   # or  DISCORD_WEBHOOK_URL=...

# ── Redis (multi-machine ONLY; single machine uses file locks) ──
# REDIS_HOST=...  REDIS_PORT=...  REDIS_PASSWORD=...
```

**Social/video lanes (Facebook, Reddit, Nextdoor, Pinterest, TikTok, YouTube, Quora, LinkedIn,
Patch, Eventbrite, comments) need NO API keys** — they post like a human via the per-client
CloakBrowser profile (§5).

---

## 4. Per-client setup

A client is a folder `clients/<id>/`. Copy `example-hvac-client` as a template. The areas:

| Folder | Holds |
|--------|-------|
| `facts/` | `business_entity.md` (name, phone, service area — ground truth, never fabricated) + SERP-tracker facts (`owned-assets.yaml`, `competition.yaml`, `locations.yaml`, `targeted-search-terms.yaml`) |
| `config/` | `sources.yaml` (which signals to ingest), `wordpress.yaml`, `castopod.yaml` |
| `strategy/` | keyword clusters + feature targets (drive content generation) |
| `rpa/` | `google_business.yaml` (account+location ids), `workflows.yaml`, `policy.yaml`, `schedules.yaml`, `profiles.yaml`, `phones.yaml`, `approvals/` |
| `web/` | API publishers area — `workflows.yaml`, `policy.yaml`, `approvals/` |
| `browser/` | CloakBrowser area — `workflows.yaml`, `policy.yaml`, `profiles.yaml`, `scripts/`, `approvals/` |

### 4a. Provision the CloakBrowser persona (unlocks all social/video)

```powershell
# 1. register the profile + create its persistent data dir (NO browser opens)
python scripts/provision_cb_profile.py --client <id> --proxy-ref proxy_<id>_01
# 2. add the matching proxy to .env (proxy_ref UPPERCASED): PROXY_<ID>_01=http://user:pass@host:port
# 3. open the profile headed + sign in ONCE per platform (cookies persist in ~/cloak-profiles/<id>-cb-agent):
python scripts/cloak_login.py <id>-cb-agent --client <id> --url https://www.facebook.com/login
#    repeat --url for reddit / tiktok / quora / linkedin / youtube / pinterest / nextdoor / patch / eventbrite
```
Then set `expected_account` + `verify_url` in `clients/<id>/browser/profiles.yaml` so the wrong-account
guard confirms identity before every post. The fingerprint is **auto-managed** (geoip-matched to the
proxy) — you don't configure it. There's no separate GUI to run; `cloak_login.py` **is** the login step
(first positional = the `<id>-cb-agent` profile id; `--client` = the client folder, defaults to `agency`).

---

## 5. Start the system

### 5a. The board (the UI you click)
```powershell
python apps/kanban-board/server.py --host 127.0.0.1 --port 8787
```
Open **http://127.0.0.1:8787**. Localhost-only + CSRF-guarded. It polls the filesystem every 3s.

### 5b. The runners (execute approved work orders)
Each publisher drains its own inbox; run on demand, on a schedule, or via the cadence (§6).
`--dry-run` = offline (fakes the network call, perfect for testing the loop).

```powershell
python automations/zernio-publisher/run.py        --client <id> [--dry-run]   # GBP + social via Zernio API
python automations/wordpress-publisher/run.py     --client <id> [--dry-run]   # WordPress
python automations/edge-deployer/run.py           --client <id> [--dry-run]   # Cloudflare edge
python automations/podcast-publisher/run.py       --client <id> [--dry-run]   # Castopod
python automations/cloakbrowser-runner/run.py     --client <id> [--dry-run]   # human-like social/video
python automations/duoplus-rpa-orchestrator/run.py --client <id> --dry-run    # phone RPA (LIVE path is stubbed -> dry-run only until wired)
```

---

## 6. The autonomous loop — cadence orchestrator

One conductor chains *ingest → generate → drain the gated publish lane*. **Gate-safe**: it only
prepares + runs publishers (which ship only approved artifacts), so a scheduled run never publishes
anything you haven't signed off on.

```powershell
python scripts/cadence.py --frequency daily   --client <id> [--dry-run]   # ingest -> issue WOs -> drip GBP -> drain publishers
python scripts/cadence.py --frequency weekly  --client <id> [--dry-run]   # ingest -> GBP batch (review) -> issue WOs
python scripts/cadence.py --frequency monthly --client <id> [--dry-run]   # ingest -> re-audit SERP estate -> re-plan gaps
```

**Schedule it (Windows Task Scheduler)** — 3 tasks:
```powershell
schtasks /Create /TN "serp-daily"   /SC DAILY  /ST 06:00 /TR "C:\path\.venv\Scripts\python.exe C:\path\scripts\cadence.py --frequency daily   --client <id>"
schtasks /Create /TN "serp-weekly"  /SC WEEKLY /D MON /ST 06:30 /TR "...cadence.py --frequency weekly  --client <id>"
schtasks /Create /TN "serp-monthly" /SC MONTHLY /D 1 /ST 07:00 /TR "...cadence.py --frequency monthly --client <id>"
```

---

## 7. Day-to-day: order → approve → publish

### Order content — the board "+ Add Work Order" → **Create content** tab (23 task types)
Pick client + content type + topic (some need a Target URL or Slug). It runs the creator → a
**draft lands in NEEDS APPROVAL**. Types:

| Lane | Task types |
|------|-----------|
| **Owned / web** | WordPress article · LinkedIn Pulse · Quora answer · Edge HTML+Schema · Podcast episode · Custom tool · Patch.com article |
| **GBP (Zernio)** | GBP post (update / event / offer) · GBP weekly batch · Google review reply · GBP image upload |
| **Social/video (CloakBrowser)** | Facebook · Reddit · Nextdoor · Pinterest · YouTube upload · Eventbrite · "Drop a comment" → Reddit / Facebook / LinkedIn / YouTube |

### Approve / reject
- **On the board:** the **Approve / Reject** buttons on each draft card. **Publish →** on an approved card queues the work order.
- **CLI:** `python scripts/approve_draft.py <client> <scope> <workflow> <period> [--area rpa|web|browser] [--edit "new text"]`

### Then a runner (or the cadence) executes the approved work order → DONE.

---

## 8. Full command reference

### Content creators (write a draft → NEEDS APPROVAL)
```powershell
python automations/article-writer/run.py  --client <id> --kind wp|linkedin|quora|facebook|reddit|nextdoor|patch --topic "..." [--slug ...] [--dry-run]
python automations/content-writer/run.py  --client <id> --kind post|event|offer|review_reply [--brief "..."] [--review "..."] [--rating 5] [--review-id ...] [--location ...] [--media-url ...] [--dry-run]
python scripts/gen_edge_html.py           --client <id> --topic "..." [--slug ...] [--dry-run]
python automations/podcast-producer/run.py --client <id> --topic "..." [--slug ...] [--dry-run]
python automations/tool-builder/run.py    --client <id> --tool "..." [--slug ...] [--dry-run]
python automations/event-writer/run.py    --client <id> --brief "...date/time/location..." [--dry-run]
python automations/comment-writer/run.py  --client <id> --kind reddit|facebook|linkedin|youtube --target <url> [--brief "..."] [--dry-run]
python automations/video-producer/run.py  --client <id> --brief "..." [--still-only] [--link <url>] [--title ...] [--workflow ...] [--area rpa|browser] [--scope ...] [--location ...] [--dry-run]
python scripts/gen_gbp_posts.py           --client <id> [--count 5] [--start YYYY-MM-DD] [--site https://...] [--review]   # weekly GBP batch
```

### SERP estate tracker + scoring
```powershell
python run_all_dry.py                                              # tracker (fixtures) -> scorer, end to end
python automations/local-mobile-serp-feature-tracker/run.py [--dry-run]   # live needs DATAFORSEO_*
python automations/serp-estate-scoring/run.py                      # scores the latest tracker run
python scripts/gaps_to_recommendations.py --client <id>           # high-value gaps -> pending recommendations
```

### Signals ingestion (the measurement layer)
```powershell
python scripts/ingest_signals.py --client <id> [--date YYYY-MM-DD]   # GSC + GA4 + Bing + Clarity + GBP -> signals/<date>.json
```

### Work-order scheduling + GBP drip
```powershell
python scripts/gen_workorders.py  --client <id> [--date YYYY-MM-DD]   # routes due scheduled work into runner inboxes
python scripts/post_daily_gbp.py  --client <id> [--date YYYY-MM-DD] [--dry-run]   # publish today's approved GBP post (1/day, idempotent)
bash scripts/issue_all.sh                                            # gen_workorders for every client with schedules + notify digest
```

### Board / assets / misc
```powershell
python scripts/board.py [--out board/index.html]                     # static HTML board snapshot
python scripts/bridge_asset_to_post.py --client <id> --base-url ... [--image-url ...] [--video-url ...] [--days 7]
python scripts/run_browser_task.py ... [--param k=v]                  # enqueue a one-off CloakBrowser task
python scripts/check_redis.py                                         # verify Redis connectivity (if REDIS_HOST set)
python scripts/notify_digest.py                                       # send a held/failed digest to Telegram/Discord
```

---

## 9. Runtime options & toggles

| Control | How | Effect |
|---------|-----|--------|
| **Dry-run** | `--dry-run` on any runner/creator | offline; fakes network calls, fixtures, no spend |
| **Kill switch** | set `enabled: false` in `clients/<id>/<area>/policy.yaml` | halts that area immediately (fail-closed) |
| **Approval period** | board approvals default to **today's date**; GBP daily posts match on `--date` | keeps daily posts distinct + matchable |
| **Estate weights** | env `ESTATE_W_OWNED/_CONTROLLED/_INFLUENCED/...`, `ESTATE_LEAD_HIGH/...`, `ESTATE_MIN_SAMPLES` | A/B scoring per client without code edits |
| **Logging** | env `LOG_LEVEL=DEBUG`, `LOG_JSON=1` | structured JSON logs (grep `reason=HELD`, `stage=approval`) |
| **DataForSEO resilience** | env `DATAFORSEO_TRIES`, `DATAFORSEO_COOLDOWN_SEC` | retry count + circuit-breaker cooldown |
| **Coordination** | set `REDIS_HOST` (+ PORT/PASSWORD) | multi-machine locks/rate-limits instead of file locks |
| **Notifications** | `TELEGRAM_*` / `DISCORD_WEBHOOK_URL` | failure + approval pings |

---

## 10. Safety model (why this is safe to run unattended)

- **Generators never publish.** Every creator writes a `pending` draft only.
- **Publishing requires a hashed, scoped, single-use, expiring approval** (`lib/approvals.py`); the runner re-verifies the hash + scope + expiry before acting (`verify_approval`).
- **Policy + kill switch** are checked in code, fail-closed, before any side-effecting action.
- **Verify-before-act** on CloakBrowser (wrong-account guard) and **idempotency** (one action per profile/workflow/period).
- **Immutable evidence + history** (hashed before/after) for every executed work order.
- Approved social/video posts are posted **verbatim** — the agent never edits approved copy.

---

## 11. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Draft "HELD" on the board | approval missing/expired/scope-mismatch — re-approve; check the work order's `period` matches the approval |
| Work order stuck nowhere | run the matching publisher (`§5b`) or the cadence; it drains the inbox |
| GBP Performance 403 | the listing isn't verified yet (`hasVoiceOfMerchant=false`) |
| Social task does nothing live | the `<client>-cb-agent` profile isn't logged into that platform yet (`§4a`) |
| Pinterest / YouTube / GBP-image fail silently | needs the **Higgsfield CLI** (image/video) and/or **`ASSET_BASE_URL`** (public media host) |
| `unicode`/emoji crash on Windows console | already handled (ASCII output); if custom, `sys.stdout.reconfigure(encoding="utf-8")` |
| Architecture diagram | `docs/ARCHITECTURE_MERMAID.md` renders inline; the live graph is `graphify-out/graph.html` (run `graphify update .`) |

---

*Plans of record live in `docs/superpowers/plans/`. The board is the easiest way in; the cadence is
how it runs itself. Nothing publishes without you.*
