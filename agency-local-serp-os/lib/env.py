"""Load the repo-root .env into os.environ for local/dev runs.

Nothing else in this codebase reads a .env file — env vars are read straight from
os.environ at call time. This loader fills os.environ from .env at package import so
`python automations/.../run.py` works on Windows without manually exporting every var
in each PowerShell session.

Real environment variables ALWAYS win over .env (override=False): a value you set with
`$env:FOO=...` in PowerShell, or a CI/launchd secret, is never clobbered by the file.

Format: `KEY=VALUE`, optional `export ` prefix, optional surrounding single/double
quotes, `#` full-line comments, blank lines ignored. Values are taken verbatim (no
escape processing) so Windows paths like `C:\\Users\\...` survive intact.
"""
import os, re, pathlib

_DEFAULT = pathlib.Path(__file__).resolve().parent.parent / ".env"
_loaded = False


def load_env(path=None, override=False):
    """Populate os.environ from a .env file. Default path is the repo-root .env, and the
    default call (no path) loads at most once per process. Returns the dict it applied."""
    global _loaded
    target = pathlib.Path(path) if path else _DEFAULT
    if path is None:
        if _loaded:
            return {}
        _loaded = True
    if not target.exists():
        return {}
    applied = {}
    for raw in target.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        if not key:
            continue
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]                      # quoted: literal value, keep any '#'
        else:
            m = re.search(r"\s#", val)           # unquoted: strip an inline comment (" #...")
            if m:
                val = val[:m.start()].rstrip()
        if override or key not in os.environ:    # real env wins unless override
            os.environ[key] = val
            applied[key] = val
    return applied
