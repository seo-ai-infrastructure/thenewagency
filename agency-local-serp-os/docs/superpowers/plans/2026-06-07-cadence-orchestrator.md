# Plan 3 — Cadence Orchestrator (the autonomous-loop conductor)

**Goal:** chain the existing pieces — *ingest Signals → plan/generate → gated publish* — on a
daily / weekly / monthly schedule, turning the manual board into the autonomous loop. The pieces
existed (`ingest_signals`, `gen_workorders`, `gen_gbp_posts`, `post_daily_gbp`, the publishers,
`run_all_dry`, `gaps_to_recommendations`); this is the conductor.

## Design
- **`lib/cadence.py`** — pure + testable. `steps_for(frequency, client, dry)` returns an ordered
  `[(name, argv)]`; `run_cadence(frequency, client, execute, dry)` runs each step via an injected
  `execute` and is **graceful** (a failing step is logged, the rest still run).
- **`scripts/cadence.py`** — the CLI; `execute()` runs each step as a subprocess.

## The schedule
| Frequency | Steps (in order) |
|---|---|
| **daily** | ingest Signals → issue due work orders → drip the approved GBP post → drain every publisher inbox (zernio, wordpress, edge, podcast, cloakbrowser) |
| **weekly** | ingest → generate the GBP batch (`--review` → drafts for sign-off) → issue work orders |
| **monthly** | ingest → re-audit the SERP estate (`run_all_dry`) → re-plan from gaps (`gaps_to_recommendations`) |

## Gate-safety (the key property)
The cadence only **prepares** (ingest, generate *drafts*, issue work orders) and runs the publish
lane — and every publisher ships **only a hashed, human-approved artifact**. So a scheduled run
**never publishes anything a human hasn't signed off on**. During the manual-first-30-days phase it
quietly does the measuring + drafting + draining; you still approve on the board.

## Run / schedule it
```bash
python scripts/cadence.py --frequency daily   --client <id>            # 1x/day
python scripts/cadence.py --frequency weekly  --client <id>            # on its day
python scripts/cadence.py --frequency monthly --client <id>            # on the 1st
python scripts/cadence.py --frequency daily   --client <id> --dry-run  # offline, no network
```
Wire to **Windows Task Scheduler** (3 tasks). `--dry-run` makes the whole chain offline.

## Follow-ons (not in v1)
- A real **planner** step (Signals-driven topic selection from the keyword clusters) — today
  "plan" = schedule-driven work-order issuance + the cluster-driven GBP batch.
- Per-step **run log** persisted to history (currently printed); Task Scheduler XML generator.
