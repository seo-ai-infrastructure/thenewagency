# duoplus-rpa-orchestrator (generic runner — owns NO client data)

Two steps:
  python gen.py --date YYYY-MM-DD            # schedules.yaml -> work orders in inbox/
  python run.py --dry-run --date YYYY-MM-DD  # claim, gate, run (fake device), log

16-step runner per work order: claim atomically -> policy check (kill switch, blocked/
allowed action class, workflow allowed) -> approval check (hash+scope+expiry+single-use)
for customer-facing -> phone lock -> profile lock -> rate-limit (account-global 1 QPS) ->
power on -> bind+verify proxy/location (API) -> switch + VERIFY profile (abort if wrong) ->
run workflow (native RPA) with intra-workflow jitter -> monitor -> capture immutable hashed
evidence -> CONFIRM landed -> record idempotent -> done/ or failed/ (no blind retry for
writes) -> release locks. Consumes the approval (single-use) on customer-facing success.
