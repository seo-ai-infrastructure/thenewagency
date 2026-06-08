"""Account-global rate limiter for DuoPlus (1 QPS per interface). File-based so it is
shared across ALL orchestrator runs/processes — the limit is account-wide, not per-run."""
import os, time, pathlib

class RateLimiter:
    def __init__(self, state_file, min_interval=1.0, fake=False):
        self.f = pathlib.Path(state_file); self.min = min_interval; self.fake = fake
        self.f.parent.mkdir(parents=True, exist_ok=True)

    def acquire(self):
        if self.fake:
            return
        lock = self.f.with_suffix(".lock")
        token = f"{os.getpid()}-{time.time()}".encode()   # so we only ever delete OUR lock
        for _ in range(2000):                       # cross-process spin lock (~20s)
            try:
                fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, token); os.close(fd); break
            except FileExistsError:
                # Steal a lock left behind by a crashed run. The critical section is
                # sub-second, so a lock older than 30s means the holder is gone; without
                # this, one crash wedges the limiter for every future run.
                try:
                    if time.time() - lock.stat().st_mtime > 30:
                        lock.unlink(missing_ok=True); continue
                except FileNotFoundError:
                    continue
                time.sleep(0.01)
        else:
            # Never acquired. Fail loudly rather than proceed UNLOCKED (which would let
            # two processes fire simultaneously and trip the account-wide QPS limit).
            raise TimeoutError("rate-limiter: could not acquire lock after 20s of contention")
        try:
            last = float(self.f.read_text()) if self.f.exists() else 0.0
            wait = self.min - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
            self.f.write_text(str(time.time()))
        finally:
            # Only remove the lock if it is still ours — a 30s stall could have let
            # another process steal it, and we must not delete a live holder's lock.
            try:
                if lock.read_bytes() == token:
                    lock.unlink(missing_ok=True)
            except FileNotFoundError:
                pass
