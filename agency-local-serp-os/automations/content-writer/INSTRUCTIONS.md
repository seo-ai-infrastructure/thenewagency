# content-writer (Tier 3 LLM gate — drafts only, never posts)

Drafts GBP posts and review replies from client facts/ + a brief, using integrations/llm.
Output is a PENDING human-review draft in clients/<id>/rpa/approvals/pending/. A human
reviews/edits, then scripts/approve_draft.py emits a hashed APPROVED artifact, which the
scheduler turns into a work order and the orchestrator posts via Zernio. The model never
publishes; it only proposes text.

  python run.py --kind post        --client <id> --location <loc> --brief "AC tune-up special"
  python run.py --kind review_reply --client <id> --location <loc> --review "..." --rating 5
  (add --dry-run, or just omit ANTHROPIC_API_KEY, to use the offline stub)
