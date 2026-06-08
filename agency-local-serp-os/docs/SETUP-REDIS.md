# Setup & Running Redis with the Agency OS

A complete, do-it-in-order runbook for wiring your Redis Cloud database into
`agency-local-serp-os`. Redis is used by **one** part of the system — the DuoPlus RPA
orchestrator — to coordinate locks and the DuoPlus rate limit across machines. Nothing
else touches it, and your real data stays in files and DuckDB.

You only need Redis if the orchestrator runs from more than one machine against the same
DuoPlus account. On a single machine the built-in file fallback is equivalent.

---

## 0. What Redis does here (one paragraph)

Two ephemeral things live in Redis: **locks** (so only one profile touches a phone at a
time) and a **per-second counter** (so all machines together stay under DuoPlus's ~1 QPS
limit). Both rely on Redis running commands one-at-a-time, which makes `SET NX` and `INCR`
atomic across every connected machine. Keys auto-expire, so nothing accumulates. Your work
orders, history, evidence, approvals, SERP data, and client facts are **not** in Redis.

---

## 1. Prerequisites

- The repo unzipped, and a working Python (`python3 --version`).
- Your Redis Cloud database (you created `duoplus-coord`).
- The redis client library:
  ```bash
  pip install redis
  ```

---

## 2. Your database

From the Redis Cloud console (already created):

- Public endpoint: `redis-13875.c245.us-east-1-3.ec2.cloud.redislabs.com:13875`
  - host = everything before the colon
  - port = `13875`
- TLS: **not enabled** (so we connect plain; see step 7 if you turn it on later)

---

## 3. Get the password

In the console's **Security** section, the **Default user password** is masked. Click the
reveal (eye) icon or **Copy** to get the real value (a long random string). If there's no
reveal control, open **Edit database** — it's shown there, and you can regenerate it.
Never paste this password into chat or commit it anywhere.

---

## 4. Configure credentials

From the repo root:

```bash
cp redis.env.example redis.env
```

Edit `redis.env` and paste your password into `REDIS_PASSWORD`. The host and port are
already filled in. Then load it into your shell:

```bash
source redis.env
```

`redis.env` is git-ignored, so the secret won't be committed.

---

## 5. Verify it works (before running anything real)

```bash
python scripts/check_redis.py
```

Expected output:

```
1) PING -> True
2) acquired phone lock: True
   second acquire is blocked (expect None): None
   re-acquire after release: True
3) rate limiter spaced 2 calls over ~1.00s (expect ~1s)
OK - Redis is reachable and the lock + rate limiter work.
```

If this passes, Redis is correctly wired. If it fails, see Troubleshooting.

---

## 6. Which files use Redis

| File | Role |
|---|---|
| `integrations/duoplus/redis_backends.py` | The Redis lock + account-global rate limiter + `get_redis()`. |
| `automations/duoplus-rpa-orchestrator/run.py` | Auto-selects Redis backends when `REDIS_HOST` is set; otherwise uses the file lock + `.rate_state`. |

Nothing else imports Redis. The selection is automatic — no code edits to switch modes.

---

## 7. Running it

The orchestrator is two steps: generate work orders from the schedules, then process them.

**Validate the Redis coordination layer now (fake phone, real Redis):**
```bash
source redis.env
python scripts/gen_workorders.py --date 2026-06-08      # a Monday
python automations/duoplus-rpa-orchestrator/run.py --dry-run --date 2026-06-08
```
With `redis.env` sourced, even `--dry-run` uses your real Redis for locks and pacing (the
phone itself stays simulated). This is how you confirm the whole flow against your DB
before DuoPlus is wired. You'll notice the run pace itself to ~1 action/second — that's the
real rate limiter working.

**Pure offline test (no Redis at all):** open a fresh shell (don't source `redis.env`), or
`unset REDIS_HOST`. The orchestrator falls back to the file lock + `.rate_state`, and
`--dry-run` is instant.

**Live run (after you wire DuoPlus):**
```bash
source redis.env
python automations/duoplus-rpa-orchestrator/run.py --date 2026-06-08
```
A live run uses Redis **and** real DuoPlus calls. Until you implement the DuoPlus methods
in `integrations/duoplus/client.py` (they currently raise `NotImplementedError`), use the
dry-run-with-Redis mode above.

TLS note: if you enable TLS in the console later, download the CA cert and add
`export REDIS_CA="/abs/path/redis_ca.pem"` to `redis.env`, or plain connections will fail.

---

## 8. Confirm Redis is actually being used

While a run is in progress, in another terminal:

```bash
redis-cli -h redis-13875.c245.us-east-1-3.ec2.cloud.redislabs.com -p 13875 -a "$REDIS_PASSWORD" KEYS 'lock:*'
redis-cli -h ... -p 13875 -a "$REDIS_PASSWORD" GET  lock:phone_duoplus_phone_001
redis-cli -h ... -p 13875 -a "$REDIS_PASSWORD" TTL  lock:phone_duoplus_phone_001
redis-cli -h ... -p 13875 -a "$REDIS_PASSWORD" MONITOR     # live stream of every command
```

You'll see `lock:phone_*` / `lock:profile_*` appear and disappear, and
`duoplus:ratelimit:<second>` counters tick.

---

## 9. Multiple machines

Put the **same `redis.env`** on each machine that runs the orchestrator and `source` it.
They now share one referee: only one machine can hold a given phone at a time, and all of
them together respect the 1 QPS DuoPlus limit. No other change is needed.

Scheduling note: a scheduler (launchd/cron) does **not** see variables you `source` in your
shell. For scheduled runs, either put the four `REDIS_*` vars in the launchd plist's
`EnvironmentVariables`, or use a small wrapper script that does
`source /abs/path/redis.env && python .../run.py` and schedule the wrapper.

---

## 10. Keys reference

| Key pattern | Purpose | TTL |
|---|---|---|
| `lock:phone_<phone_id>` | One actor per phone | 10 min (auto-clears a crashed holder) |
| `lock:profile_<profile_id>` | One run per profile | 10 min |
| `duoplus:ratelimit:<epoch_second>` | Account-global 1 QPS window | 2 s |

All keys carry a TTL, so the database self-cleans and stays tiny.

---

## 11. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `check_redis.py` hangs on PING | Wrong port, or network blocked. Re-check the endpoint. |
| Auth error / `WRONGPASS` | Password wrong or not revealed. Re-copy it; re-`source redis.env`. |
| Connection works in `redis-cli` but not Python | You enabled TLS — set `REDIS_CA` (or disable TLS). |
| A lock seems stuck | It self-clears at its TTL; or `redis-cli ... DEL lock:phone_<id>`. |
| Orchestrator instant in dry-run, no Redis keys | `REDIS_HOST` not set — you didn't `source redis.env` in this shell. |
| `ModuleNotFoundError: redis` | `pip install redis`. |

---

## 12. Security & limits

- `redis.env` is git-ignored — keep it that way; never commit credentials.
- Free tier: 30 MB, ~100 ops/sec, 30 connections — far more than coordination needs.
- `persistence: None` is correct here; locks and counters are meant to be ephemeral.
- Rotate the password from the console if it's ever exposed, then update `redis.env`.
- The free database is reclaimed after ~30 days of inactivity; for production, move to a
  paid Essentials plan.
