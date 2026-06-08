"""Cadence orchestrator — the autonomous-loop conductor (Plan 3).

Chains the EXISTING pieces on a daily / weekly / monthly schedule:
    ingest Signals  ->  plan / generate (drafts + work orders)  ->  gated publish

It is GATE-SAFE: the cadence only PREPARES (ingest, generate drafts, issue work orders) and runs
the publish lane — and every publisher only ships an already hashed-and-approved artifact. So a
scheduled run never publishes anything a human hasn't signed off on. Steps are run GRACEFULLY:
one failing step is logged and the rest still run (a flaky ingest must not block publishing).

steps_for() is pure (returns a list of (name, argv)) so it's fully unit-testable; run_cadence()
takes an injected `execute(name, argv) -> (ok, output)` so the loop is testable without subprocess.
"""

# Publishers whose inboxes the daily lane drains (each only acts on approved work orders).
PUBLISHERS = ["zernio-publisher", "wordpress-publisher", "edge-deployer",
              "podcast-publisher", "cloakbrowser-runner"]


def steps_for(frequency, client, dry=False):
    """Ordered [(step_name, argv)] for a frequency. argv[0] is a repo-relative script path."""
    d = ["--dry-run"] if dry else []
    C = ["--client", client]
    publish = [(f"publish:{p}", [f"automations/{p}/run.py"] + C + d) for p in PUBLISHERS]
    if frequency == "daily":
        return [
            ("ingest_signals",    ["scripts/ingest_signals.py"] + C),       # measure (calls/CRO/SERP)
            ("issue_workorders",  ["scripts/gen_workorders.py"] + C),       # plan: due scheduled work
            ("publish_gbp_daily", ["scripts/post_daily_gbp.py"] + C + d),   # drip the approved GBP post
            *publish,                                                        # drain approved inboxes
        ]
    if frequency == "weekly":
        return [
            ("ingest_signals",   ["scripts/ingest_signals.py"] + C),
            ("gen_gbp_batch",    ["scripts/gen_gbp_posts.py"] + C + ["--review"]),  # generate drafts for review
            ("issue_workorders", ["scripts/gen_workorders.py"] + C),
        ]
    if frequency == "monthly":
        return [
            ("ingest_signals",    ["scripts/ingest_signals.py"] + C),
            ("serp_estate_audit", ["run_all_dry.py"]),                      # re-audit the SERP estate
            ("gaps_to_recs",      ["scripts/gaps_to_recommendations.py"] + C),  # re-plan from gaps
            ("aeo_recs",          ["scripts/aeo_gaps_to_recommendations.py"] + C),  # citation + aggregator conquest
        ]
    raise ValueError(f"unknown frequency: {frequency} (use daily|weekly|monthly)")


def run_cadence(frequency, client, execute, dry=False):
    """Run every step for `frequency` via execute(name, argv) -> (ok, output). Continues past a
    failing step (graceful). Returns a per-step log: [{step, ok, output}]."""
    log = []
    for name, argv in steps_for(frequency, client, dry):
        try:
            ok, out = execute(name, argv)
        except Exception as e:
            ok, out = False, f"{type(e).__name__}: {e}"
        log.append({"step": name, "ok": bool(ok), "output": out or ""})
    return log
