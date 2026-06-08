"""Structured, level-configurable logging (#16). Env:
  LOG_LEVEL=DEBUG|INFO|WARNING|ERROR   (default INFO)
  LOG_JSON=1                           -> one JSON object per line, grep-able in the launchd logs
                                          the board/ops already pipe (filter reason=HELD, stage=approval, ...)
Usage:  log = lib.log.get_logger("tracker"); log.info("done", extra={"run_id": rid, "n": n})
Plain mode prints '[name] message' so it reads like the existing print()s."""
import os, sys, json, logging

_STD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime", "taskName"}


class _JsonFormatter(logging.Formatter):
    def format(self, rec):
        d = {"ts": self.formatTime(rec), "level": rec.levelname, "logger": rec.name,
             "msg": rec.getMessage()}
        for k, v in rec.__dict__.items():                 # extra={...} fields ride along
            if k not in _STD and not k.startswith("_"):
                d[k] = v
        return json.dumps(d, default=str)


def get_logger(name):
    log = logging.getLogger(name)
    if not log.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(_JsonFormatter() if os.environ.get("LOG_JSON")
                       else logging.Formatter("[%(name)s] %(message)s"))
        log.addHandler(h)
        log.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
        log.propagate = False
    return log
