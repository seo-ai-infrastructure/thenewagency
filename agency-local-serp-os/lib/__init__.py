"""Shared safety library (policy, approval gate, idempotency, evidence, rate limiter).

Importing the package loads the repo-root .env into os.environ (see lib/env.py) so entry
points pick up API keys / REDIS_HOST without manual exporting — important on Windows where
PowerShell can't `source` a .env. Real environment variables still take precedence.
"""
from .env import load_env

load_env()
