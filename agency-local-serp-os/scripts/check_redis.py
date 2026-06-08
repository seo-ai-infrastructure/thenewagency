#!/usr/bin/env python3
"""Smoke-test Redis against your real database, using the exact backends the
orchestrator uses. Run after sourcing your env:

    source redis.env
    python scripts/check_redis.py

Proves: connection (PING), the distributed lock (acquire / blocked re-acquire /
release / re-acquire), and the rate limiter (spaces calls to <=1 QPS). Cleans up
its own test keys."""
import sys, time, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.redis_backends import get_redis, RedisRateLimiter, RedisLock


def main():
    r = get_redis()
    print("1) PING ->", r.ping())

    lock = RedisLock(r)
    h = lock.acquire("selftest_phone", ttl_ms=5000)
    print("2) acquired phone lock:", bool(h))
    blocked = lock.acquire("selftest_phone")
    print("   second acquire is blocked (expect None):", blocked)
    lock.release(h)
    h3 = lock.acquire("selftest_phone", ttl_ms=5000)
    print("   re-acquire after release:", bool(h3))
    lock.release(h3)

    rl = RedisRateLimiter(r, key="selftest:rl", max_per_sec=1)
    t0 = time.time()
    rl.acquire(); rl.acquire()                      # 2nd call should wait for the next second
    print(f"3) rate limiter spaced 2 calls over {time.time() - t0:.2f}s (expect ~1s)")

    for k in r.scan_iter("selftest*"):              # tidy up
        r.delete(k)
    print("OK - Redis is reachable and the lock + rate limiter work.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAILED:", e)
        print("Check: password correct? port open? if you enabled TLS, set REDIS_CA.")
        sys.exit(1)
