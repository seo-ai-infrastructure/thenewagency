"""Castopod (self-hosted, open-source) — publish a podcast episode. The instance emits the
podcast RSS that Spotify/Apple/YouTube subscribe to, so one publish fans out everywhere.

NOTE: Castopod's REST API path can vary by version — override CASTOPOD_EPISODES_PATH if needed.
fake=True simulates for offline runs. Returns (landed, response)."""
import os, requests


class CastopodClient:
    def __init__(self, rate_limiter, fake=False):
        self.rl, self.fake = rate_limiter, fake

    def create_episode(self, base, token, podcast_id, title, audio_url, description="",
                       season=None, number=None, publish=True):
        self.rl.acquire()
        if self.fake:
            return True, {"id": "ep_fake_001", "title": title, "audio_url": audio_url, "_fake": True}
        path = os.environ.get("CASTOPOD_EPISODES_PATH",
                              f"/api/rest/v1/podcasts/{podcast_id}/episodes")
        body = {"title": title, "audio_url": audio_url, "description": description, "publish": publish}
        if season is not None: body["season_number"] = season
        if number is not None: body["episode_number"] = number
        r = requests.post(base.rstrip("/") + path,
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                          json=body, timeout=60)
        try: res = r.json()
        except Exception: res = {"error": r.text[:200]}
        landed = r.status_code < 300 and isinstance(res, dict) and "error" not in res
        return landed, res
