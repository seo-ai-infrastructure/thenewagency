"""WordPress via the REST API + Application Password (self-hosted, ~1 site per client).

Auth is HTTP Basic with a WordPress Application Password (spaces allowed). Per-client
site url + username live in clients/<id>/config/wordpress.yaml; the app password is read
from env by the publisher (never committed). fake=True simulates calls for offline runs.
Rate-limited via the injected limiter. Returns (landed, response) like the Zernio client."""
import requests

WPJSON = "/wp-json"


class WordPressClient:
    def __init__(self, rate_limiter, fake=False):
        self.rl, self.fake = rate_limiter, fake

    def _request(self, method, api_url, path, username, app_password, body=None):
        self.rl.acquire()
        url = api_url.rstrip("/") + WPJSON + path
        if self.fake:
            return {"id": 99001, "link": api_url.rstrip("/") + "/?p=99001",
                    "status": (body or {}).get("status", "draft"), "_fake": True}
        r = requests.request(method, url, auth=(username, app_password),
                             json=body, timeout=60)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _landed(res):
        # WP REST errors carry a "code" (e.g. rest_cannot_create); success carries an int id.
        return bool(res) and "code" not in res and isinstance(res.get("id"), int)

    def create_post(self, api_url, username, app_password, title, content,
                    status="draft", slug=None, excerpt=None, categories=None,
                    tags=None, meta=None, featured_media=None):
        """Create a post/article. status defaults to 'draft' (safe); the publisher passes
        'publish' for approved content. Returns (landed, response)."""
        body = {"title": title, "content": content, "status": status}
        for k, v in (("slug", slug), ("excerpt", excerpt), ("categories", categories),
                     ("tags", tags), ("meta", meta), ("featured_media", featured_media)):
            if v is not None:
                body[k] = v
        res = self._request("POST", api_url, "/wp/v2/posts", username, app_password, body)
        return self._landed(res), res

    def update_post(self, api_url, username, app_password, post_id, **fields):
        res = self._request("POST", api_url, f"/wp/v2/posts/{int(post_id)}",
                            username, app_password, fields or None)
        return self._landed(res), res

    def upload_media(self, api_url, username, app_password, filename, data, content_type):
        """Upload a media binary (for featured images). Returns (landed, response)."""
        self.rl.acquire()
        url = api_url.rstrip("/") + WPJSON + "/wp/v2/media"
        if self.fake:
            return True, {"id": 99002, "source_url": api_url.rstrip("/") + f"/wp-content/{filename}", "_fake": True}
        r = requests.post(url, auth=(username, app_password), data=data,
                          headers={"Content-Disposition": f'attachment; filename="{filename}"',
                                   "Content-Type": content_type}, timeout=120)
        r.raise_for_status()
        res = r.json()
        return self._landed(res), res
