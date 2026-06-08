"""ElevenLabs text-to-speech. Returns MP3 audio bytes for voice/podcast workflows.
fake=True returns deterministic stub bytes for offline runs. Returns (landed, bytes|error)."""
import requests

BASE = "https://api.elevenlabs.io/v1"


class ElevenLabsClient:
    def __init__(self, rate_limiter, fake=False):
        self.rl, self.fake = rate_limiter, fake

    def tts(self, text, voice_id, api_key, model_id="eleven_multilingual_v2", voice_settings=None):
        """Synthesize speech. On success returns (True, mp3_bytes); on failure (False, err_dict)."""
        self.rl.acquire()
        if self.fake:
            return True, b"ID3FAKE_MP3_AUDIO_BYTES"
        body = {"text": text, "model_id": model_id}
        if voice_settings: body["voice_settings"] = voice_settings
        r = requests.post(f"{BASE}/text-to-speech/{voice_id}",
                          headers={"xi-api-key": api_key, "accept": "audio/mpeg",
                                   "content-type": "application/json"},
                          json=body, timeout=180)
        if r.status_code >= 300:
            try: return False, r.json()
            except Exception: return False, {"error": r.text[:200], "status": r.status_code}
        return True, r.content
