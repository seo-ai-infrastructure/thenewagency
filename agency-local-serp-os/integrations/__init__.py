"""Integration clients (DataForSEO, DuoPlus, Zernio/GBP, CloakBrowser, Higgsfield media, LLM).

Importing the package loads the repo-root .env (via lib.env) so API keys are available
without manual exporting on Windows. Guarded so it never breaks if lib isn't importable yet.
"""
try:
    from lib.env import load_env
    load_env()
except Exception:
    pass
