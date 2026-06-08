# local-mobile-serp-feature-tracker
Three DataForSEO lanes (Local Finder / Organic mobile / AI Mode), normalized into one
serp_feature_snapshot schema with 5-class ownership and AI citations.
Schedule-triggered collector (run-level idempotency via state/, not inbox-driven).
Dry-run reads fixtures; live archives raw responses to raw/. AI Mode absence is recorded,
not errored. Output: history/<run_id>.jsonl -> consumed by serp-estate-scoring.
