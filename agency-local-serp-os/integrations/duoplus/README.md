# integrations/duoplus (shared)
How the agency talks to DuoPlus. client.py (API control + native RPA + ADB),
rate_limiter.py (ACCOUNT-GLOBAL 1 QPS), policy.py (fail-closed enforcement + kill switch).
Proxy + location are bound via the API (identity consistency), never the UI.
See safety_policy.md for the allowed/blocked action classes.

## Multi-machine coordination (optional)
redis_backends.py provides a Redis distributed lock + account-global rate limiter.
The orchestrator uses them automatically when REDIS_HOST is set; otherwise it falls
back to the single-machine file lock + .rate_state. Setup: free DB at redis.io/cloud,
then export REDIS_HOST/REDIS_PORT/REDIS_PASSWORD/REDIS_CA. Requires: pip install redis.
