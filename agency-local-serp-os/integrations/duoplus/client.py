"""DuoPlus client — wired to the real DuoPlus Open API (verified live, June 2026).

Base:  https://openapi.duoplus.cn/api/v1   (override with DUOPLUS_API_BASE)
Auth:  header DuoPlus-API-Key = $DUOPLUS_API_KEY
Envelope: {"code":200, "data":{...}, "message":"Success"}  (code != 200 -> error)
Limit: 1 QPS per interface, enforced by the shared RateLimiter.

DuoPlus reality (differs from the original spec): each cloud phone IS a fixed identity —
its own IP/proxy/GPS/SIM, set at provisioning. There is NO "profile switch"; a profile in
profiles.yaml maps 1:1 to a cloud phone (its duoplus_image_id). So:
  - phone_status / power_on : real endpoints (cloudPhone/status, cloudPhone/powerOn)
  - bind_proxy_location     : NO-OP by default (phone is pre-provisioned); re-binds only if
                              the profile sets rebind_proxy: true (via cloudPhone/initProxy)
  - switch_profile          : NO-OP (the phone is the identity)
  - verify_profile          : confirms the phone is powered on; the DuoPlus API exposes no
                              logged-in app account, so account-level verify-before-act must
                              be a step INSIDE the RPA template (screenshot/check)
  - run_workflow            : automation/addTask (run a template) -> find task via
                              automation/taskList -> poll automation/taskLogList for result.
                              FAIL-CLOSED: anything we can't confirm as success => not landed.

fake=True simulates everything (no network) so the whole flow is dry-runnable with no device.
Methods take a DuoPlus image_id (the orchestrator resolves phone_id -> duoplus_image_id).
"""
import os, time, datetime

API_KEY_HEADER = "DuoPlus-API-Key"
_FMT = "%Y-%m-%d %H:%M:%S"          # taskList window bounds
_ISSUE_FMT = "%Y-%m-%d %H:%M"       # addTask "Publish Time" — MUST be minute precision (verified live; seconds -> 400)


class DuoPlusClient:
    def __init__(self, rate_limiter, fake=False):
        self.rl, self.fake = rate_limiter, fake
        self.base = os.environ.get("DUOPLUS_API_BASE", "https://openapi.duoplus.cn/api/v1").rstrip("/")
        self.template_type = int(os.environ.get("DUOPLUS_TEMPLATE_TYPE", "2"))   # 1=official, 2=custom

    # ---- HTTP core ----
    def _request(self, path, body):
        self.rl.acquire()                                   # account-global 1 QPS
        import requests
        r = requests.post(f"{self.base}/{path}",
                          headers={API_KEY_HEADER: os.environ["DUOPLUS_API_KEY"],
                                   "Content-Type": "application/json"},
                          json=body, timeout=60)
        r.raise_for_status()
        j = r.json()
        if j.get("code") != 200:
            raise RuntimeError(f"DuoPlus {path} -> code={j.get('code')} {j.get('message')}")
        return j.get("data") or {}

    # ---- control / provisioning ----
    def phone_status(self, image_id):
        if self.fake:
            return {"id": image_id, "status": 1}
        lst = self._request("cloudPhone/status", {"image_ids": [image_id]}).get("list") or []
        return lst[0] if lst else {"id": image_id, "status": None}

    def power_on(self, image_id, wait=True, timeout=120, poll=5):
        if self.fake:
            return {"ok": True}
        self._request("cloudPhone/powerOn", {"image_ids": [image_id]})   # async
        if not wait:
            return {"ok": True, "async": True}
        waited = 0
        while waited < timeout:
            if (self.phone_status(image_id) or {}).get("status") == 1:   # 1 = powered on
                return {"ok": True, "status": 1}
            time.sleep(poll); waited += poll
        return {"ok": False, "status": "timeout"}

    def power_off(self, image_id):
        if self.fake:
            return {"ok": True}
        return self._request("cloudPhone/powerOff", {"image_ids": [image_id]})

    def bind_proxy_location(self, profile, proxy, location):
        """Phones are pre-provisioned with their proxy + GPS, so this is a NO-OP by default.
        Set profile rebind_proxy: true ONLY if you really want to re-assign via the API."""
        if self.fake:
            return {"proxy": proxy.get("id"), "location": location.get("name"), "bound": True}
        if not profile.get("rebind_proxy"):
            return {"location": location.get("name") or "(provisioned)", "bound": False,
                    "note": "phone pre-provisioned; no re-bind"}
        image_id = profile.get("duoplus_image_id") or profile.get("phone_id")
        body = {"image_id": image_id, "proxy": {}}
        if proxy.get("id"):     body["proxy"]["id"] = proxy["id"]
        if proxy.get("host"):   body["proxy"].update({"host": proxy["host"], "port": proxy.get("port"),
                                                      "user": proxy.get("user"), "password": proxy.get("password")})
        if location.get("lat") is not None and location.get("lng") is not None:
            body["location"] = {"latitude": location["lat"], "longitude": location["lng"]}
        self._request("cloudPhone/initProxy", body)
        return {"location": location.get("name"), "bound": True}

    def switch_profile(self, image_id, profile_id):
        # No-op: a DuoPlus cloud phone is a single fixed identity (no in-phone profile switch).
        return {"ok": True, "note": "no-op (DuoPlus phone = fixed identity)"}

    def verify_profile(self, image_id, profile):
        """Confirm the phone is the right one and powered on. The DuoPlus API exposes no
        logged-in app account, so app-account verification must be a step in the RPA template."""
        if self.fake:
            return not profile.get("simulate_verify_fail", False)
        status = (self.phone_status(image_id) or {}).get("status")
        if status != 1:
            print(f"    verify: phone {image_id} not powered on (status={status})")
            return False
        region = profile.get("expected_proxy_region")           # optional identity cross-check
        if region:
            info = self._request("cloudPhone/info", {"image_id": image_id})
            got = ((info.get("proxy") or {}).get("region") or "").lower()
            if region.lower() not in got:
                print(f"    verify: proxy region '{got}' != expected '{region}'")
                return False
        return True

    # ---- in-app workflow (native RPA template) ----
    def run_workflow(self, image_id, template_id, profile, task_params=None):
        """Run a DuoPlus RPA template and CONFIRM it landed. Returns (landed, report).
        Template inputs come from profile['template_config'] (static defaults/types), with
        per-run values from the work order's task_params overriding by key."""
        if self.fake:
            if profile.get("simulate_fail"):
                return False, {"status": "failed", "template": template_id}
            return True, {"status": "succeeded", "template": template_id, "steps": 4}
        if not template_id:
            return False, {"status": "failed", "error": "workflow has no duoplus_template_id"}
        name = f"agency-{template_id}-{int(time.time())}"
        self._request("automation/addTask", {
            "template_id": template_id, "template_type": self.template_type,
            "name": name, "remark": "agency-local-serp-os",
            "images": [{"image_id": image_id,
                        "issue_at": datetime.datetime.now().strftime(_ISSUE_FMT),
                        "config": self._merge_config(profile.get("template_config", []), task_params)}]})
        task_id = self._find_task_id(name)                      # addTask returns no id
        if not task_id:
            return False, {"status": "unknown", "error": "task created but not found in taskList", "name": name}
        return self._await_result(task_id)

    def _task_window(self):
        # Wide, TZ-proof window: the API filters issue_at in UTC+8, our clock may be anywhere.
        # +1d future / -2d past absorbs the offset; span < 7d (API retains only 7 days).
        now = datetime.datetime.now()
        return (now - datetime.timedelta(days=2)).strftime(_FMT), (now + datetime.timedelta(days=1)).strftime(_FMT)

    def _find_task_id(self, name, tries=10, poll=2):
        for _ in range(tries):
            s, e = self._task_window()
            data = self._request("automation/taskList", {
                "issue_at_start": s, "issue_at_end": e, "name": name,
                "sort_by": "created_at", "order": "desc", "page": 1, "pagesize": 10})
            for t in data.get("list", []):
                if t.get("name") == name:
                    return t.get("id")
            time.sleep(poll)
        return None

    def _await_result(self, task_id, timeout=600, poll=10):
        waited = 0
        while waited < timeout:
            s, e = self._task_window()
            data = self._request("automation/taskList", {
                "issue_at_start": s, "issue_at_end": e, "id": task_id, "page": 1, "pagesize": 10})
            entry = next((t for t in data.get("list", []) if t.get("id") == task_id), None)
            if entry and entry.get("finish_at"):               # task done
                return self._evaluate_logs(task_id, entry)
            time.sleep(poll); waited += poll
        return False, {"status": "timeout", "task_id": task_id}

    def _evaluate_logs(self, task_id, entry):
        logs = self._request("automation/taskLogList", {"task_id": task_id}).get("list") or []
        failures = [l for l in logs if not (l.get("result_info") or {}).get("result", True)]
        landed = bool(logs) and not failures                   # fail-closed: no logs => not landed
        rep = {"status": "succeeded" if landed else "failed", "task_id": task_id,
               "actions": len(logs), "finish_at": entry.get("finish_at")}
        if failures:
            rep["error"] = (failures[0].get("result_info") or {}).get("error_message")
        return landed, rep

    @staticmethod
    def _merge_config(base, params):
        """DuoPlus addTask config = [{key,value,type,required}]. Start from the static base
        (profile template_config), then apply per-run task_params: override an existing key's
        value, or append a new string param. Returns the merged list."""
        cfg = [dict(e) for e in (base or [])]
        idx = {e.get("key"): e for e in cfg}
        for k, v in (params or {}).items():
            if k in idx:
                idx[k]["value"] = v
            else:
                cfg.append({"key": k, "value": v, "type": "string", "required": False})
        return cfg

    def adb(self, image_id, command):
        # Diagnostics only (endpoint slug: execute-the-adb-command). Not on the posting hot path;
        # confirm the exact payload in the DuoPlus docs before relying on it.
        raise NotImplementedError("adb: wire cloudPhone ADB endpoint (execute-the-adb-command) if needed")
