"""CloakBrowser integration — stealth Chromium (drop-in Playwright) driven per persistent
profile. Each profile = its own fingerprint + proxy + persistent user_data_dir, so cookies
and account logins survive between runs (no re-login). fake=True simulates everything for
dry-runs.

Live wiring uses the `cloakbrowser` package (pip install cloakbrowser):
    launch_persistent_context(user_data_dir=..., proxy="http://user:pass@host:port",
                              geoip=True, humanize=True, headless=False)  -> Playwright BrowserContext
The stealth Chromium binary downloads to ~/.cloakbrowser/ on first launch (or pre-fetch with
`python -c "import cloakbrowser; cloakbrowser.ensure_binary()"`).

ctx handle (returned by launch, passed back to verify/run/close) is a dict:
    {"profile_id": str, "fake": bool, "context": BrowserContext|None, "page": Page|None}
"""
import os, json, time, threading, importlib.util, pathlib


class CloakBrowserClient:
    def __init__(self, rate_limiter, fake=False):
        self.rl = rate_limiter; self.fake = fake

    def _resolve_proxy(self, profile):
        """profile['proxy_ref'] (e.g. 'proxy_01') -> env PROXY_01 = 'http://user:pass@host:port'."""
        ref = profile.get("proxy_ref")
        if not ref:
            return None
        val = os.environ.get(ref.upper())
        if not val:
            raise RuntimeError(f"proxy_ref '{ref}' is set but env {ref.upper()} is empty — add it "
                               f"to .env, e.g. {ref.upper()}=http://user:pass@host:port")
        return val

    def launch(self, profile):
        self.rl.acquire()
        if self.fake:
            return {"profile_id": profile["profile_id"], "fake": True, "context": None, "page": None,
                    "user_data_dir": profile.get("user_data_dir"),
                    "logged_in_as": profile.get("expected_account")}      # persistent session pretended
        import cloakbrowser
        udd = pathlib.Path(os.path.expanduser(profile["user_data_dir"]))  # ~ resolves on Windows too
        udd.mkdir(parents=True, exist_ok=True)
        kw = dict(user_data_dir=str(udd), proxy=self._resolve_proxy(profile),
                  humanize=True, headless=profile.get("headless", False),
                  args=["--remote-debugging-port=0"])   # local CDP for agent_task (browser-use bridge)
        try:                                     # geoip: match tz/locale to the proxy exit (stealth)
            ctx = cloakbrowser.launch_persistent_context(geoip=True, **kw)
        except ImportError:                      # geoip2 not installed -> degrade (pip install cloakbrowser[geoip])
            ctx = cloakbrowser.launch_persistent_context(geoip=False, **kw)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        return {"profile_id": profile["profile_id"], "fake": False, "context": ctx, "page": page,
                "user_data_dir": str(udd)}

    def verify_profile(self, ctx, profile):
        """Verify-before-act: confirm the persistent session is the expected account."""
        if self.fake:
            if profile.get("simulate_verify_fail"): return False
            return ctx.get("logged_in_as") == profile.get("expected_account")
        expected = profile.get("expected_account")
        if not expected:
            return True                          # nothing to verify against (pure read-only recon)
        verify_url = profile.get("verify_url")
        if not verify_url:
            # Can't confirm identity without a page that shows the logged-in account — fail closed.
            print("    verify: profile has expected_account but no verify_url — failing closed "
                  "(set profiles.yaml verify_url to an account page that shows the login, "
                  "or clear expected_account for unverified read-only profiles)")
            return False
        try:
            page = ctx["page"]
            page.goto(verify_url, wait_until="domcontentloaded", timeout=30000)
            return expected.lower() in (page.content() or "").lower()
        except Exception as e:
            print(f"    verify error: {type(e).__name__}: {e}")
            return False

    def run_script(self, ctx, script_path, params):
        """Deterministic Playwright workflow: import the module at script_path, call run(page, params)."""
        self.rl.acquire()
        if self.fake:
            return True, {"kind": "playwright_script", "script": script_path,
                          "params": params, "observed": "fake run ok"}
        try:
            mod = self._load_module(script_path)
            result = mod.run(ctx["page"], params)
            return True, {"kind": "playwright_script", "script": script_path, **(result or {})}
        except Exception as e:
            return False, {"kind": "playwright_script", "script": script_path,
                           "error": f"{type(e).__name__}: {e}"}

    @staticmethod
    def _landed_from_success(success, require_success=False):
        """Read-only scans may not expose a success flag; public actions must."""
        return success is True if require_success else success is not False

    def run_agent_task(self, ctx, goal, params, require_success=False):
        """Tier-4 agentic browser use: a Claude-driven browser-use Agent attaches to THIS stealth
        browser via CDP and pursues `goal`. Read-only by default; any public action must already
        be approved upstream (the approved text arrives in params). Returns (landed, report)."""
        self.rl.acquire()
        if self.fake:
            return True, {"kind": "agent_task", "goal": goal, "params": params,
                          "summary": "fake agent observation: 0 new items", "success": True}
        try:
            import browser_use  # noqa: F401
        except ImportError:
            return False, {"kind": "agent_task", "error": "agent_task needs browser-use (pip install browser-use)"}
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return False, {"kind": "agent_task", "error": "set ANTHROPIC_API_KEY for agent_task"}
        port = self._cdp_port(ctx)
        if not port:
            return False, {"kind": "agent_task", "error": "no CDP port on the launched browser"}
        task = goal if not params else f"{goal}\n\nInputs (JSON): {json.dumps(params)}"
        out = {}

        def worker():
            import asyncio
            from browser_use import Agent, Browser, ChatAnthropic
            async def go():
                browser = Browser(cdp_url=f"http://127.0.0.1:{port}")
                llm = ChatAnthropic(model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5"), api_key=key)
                agent = Agent(task=task, llm=llm, browser=browser)
                hist = await agent.run(max_steps=int(os.environ.get("AGENT_MAX_STEPS", "25")))
                success = hist.is_successful() if hasattr(hist, "is_successful") else None
                return {"result": hist.final_result(), "success": success}
            loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
            try:
                out["data"] = loop.run_until_complete(go())
            except Exception as e:
                out["err"] = f"{type(e).__name__}: {e}"
            finally:
                loop.close()

        th = threading.Thread(target=worker, daemon=True); th.start()
        th.join(timeout=int(os.environ.get("AGENT_TIMEOUT", "360")))
        if th.is_alive():
            return False, {"kind": "agent_task", "goal": goal, "error": "agent timed out"}
        if "err" in out:
            return False, {"kind": "agent_task", "goal": goal, "error": out["err"]}
        data = out.get("data") or {}
        success = data.get("success")
        landed = self._landed_from_success(success, require_success=require_success)
        return landed, {"kind": "agent_task", "goal": goal, "summary": data.get("result"), "success": success}

    @staticmethod
    def _cdp_port(ctx):
        udd = ctx.get("user_data_dir") if isinstance(ctx, dict) else None
        if not udd:
            return None
        f = pathlib.Path(udd) / "DevToolsActivePort"
        for _ in range(20):
            if f.exists():
                try:
                    return f.read_text().splitlines()[0].strip()
                except Exception:
                    return None
            time.sleep(0.3)
        return None

    def close(self, ctx):
        if self.fake:
            return
        c = ctx.get("context") if isinstance(ctx, dict) else None
        if c is not None:
            try: c.close()
            except Exception: pass

    @staticmethod
    def _load_module(script_path):
        p = pathlib.Path(script_path)
        spec = importlib.util.spec_from_file_location(p.stem, str(p))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
