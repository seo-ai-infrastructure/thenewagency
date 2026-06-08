"""Google Business Profile via Zernio (https://docs.zernio.com/platforms/google-business).
Zernio handles the Google business.manage OAuth during account connection; here we only
need the Zernio API key (Bearer) + the connected accountId. fake=True simulates calls so
the orchestrator runs with no network. Rate-limited via the injected limiter."""
import os

BASE = "https://zernio.com/api/v1"
CONTENT_LIMIT = 1500   # Zernio/Google GBP post character limit

class ZernioGBPClient:
    def __init__(self, rate_limiter, fake=False):
        self.rl, self.fake = rate_limiter, fake

    def _headers(self):
        return {"Authorization": f"Bearer {os.environ['ZERNIO_API_KEY']}",
                "Content-Type": "application/json"}

    def _request(self, method, path, body=None):
        self.rl.acquire()
        if self.fake:
            return {"ok": True, "method": method, "path": path, "_id": "fake_gbp_obj_123"}
        import requests
        r = requests.request(method, BASE + path, headers=self._headers(), json=body, timeout=60)
        r.raise_for_status()
        return r.json()

    def create_local_post(self, account_id, content, media_url=None, location_id=None,
                          topic_type="STANDARD", call_to_action=None, event=None,
                          offer=None, language_code=None, publish_now=True):
        """POST /posts with a googlebusiness platform entry. Returns (landed, response)."""
        if not content or len(content) > CONTENT_LIMIT:
            return False, {"error": f"content empty or exceeds {CONTENT_LIMIT} chars"}
        psd = {}
        if location_id:      psd["locationId"] = location_id
        if topic_type and topic_type != "STANDARD": psd["topicType"] = topic_type
        if call_to_action:   psd["callToAction"] = call_to_action
        if event:            psd["event"] = event
        if offer:            psd["offer"] = offer
        if language_code:    psd["languageCode"] = language_code
        platform = {"platform": "googlebusiness", "accountId": account_id}
        if psd: platform["platformSpecificData"] = psd
        body = {"content": content, "platforms": [platform], "publishNow": publish_now}
        if media_url: body["mediaItems"] = [{"type": "image", "url": media_url}]
        res = self._request("POST", "/posts", body)
        return (bool(res) and "error" not in res), res

    def reply_to_review(self, account_id, review_id, comment):
        """Reply to a GBP review. Path follows Zernio's gmb-reviews pattern — confirm the
        exact reply path against the Reviews API reference when you wire live."""
        res = self._request("POST", f"/accounts/{account_id}/gmb-reviews/{review_id}/reply",
                            {"comment": comment})
        return (bool(res) and "error" not in res), res

    def create_media(self, account_id, source_url, description="", category="ADDITIONAL"):
        res = self._request("POST", f"/accounts/{account_id}/gmb-media",
                            {"sourceUrl": source_url, "description": description, "category": category})
        return (bool(res) and "error" not in res), res


    # --- generic multi-platform (social) — same /posts endpoint, any of Zernio's 14 platforms ---
    def create_post(self, platform, account_id, content, media_url=None,
                    publish_now=True, platform_specific=None, title=None):
        entry = {"platform": platform, "accountId": account_id}
        if platform_specific: entry["platformSpecificData"] = platform_specific
        body = {"content": content, "platforms": [entry], "publishNow": publish_now}
        if media_url: body["mediaItems"] = [{"type": "image", "url": media_url}]
        if title: body["title"] = title
        res = self._request("POST", "/posts", body)
        return (bool(res) and "error" not in res), res

    def cross_post(self, platforms, account_ids, content, media_url=None, publish_now=True):
        entries = [{"platform": p, "accountId": a} for p, a in zip(platforms, account_ids)]
        body = {"content": content, "platforms": entries, "publishNow": publish_now}
        if media_url: body["mediaItems"] = [{"type": "image", "url": media_url}]
        res = self._request("POST", "/posts", body)
        return (bool(res) and "error" not in res), res

    def get_locations(self, account_id):
        return self._request("GET", f"/accounts/{account_id}/gmb-locations")
