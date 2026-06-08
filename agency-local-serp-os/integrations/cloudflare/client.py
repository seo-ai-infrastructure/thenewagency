"""Cloudflare Workers — deploy an edge script that serves approved HTML + Schema.org JSON-LD.
The AIO-speed tactic: static, schema-rich HTML at the edge. Uses the service-worker script
format (application/javascript). fake=True simulates for offline runs. (landed, response)."""
import requests

BASE = "https://api.cloudflare.com/client/v4"

# Wrap raw HTML into a minimal service-worker that serves it with sensible caching.
WORKER_TEMPLATE = """addEventListener('fetch', e => e.respondWith(
  new Response(%s, {headers: {'content-type': 'text/html;charset=UTF-8',
    'cache-control': 'public, max-age=3600'}})));"""


class CloudflareClient:
    def __init__(self, rate_limiter, fake=False):
        self.rl, self.fake = rate_limiter, fake

    @staticmethod
    def wrap_html(html):
        """Embed HTML into an edge worker as a JS string literal (JSON-escaped)."""
        import json
        return WORKER_TEMPLATE % json.dumps(html)

    def deploy_worker(self, account_id, token, script_name, worker_js):
        """PUT a Worker script. Returns (landed, response). CF returns success:false on errors
        (not HTTP error codes), so we read the body rather than raise_for_status."""
        self.rl.acquire()
        if self.fake:
            return True, {"success": True, "result": {"id": script_name, "_fake": True}}
        url = f"{BASE}/accounts/{account_id}/workers/scripts/{script_name}"
        r = requests.put(url, headers={"Authorization": f"Bearer {token}",
                                       "Content-Type": "application/javascript"},
                         data=worker_js.encode("utf-8"), timeout=60)
        try: res = r.json()
        except Exception: res = {"success": False, "errors": [{"message": r.text[:200]}]}
        return bool(res.get("success")), res

    def deploy_html(self, account_id, token, script_name, html):
        """Convenience: wrap raw HTML into a worker and deploy it."""
        return self.deploy_worker(account_id, token, script_name, self.wrap_html(html))
