# Config Guide — DuoPlus RPA Setup (fill-in-the-blanks)

Set these up in order. Two locations:
- `integrations/duoplus/` — how to talk to DuoPlus (shared across all clients)
- `clients/<client_id>/rpa/` — this client's phones, profiles, workflows, schedules (data)

The chain is **phones ← profiles ← workflows ← schedules**, with the runner enforcing
policy + approval gates on every job. A misconfigured schedule still can't make a profile
do something it isn't permitted to.

---

## Step 1 — API connection (`integrations/duoplus/`)

The system can't reach DuoPlus until this is done.

- [ ] Get your API key: DuoPlus console → Automation → API.
- [ ] Export it (the system sends it as the `DuoPlus-API-Key` header):
      ```bash
      export DUOPLUS_API_KEY="your-key"
      ```
- [ ] Wire the real calls in `integrations/duoplus/client.py` — every method
      (`phone_status`, `power_on`, `bind_proxy_location`, `switch_profile`,
      `verify_profile`, `run_workflow`, `adb`) currently raises `NotImplementedError`.
      Replace each with the DuoPlus HTTP call, reading `os.environ["DUOPLUS_API_KEY"]`.
      `endpoints.yaml` lists the endpoint categories as your map.

Until wired, run everything with `--dry-run` (fake device).

---

## Step 2 — Device id (`clients/<client_id>/rpa/phones.yaml`)

```yaml
phones:
  - phone_id: duoplus_phone_001            # YOUR label (profiles point at this)
    duoplus_image_id: "______"             # FILL: real cloud-phone id from DuoPlus
    timezone: "America/New_York"           # FILL: used to resolve schedule windows
    max_parallel_runs: 1                   # keep 1 (one foreground per phone)
    active: true
```
- [ ] `duoplus_image_id` from DuoPlus console or the `cloudPhone/list` API.
- [ ] `timezone` = the phone's local zone.
- [ ] Leave `max_parallel_runs: 1`.

---

## Step 3 — Profiles (`clients/<client_id>/rpa/profiles.yaml`)

One block per profile on the phone.
```yaml
profiles:
  - profile_id: profile_001
    phone_id: duoplus_phone_001            # must match a phones.yaml phone_id
    expected_account: "______"             # FILL: account id verify-before-act checks
    proxy: { id: "______" }                # FILL: proxy bound via API
    location: { name: "______", lat: 0.0, lng: 0.0 }   # FILL: bound via API
    allowed_workflows: [mobile_profile_healthcheck]    # whitelist for this profile
    max_runs_per_day: 2
    active: true
```
- [ ] `expected_account` — the on-device account; if it doesn't match, the run aborts.
- [ ] `proxy.id` + `location` — bound and verified before any action.
- [ ] `allowed_workflows` — a profile can ONLY run workflows listed here.
- [ ] **Remove any `simulate_verify_fail: true`** — that's a demo flag; it forces an abort.

---

## Step 4 — RPA workflows (`clients/<client_id>/rpa/workflows.yaml`)

Two halves: build the in-app automation as a DuoPlus RPA template (taps/types/swipes),
then declare it here.
```yaml
workflows:
  - workflow_id: approved_content_post
    execution_method: duoplus_rpa
    duoplus_template_id: "______"          # FILL: id of your DuoPlus RPA template
    action_class: client_owned_content_publishing_after_approval   # MUST be allowed in policy.yaml
    customer_facing: true                  # true -> needs a human-approved artifact
    approval_required: true
    description: "..."
```
- [ ] Build the template in DuoPlus; paste its id into `duoplus_template_id`.
- [ ] Set `action_class` to a value in `policy.yaml`'s `allowed_action_classes`
      (and not in `blocked_action_classes`), or the runner refuses it.
- [ ] `customer_facing: true` + `approval_required: true` for anything that posts/changes
      something public. Read-only checks use `customer_facing: false`.

---

## Step 5 — Schedules (`clients/<client_id>/rpa/schedules.yaml`)

Which workflow runs for which profiles, when.
```yaml
schedules:
  - schedule_id: daily_profile_healthcheck
    workflow_id: mobile_profile_healthcheck
    frequency: daily                       # daily | weekly | monthly
    profiles: [profile_001, profile_002]
    execution_policy: sequential_per_phone
    cooldown_seconds_between_profiles: 300
    active: true
  - schedule_id: weekly_approved_content_post
    workflow_id: approved_content_post
    frequency: weekly
    day_of_week: monday                    # weekly needs this; monthly needs day_of_month
    profiles: [profile_001]
    requires_approval_artifact: true
    active: true
```
- [ ] `frequency` + `day_of_week` (weekly) or `day_of_month` (monthly).
- [ ] Different workflows on different days = more schedule blocks.
- [ ] Trigger daily:
      ```bash
      python scripts/gen_workorders.py --date $(date +%F)
      python automations/duoplus-rpa-orchestrator/run.py --date $(date +%F)
      ```
- [ ] For recurrence, schedule a wrapper (launchd/cron) that sources env then runs both.
      A scheduler won't see a `source`d shell — the wrapper must export `DUOPLUS_API_KEY`
      and `source redis.env` itself.

---

## Step 6 — Policy (`clients/<client_id>/rpa/policy.yaml`)

- [ ] `enabled: true` — the global kill switch; set `false` to halt all RPA instantly.
- [ ] Every workflow's `action_class` appears in `allowed_action_classes`.
- [ ] Abuse classes stay in `blocked_action_classes` (fake reviews, engagement, etc.).

---

## Scheduling: DuoPlus native vs your orchestrator

Decision rule:
- **Customer-facing / write / approval-required / needs coordination → your orchestrator.**
  Always. DuoPlus native scheduling bypasses policy, approval, verify, idempotency, and
  the Redis locks/rate-limit — none of those run if DuoPlus fires the template itself.
- **Read-only, unconditional, no approval (e.g., login-state healthcheck) → native is OK,**
  and it gains resilience (runs even if your machine is off). Pull the DuoPlus task reports
  back into `history/` for the record.

If you mix them: the Redis locks only coordinate your system against itself, NOT against
DuoPlus's native scheduler. Keep native tasks on a different phone, or in a time window
your orchestrator never runs in, or they can collide on the foreground / 1 QPS limit.

If the only reason to consider native is "must run when my Mac is off," prefer running your
orchestrator on a small always-on box — you keep all the gates — and reserve native for the
safe read-only subset.

---

## Validate before going live

- [ ] `python scripts/check_redis.py` → `OK` (if using Redis)
- [ ] `python scripts/gen_workorders.py --date <a Monday>`
- [ ] `python automations/duoplus-rpa-orchestrator/run.py --dry-run --date <same date>`
      → reads run, writes HELD without approval, wrong-account aborts.
- [ ] Only then implement the `client.py` calls and do a real run.

---

## Facts integration (NAP consistency)

Content and entity data live ONCE in `clients/<id>/facts/business_entity.md` (name,
address, phone, service area). DuoPlus posts are built from it upstream — the RPA layer
never composes content on-device. Per-profile proxy/geo stays in `profiles.yaml` (it
differs per profile); shared business identity stays in facts/. See root `CONTEXT.md`.

## Content flow (where the LLM is allowed)

```
content-writer (Tier 3, upstream)  ->  human approves exact copy  ->  approved artifact
        ->  scheduler issues RPA work order  ->  orchestrator posts the approved artifact
```
The RPA layer is dumb on purpose: it posts a pre-approved artifact and confirms it landed.
No drafting, summarizing, or "deciding what to post" happens on the phone.

## SERP Estate -> RPA handoff

`python scripts/gaps_to_recommendations.py --client <id>` reads the latest SERP tracker
history, finds HIGH-value slots owned by competitors / unclaimed, and writes
`pending_human_review` recommendations into `rpa/approvals/pending/`. These are NOT
executable — a human chooses the action and supplies content, which becomes an approved
artifact, which the scheduler turns into a work order. The bridge only raises the flag.

## Risk tiers (policy.yaml)

`human_gate_action_classes` lists public-posting classes (gbp_post_publish,
gbp_review_reply, gbp_photo_upload, client_owned_content_publishing_after_approval). Any
workflow with one of these action classes ALWAYS requires approval — even if it forgot to
set `customer_facing` — as a defense-in-depth safety net.

## Observability & history

Each run appends to `history/runs.jsonl`: status, hashed before/after evidence (in the
client's `logs/`), and the DuoPlus `task_report`. That's your client-reporting and
debugging audit trail. For live runs, pull DuoPlus task reports back via the API into the
same record.

## Cost & scaling

One orchestrator manages many phones/clients via the YAML configs. The DuoPlus API limit
(~1 QPS per interface) is ACCOUNT-WIDE, so multi-client throughput shares one budget — the
Redis account-global limiter is what keeps you under it across machines. Cost scales with
phones x profiles x actions x cadence; check current DuoPlus pricing tiers in your console.
Push read-only tasks to a lighter cadence; keep customer-facing actions modest and gated.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Work order sits in `failed/` with "approval artifact missing" | Customer-facing/gated workflow with no approved artifact — create one (`make_approval.py`) or it stays held. |
| "BLOCKED — action_class not in allowed_action_classes" | Add the class to `policy.yaml` allowed list (and confirm it's not blocked). |
| "VERIFY FAILED — abort" | On-device account != `expected_account`, or a leftover `simulate_verify_fail: true`. |
| Proxy binding fails (live) | Check the proxy id is valid in DuoPlus and `bind_proxy_location` is wired in client.py. |
| "phone busy — requeued" | Another run holds the phone lock; expected — it retries next sweep. Check `state/locks/`. |
| DuoPlus API errors / 429 | Rate limit — ensure the limiter is active (Redis for multi-machine); back off. |

## Never run unapproved customer-facing workflows natively in DuoPlus

DuoPlus native scheduling bypasses policy, approval, verify, idempotency, and the locks.
Customer-facing/public-posting workflows must ALWAYS go through the orchestrator. Reserve
native scheduling for read-only, no-approval tasks — see the scheduling section above.

---

## Google Business posting (API-first, via Zernio)

GBP has an API, so GBP workflows do NOT use the phone. They run with
`execution_method: google_business_api` and go through `integrations/google_business/`
(Zernio: https://docs.zernio.com/platforms/google-business). Zernio owns the Google
`business.manage` OAuth at connect time; you hold only the Zernio API key.

Setup:
- [ ] `export ZERNIO_API_KEY="..."`
- [ ] Connect the client's GBP account in Zernio; put the connected `account_id` and a
      `default_location_id` (from `GET /accounts/{id}/gmb-locations`) into
      `clients/<id>/rpa/google_business.yaml`.
- [ ] Workflows `gbp_post_publish` / `gbp_photo_upload` / `gbp_review_reply` use
      `execution_method: google_business_api` (already set for gbp_post_publish).
- [ ] GBP schedules target `gbp_locations: [...]` (a location), not phone `profiles`.

The orchestrator routes by `execution_method`: API workflows skip the phone/lock/verify
steps but keep the SAME gates — policy, human approval (the approved artifact's text is
exactly what gets posted), idempotency, evidence, and history. DuoPlus RPA stays for
app-only actions with no API (Q&A is gone from Google's API; videos and service-areas
aren't supported). Limits via Zernio: 1500 chars, 1 image (JPEG/PNG, <=5MB, >=400x300).

---

## LLM gate (content-writer) & the Zernio MCP

**Drafting (Tier 3):** `automations/content-writer/` drafts GBP posts and review replies
from `facts/business_entity.md` + a brief, via `integrations/llm/gate.py`. It writes a
PENDING draft to `approvals/pending/` — it never posts. Flow:

```
content-writer (LLM draft) -> approvals/pending/
   -> human reviews/edits -> scripts/approve_draft.py (hash+scope+expiry) -> approvals/approved/
   -> gen.py issues a work order -> orchestrator posts via Zernio (gated)
```
Run: `python automations/content-writer/run.py --kind post|review_reply --client <id>
--location <loc> --brief "..."`. Needs `ANTHROPIC_API_KEY` (+ optional `CLAUDE_MODEL`);
without it, an offline stub is produced so dry-runs work.

**Social:** the Zernio client now has `create_post(platform, ...)` and `cross_post(...)`
covering all 14 Zernio platforms — the same gated pipeline handles social like GBP.

**MCP — when to use it:** the Zernio MCP (`https://mcp.zernio.com/mcp`) is for INTERACTIVE
work inside Claude (you as the live human gate): ad-hoc drafting, cross-posting, inbox
triage. Do NOT use it as the pipeline's execution path — it lets an agent publish directly,
bypassing approval/policy/idempotency/evidence. The deterministic REST client stays the
unattended executor; the MCP is your assistant-mode convenience; the LLM gate is generate-only.

---

## Two separate execution subsystems (do not conflate)

RPA and Zernio are different parts of the system. They share only the neutral safety
library in `lib/` (policy, approval gate, idempotency, evidence, rate limiter, redis).

- **DuoPlus RPA** — `automations/duoplus-rpa-orchestrator/` — phone-based in-app automation
  ONLY. Phones, profiles, proxy/location bind, device locks, verify-before-act. Processes
  work orders with `execution_method: duoplus_rpa`.
- **Zernio publisher** — `automations/zernio-publisher/` — API posting to Google Business
  Profile + 14 social platforms. No phones, no locks. Processes work orders with
  `execution_method: google_business_api`.

`scripts/gen_workorders.py` is the shared scheduler: it reads the client's `schedules.yaml`
and drops each work order into the inbox of the subsystem that owns its workflow's
`execution_method`. Run order:

    python scripts/gen_workorders.py --date YYYY-MM-DD          # issue to both inboxes
    python automations/duoplus-rpa-orchestrator/run.py --dry-run --date YYYY-MM-DD
    python automations/zernio-publisher/run.py        --dry-run --date YYYY-MM-DD

Each subsystem only picks up its own work orders and gates them independently.

---

## Third execution surface: cloakbrowser-runner (desktop web)

Persistent, fingerprinted browser identities via CloakBrowser (stealth Chromium, drop-in
Playwright). Parallel to DuoPlus and Zernio; shares only lib/. Agency-owned agents live under
`clients/agency/browser/` (profiles, workflows, scripts, policy, approvals, logs).

- Each profile = unique fingerprint + sticky proxy + persistent `user_data_dir` (log in once
  via CloakBrowser Manager; cookies/sessions persist, no re-login).
- Workflows are `playwright_script` (deterministic) or `agent_task` (Tier-4 AI browser agent).
- Read-only recon (rank_spot_check, social_scan) needs no approval; public actions
  (social_posting) are HELD until a hashed approval exists. verify-before-act aborts on the
  wrong account. One context per profile (lock); BYO proxies; humanize=True.

Ad-hoc:    python scripts/run_browser_task.py agency agent_01 rank_spot_check --param keyword="..." --param domain=...
Execute:   python automations/cloakbrowser-runner/run.py --dry-run
Scheduled: scripts/gen_workorders.py --client agency --date YYYY-MM-DD   (routes cloakbrowser -> this inbox)

Method ladder across surfaces: prefer Zernio (API) -> CloakBrowser (web) -> DuoPlus (phone).

---

## The board (scripts/board.py)

A read-only kanban that projects the live filesystem — it holds no state of its own, so it
can't drift from reality. Scans all three subsystem inboxes/working/done/failed plus every
client's approvals/{pending,approved} store and renders a self-contained HTML board:

  NEEDS APPROVAL · QUEUED · IN PROGRESS · DONE · FAILED/HELD

NEEDS APPROVAL surfaces pending drafts (the things most likely to get lost) with a ready-to-
copy approve_draft.py command on each card; FAILED/HELD shows the reason from history.

  python scripts/board.py                 # writes board/index.html
  python scripts/board.py --out ~/serp-board.html
  open board/index.html                   # or point a browser at it from your phone

Refresh by re-running it (cheap). To keep it always-current, add it to launchd/cron on the
Mac mini, or run it at the end of each orchestrator pass.

---

## video-producer (image -> video asset, gated)

`automations/video-producer/` turns a brief into a still (Nano Banana) animated to a clip (Veo
image-to-video), via the LLM gate for the prompts. Assets land under
`clients/<id>/rpa/assets/<draft_id>/` and a PENDING draft records their paths. A human reviews
the actual files, then `scripts/approve_draft.py <client> <scope> video_asset <period>` emits the
hashed approval — only then may a publisher use the asset. The producer never publishes.

  python automations/video-producer/run.py --client <id> --location <loc> --brief "..." [--still-only] [--dry-run]

Live calls need GOOGLE_API_KEY and SPEND money; --dry-run writes free placeholder files and runs
the whole gated flow. Models via NANOBANANA_MODEL / VEO_MODEL env (see secrets.env.example).

---

## Closing the loop: asset -> GBP post (scripts/bridge_asset_to_post.py)

After a video_asset is APPROVED, the bridge routes it to a gated GBP post:

  video-producer -> approve_draft (video_asset) -> bridge_asset_to_post -> zernio-publisher

  python scripts/bridge_asset_to_post.py <client> <scope> <period> --base-url https://cdn.example.com/assets

You host the files (sync clients/<id>/rpa/assets/<draft_id>/ to {base}/<id>/<draft_id>/). The bridge
maps the still to a public URL, emits a gbp_post_publish approval using the SAME hashing as the gate
(so verify_approval accepts it; provenance records bridged_from), and drops a typed work order in the
zernio inbox. GBP posts the STILL image (Google has no video posts); the clip URL is recorded in the
approval for a future social target. No new content is created — the human already approved this asset.
