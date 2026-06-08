# New Content & Publishing Workflows — Connect-Everything Plan

**Goal:** Add 7 content/code **creators** and 6 platform **publishers**, and wire them into the existing gated pipeline so each becomes a tracked **work order** on the **kanban board** — drafts that a human approves, then publish to WordPress, social (human-like via CloakBrowser), YouTube/TikTok, Cloudflare edge, and podcast hosts.

**Key insight — nothing new architecturally.** Everything below is either:
- a **creator** → emits a *pending draft* (`approvals/pending/`) → human approves (`approve_draft.py` → hashed artifact), **or**
- a **publisher** → consumes an *approved artifact* via a typed work order → executes on a platform, gated by policy + approval + verify-before-act.

This is the exact `content-writer → approve → zernio-publisher` flow already proven live for GBP. We're adding creators, publishers, `execution_method`s, and integrations — not a new pipeline.

---

## 0. Decisions (locked 2026-06-06)

| Topic | Decision | Impact |
|---|---|---|
| **Voice/TTS** | **ElevenLabs** | `integrations/elevenlabs/client.py`; `ELEVENLABS_API_KEY` |
| **Podcast host** | **Castopod** (self-hosted, open-source) | `integrations/castopod/client.py` → episode + RSS; you host the instance |
| **TikTok** | **CloakBrowser only** | no TikTok API; upload via per-client profile, human-like |
| **YouTube** | **CloakBrowser only** | no YouTube API; upload via per-client profile, human-like |
| **WordPress** | **self-hosted, REST + Application Password, ~1 site per client** | per-client `clients/<id>/config/wordpress.yaml` + env app-password |
| **Social — first platforms** | **Facebook, Reddit, TikTok, Quora** (Pinterest/YouTube later) | all via CloakBrowser |
| **CloakBrowser profiles** | **one persona per client**, named `<client>-cb-agent` (e.g. `example-hvac-client-cb-agent`), logged into every platform | new **Phase 0**: profile provisioning + registration |

**Net effect:** only **WordPress, Castopod, Cloudflare** use real APIs. *Everything social/video* (Facebook, Reddit, TikTok, Quora, YouTube, Pinterest) runs through the **already-live CloakBrowser lane**, acting as a human on the client's `<client>-cb-agent` profile.

---

## 1. The unified content model

Every creator emits a **content draft** with a `kind`, so one approval gate + one board lifecycle covers all of them:

```jsonc
// clients/<id>/<area>/approvals/pending/<scope>__<workflow>__<period>__draft.json
{ "kind": "wp_article|linkedin_pulse|quora_answer|edge_html|audio|podcast|video|code_tool",
  "workflow_id": "...", "scope_id": "...", "status": "pending_human_review",
  "content": { "title": "...", "body": "...", "media": [...], "meta": {...} },
  "provenance": { "cluster": "...", "engine": "...", "source": "..." } }
```

A **publisher work order** then carries `execution_method` + `approval_ref` (the hashed approved artifact) — identical to today's `wo_gbp_*` shape.

Lifecycle on the board is unchanged: **NEEDS APPROVAL → QUEUED → IN PROGRESS → DONE / FAILED**, tagged by a `system` color.

---

## 2. Part A — Content/code creators (generate-only, Tier-3)

Each is a generator that reuses the LLM gate (`integrations/llm/gate.py`), the SERP-driven `content_template.py`, and the strategy clusters. **None publishes** — they only write pending drafts/assets.

| # | Workflow | Generator (new) | Output `kind` | Reuses / needs |
|---|----------|-----------------|---------------|----------------|
| A1 | **Cloudflare edge HTML + Schema** | `scripts/gen_edge_html.py` | `edge_html` | LLM → static HTML + JSON-LD `@graph`; targets AIO tactic |
| A2 | **WordPress article** | `automations/article-writer/run.py --kind wp` | `wp_article` | `content_template` (SERP brief) + LLM long-form |
| A3 | **LinkedIn Pulse article** | `automations/article-writer/run.py --kind linkedin` | `linkedin_pulse` | same generator, professional voice variant |
| A4 | **Quora answer** | `automations/article-writer/run.py --kind quora` | `quora_answer` | LLM Q&A; targets PAA/featured-snippet tactic |
| A5 | **Audio / voice** | `scripts/gen_voice.py` | `audio` | TTS integration (decision below) |
| A6 | **Podcast** | `automations/podcast-producer/run.py` | `podcast` | LLM script → A5 voice → audio file + show notes |
| A7 | **Custom tools / code** | `automations/tool-builder/run.py` | `code_tool` | LLM code-gen → repo/files draft (e.g. a calculator widget, edge worker) |

**Design notes**
- A2/A3/A4 share **one** generator (`article-writer`) with `--kind` variants — DRY. Each kind has a prompt template under `automations/article-writer/prompts/`.
- A1 (edge HTML) and A7 (code) emit **file artifacts** (HTML/JS) instead of text; the draft references the file path + a content hash (same evidence pattern as `video-producer`).
- All creators stamp `provenance.cluster` + target `engine`/feature so the board's calendar and the Signals layer can attribute lift to a cluster.

---

## 3. Part B — Publishers (approved artifact → platform)

Each adds an `execution_method`, a publisher automation, and an integration client. All are **customer-facing → gated** (require an approved artifact + pass policy).

| # | Platform | `execution_method` | Publisher | Integration | Auth |
|---|----------|--------------------|-----------|-------------|------|
| B1 | **WordPress** (self-hosted, ~1/client) | `wordpress_api` | `automations/wordpress-publisher/run.py` *(new)* | `integrations/wordpress/client.py` *(new)* | WP REST API + **Application Password**, per-client (`clients/<id>/config/wordpress.yaml` + env) |
| B2 | **Social/video — human-like** (Facebook, Reddit, TikTok, Quora; then Pinterest, YouTube) | `cloakbrowser` *(existing)* | `cloakbrowser-runner` *(existing)* + per-platform scripts/agent-tasks | `clients/<id>/browser/scripts/{facebook,reddit,tiktok,quora,youtube}_post.py` *(new)* | **per-client CloakBrowser profile `<client>-cb-agent`**, logged in to each platform — **no API**, posts/uploads like a human |
| B3 | **Cloudflare edge** (deploy A1) | `cloudflare_edge` | `automations/edge-deployer/run.py` *(new)* | `integrations/cloudflare/client.py` *(new)* | Workers API (`CLOUDFLARE_API_TOKEN`, `CF_ACCOUNT_ID`) |
| B4 | **Podcast** (Castopod, self-hosted) | `castopod_api` | `automations/podcast-publisher/run.py` *(new)* | `integrations/castopod/client.py` *(new)* | Castopod REST API on your instance → episode + RSS → Spotify/Apple/YouTube pull |

**Design notes**
- **B2 is the "like a human" lane** — the most strategically important (barnacle SEO + social + video). It reuses the *already-wired* CloakBrowser runner + `browser-use` agent on the client's **`<client>-cb-agent`** profile. Each platform is a `playwright_script` (deterministic, e.g. a Pinterest pin or a TikTok/YouTube upload form) or an `agent_task` (Claude drives a contextual post, e.g. a Reddit reply or Quora answer). Verify-before-act confirms it's on the right profile/account; humanize/jitter is on. Gated by approval — approved text/media is posted verbatim.
- **YouTube + TikTok are uploads through B2** (no platform API): the approved video asset (from `higgsfield_media`) is uploaded via the profile's web UI, shorts vs long-form is just metadata (`#shorts`, aspect ratio).
- **Castopod (B4)** is self-hosted and open-source; its REST API creates the episode and Castopod emits the podcast RSS that Spotify/Apple/YouTube subscribe to. A6 produces the audio; B4 publishes it.
- **Per-client profile provisioning (Phase 0)** is the prerequisite for the whole B2 lane — see §6.

---

## 4. Part C — Wiring (the connective tissue)

### 4.1 Workflow registry (`clients/<id>/<area>/workflows.yaml`)
Register each workflow so `gen_workorders` and the publishers pick them up. Example entries:
```yaml
- { workflow_id: wp_article_publish, execution_method: wordpress_api,   action_class: client_owned_content_publishing_after_approval, customer_facing: true,  approval_required: true }
- { workflow_id: facebook_post,      execution_method: cloakbrowser,    action_class: social_posting,                                customer_facing: true,  approval_required: true, kind: agent_task,       profile: "<client>-cb-agent" }
- { workflow_id: reddit_post,        execution_method: cloakbrowser,    action_class: social_posting,                                customer_facing: true,  approval_required: true, kind: agent_task,       profile: "<client>-cb-agent" }
- { workflow_id: quora_answer_post,  execution_method: cloakbrowser,    action_class: social_posting,                                customer_facing: true,  approval_required: true, kind: agent_task,       profile: "<client>-cb-agent" }
- { workflow_id: tiktok_upload,      execution_method: cloakbrowser,    action_class: client_owned_video_publishing_after_approval,  customer_facing: true,  approval_required: true, kind: playwright_script, profile: "<client>-cb-agent" }
- { workflow_id: youtube_upload,     execution_method: cloakbrowser,    action_class: client_owned_video_publishing_after_approval,  customer_facing: true,  approval_required: true, kind: playwright_script, profile: "<client>-cb-agent" }
- { workflow_id: edge_deploy,        execution_method: cloudflare_edge, action_class: first_party_infrastructure_deploy,             customer_facing: false, approval_required: true }
- { workflow_id: podcast_publish,    execution_method: castopod_api,    action_class: client_owned_content_publishing_after_approval, customer_facing: true,  approval_required: true }
```

### 4.2 Policy (`clients/<id>/<area>/policy.yaml`)
Add the new `action_class`es to `allowed_action_classes`; add the public-posting ones (`social_posting`, `client_owned_*_publishing_after_approval`) to `human_gate_action_classes`. Blocked classes (fake engagement, etc.) stay blocked — applies to the new social path too.

### 4.3 Scheduler routing (`scripts/gen_workorders.py`)
Extend `INBOX` to map each new `execution_method` → its publisher inbox:
```python
INBOX = { "duoplus_rpa": ..., "google_business_api": ...,
          "cloakbrowser":    .../"cloakbrowser-runner"/"inbox",   # FB / Reddit / TikTok / Quora / YouTube all route here
          "wordpress_api":   .../"wordpress-publisher"/"inbox",
          "cloudflare_edge": .../"edge-deployer"/"inbox",
          "castopod_api":    .../"podcast-publisher"/"inbox" }
```
Each publisher is a thin clone of `zernio-publisher/run.py`: claim → gate (idempotency + policy + approval) → call its integration client → evidence → finish. The shared machinery (`lib/orchestration.WorkOrderRunner`, `lib/approvals`, `lib/rate_limiter`) is reused unchanged.

### 4.4 Credentials (`.env` + `secrets.env.example`)
Only three integrations need API keys — the social/video lane needs none (just the logged-in profile).
```
# WordPress (per client): site url + user live in clients/<id>/config/wordpress.yaml; password in env
WP_APP_PASSWORD_<CLIENT>=            # e.g. WP_APP_PASSWORD_EXAMPLE_HVAC
# Cloudflare edge
CLOUDFLARE_API_TOKEN= / CF_ACCOUNT_ID=
# Castopod (your self-hosted instance)
CASTOPOD_API_BASE= / CASTOPOD_API_TOKEN=
# ElevenLabs voice
ELEVENLABS_API_KEY=
# (CloakBrowser social/video: NO keys — uses the <client>-cb-agent profile)
```
(Loaded by the existing `lib/env.py` auto-loader; secrets stay gitignored.)

---

## 5. Part D — Work orders + Kanban integration

### 5.1 New systems on the board
Two spots: `lib/board_scan.py` assigns each card a `system` (by automation dir); the `SYS` color/label map lives in `static/app.js`. Add the API-publisher systems and a platform sub-tag for the CloakBrowser lane (so FB/Reddit/TikTok/Quora/YouTube are distinguishable even though they share the `cloakbrowser` runner):
```python
# board_scan.py — dir → system
SUBSYS += { "wordpress-publisher":"wordpress", "edge-deployer":"edge", "podcast-publisher":"podcast" }
# cloakbrowser-runner cards already = system "cloakbrowser"; add card.platform from the work order
#   (facebook|reddit|tiktok|quora|youtube) for a sub-badge.
```
```js
// app.js — system → [label, color]
SYS += { wordpress:["WP","#21759b"], edge:["EDGE","#f38020"], podcast:["POD","#8b5cf6"] };
// plus a small platform→icon map for cloakbrowser cards (FB/RD/TT/Q/YT)
```
No new columns — the lifecycle (approval→queued→progress→done/failed) is shared; `system` + `platform` tags distinguish them. The client filter (already shipped) scopes them.

### 5.2 Generalize the content calendar
Today `content_calendar()` reads GBP calendars only. Generalize it to read a per-client **content schedule** (`clients/<id>/content/schedule/*.json`) covering every `kind` (article, video, podcast, social, edge), each entry `{date, client, kind, platform, title, status}`. The board's calendar then shows the **full publishing calendar** across all platforms, filterable by client (and a new `kind`/platform sub-filter). Status derives from the approval store exactly as it does now.

### 5.3 Create-form (board "+ Add Work Order")
`apps/kanban-board/server.py` `catalog()` already lists workflows per client from `workflows.yaml`; the new workflows appear automatically once registered (4.1). The create modal needs only a small addition: a `kind`-aware target/param hint per `execution_method`.

### 5.4 The full connected flow
```
Signals (ingest) + Strategy (keyword+features clusters, playbook)
  → plan a content asset per cluster (manual)
  → CREATOR (A1–A7) emits a draft  ──► board: NEEDS APPROVAL
  → human approves (approve_draft / board button)  ──► hashed artifact, board: QUEUED
  → cadence / gen_workorders issues a PUBLISHER work order (execution_method)
  → PUBLISHER (B1–B6) executes, gated  ──► board: IN PROGRESS → DONE (or FAILED/HELD)
  → content calendar shows it on its date; Signals re-ingest measures call/conversion lift
```

---

## 6. Phased roadmap (build order)

Each phase is independently shippable + testable (mock the external API/browser in tests, like Plan 1's connectors). Each gets its own `writing-plans` TDD pass when built.

- **Phase 1 — WordPress + board wiring (B1 + A2 + Part D):** highest-leverage owned-content channel, and uses a real API so it proves the *new-creator → approve → new-publisher → execution_method → board* loop end-to-end. Lands the board system map + generalized content calendar that every later phase reuses for free.
- **Phase 0 — CloakBrowser per-client profiles:** provision `<client>-cb-agent` (profile dir + `clients/<id>/browser/profiles.yaml` registration + a one-time human login pass). Prerequisite for all of B2. Small, do it right before Phase 2.
- **Phase 2 — Social-as-human (B2 + A3/A4):** Facebook, Reddit, Quora (`agent_task`) on `<client>-cb-agent`; LinkedIn Pulse + Quora creators. Barnacle SEO.
- **Phase 3 — Video-as-human (B2 video + higgsfield video):** TikTok + YouTube uploads via the profile (`playwright_script`); shorts.
- **Phase 4 — Edge (A1 + B3):** Cloudflare HTML+Schema worker — the AIO-speed tactic.
- **Phase 5 — Audio/Podcast (A5/A6 + B4):** ElevenLabs voice → podcast producer → Castopod → Spotify/Apple/YouTube.
- **Phase 6 — Custom tools (A7):** code-gen workflow for bespoke widgets/tools (often feeds Phase 4 edge).

---

## 7. Decisions resolved → operational inputs still needed

All design decisions are locked in §0. The remaining items are *credentials/assets you supply per client* as each phase goes live (code is built + tested against mocks first):

- **WordPress** (Phase 1): each client's `api_url` + `username` (→ `wordpress.yaml`) and an Application Password (→ env). Needed only to *live-publish*; build/tests don't.
- **CloakBrowser profiles** (Phase 0): create `<client>-cb-agent`, then a **one-time human login** to Facebook/Reddit/TikTok/Quora (and later YouTube) on that profile.
- **Castopod** (Phase 5): your instance base URL + API token.
- **ElevenLabs** (Phase 5): `ELEVENLABS_API_KEY` + a chosen voice id.
- **Cloudflare** (Phase 4): API token + account id (+ a zone/worker route).

---

## 8. Reuse summary (why this is mostly wiring, not new architecture)

| Existing piece | Reused for |
|---|---|
| `lib/orchestration.WorkOrderRunner` | every new publisher (claim/gate/evidence/finish) |
| `lib/approvals` + `approve_draft.py` | every new creator's draft → hashed gated artifact |
| `lib/policy` (allowed/blocked/human-gate) | every new public-posting workflow |
| `integrations/llm/gate.py` + `content_template.py` | every text/code creator |
| `cloakbrowser-runner` + `browser-use` + per-client `<client>-cb-agent` profile | the entire B2 lane — Facebook, Reddit, TikTok, Quora, YouTube (human-like) |
| `higgsfield_media` | video assets for YouTube/TikTok uploads; images for articles/social |
| `gen_workorders.py` | routing new execution_methods to inboxes |
| `board_scan` + kanban + content calendar + client filter | tracking every new workflow as work orders |
| `lib/signals` (Plan 1) | measuring call/conversion lift per published asset |
