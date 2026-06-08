"""Redis-backed coordination for multi-machine setups. Drop-in replacements for the
single-machine file lock + file rate limiter. Used by the orchestrator only when
REDIS_HOST is set in env; otherwise the file-based versions are used (dry-run/offline).

Setup (Redis Cloud free tier): create a free DB at redis.io/cloud, then export
REDIS_HOST / REDIS_PORT / REDIS_PASSWORD / REDIS_CA (CA path; omit to disable TLS)."""
import os, time, uuid


def get_redis():
    import redis  # lazy import so this module loads even when redis isn't installed
    kwargs = dict(
        host=os.environ["REDIS_HOST"], port=int(os.environ["REDIS_PORT"]),
        password=os.environ.get("REDIS_PASSWORD"),
        decode_responses=True, socket_timeout=5, socket_connect_timeout=5,
    )
    ca = os.environ.get("REDIS_CA")
    if ca:                                  # TLS (recommended; uses the CA you downloaded)
        kwargs.update(ssl=True, ssl_ca_certs=ca)
    return redis.Redis(**kwargs)


class RedisRateLimiter:
    """Account-global ≤ max_per_sec across ALL machines (fixed 1-second window).
    Matches the file RateLimiter interface: .acquire()."""
    def __init__(self, client, key="duoplus:ratelimit", max_per_sec=1, fake=False):
        self.r, self.key, self.max, self.fake = client, key, max_per_sec, fake

    def acquire(self):
        if self.fake:
            return
        while True:
            sec = int(time.time())
            k = f"{self.key}:{sec}"
            pipe = self.r.pipeline()        # MULTI/EXEC: incr + expire apply atomically,
            pipe.incr(k); pipe.expire(k, 2) # so a crash can't leave a key without a TTL
            n = pipe.execute()[0]
            if n <= self.max:
                return
            time.sleep(max(0, (sec + 1) - time.time()) + 0.001)


class RedisLock:
    """Distributed phone/profile lock (SET NX PX). TTL prevents deadlock if a worker
    dies mid-run. Release is an atomic check-and-delete so you only free your own lock."""
    _RELEASE = ("if redis.call('get', KEYS[1]) == ARGV[1] then "
                "return redis.call('del', KEYS[1]) else return 0 end")

    def __init__(self, client):
        self.r = client

    def acquire(self, name, ttl_ms=600_000):
        """Returns a handle ('redis', name, token) if acquired, else None."""
        token = str(uuid.uuid4())
        if self.r.set(f"lock:{name}", token, nx=True, px=ttl_ms):
            return ("redis", name, token)
        return None

    def release(self, handle):
        _, name, token = handle
        self.r.eval(self._RELEASE, 1, f"lock:{name}", token)
