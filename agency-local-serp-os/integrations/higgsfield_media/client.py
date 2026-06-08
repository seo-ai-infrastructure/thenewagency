"""Higgsfield media backend — image/video generation via the authenticated `higgsfield` CLI
(npm install, `higgsfield auth login`). Interface: generate_image / animate_image.
Image -> GPT Image 2 by default; image-to-video -> Veo 3.1 Lite (works on the starter plan;
Seedance 2.0 needs Pro). Veo via Higgsfield is fine — it's the Higgsfield platform, not a
direct Google Cloud account. Durations allowed: 4, 6, 8.

Selected by video-producer when MEDIA_BACKEND=higgsfield. fake=True writes placeholder bytes
so the gated pipeline is fully dry-runnable with no credits spent. Live calls SPEND credits.

Env overrides: HIGGSFIELD_IMAGE_MODEL, HIGGSFIELD_VIDEO_MODEL, HIGGSFIELD_VIDEO_SECONDS,
HIGGSFIELD_TIMEOUT.
"""
import os, re, shutil, subprocess, pathlib

_URL_RE = re.compile(r"https?://[^\s'\"]+\.(?:png|jpg|jpeg|webp|mp4|mov)", re.IGNORECASE)


class HiggsfieldMediaClient:
    def __init__(self, rate_limiter=None, fake=False,
                 image_model=None, video_model=None):
        self.rl = rate_limiter; self.fake = fake
        self.image_model = image_model or os.environ.get("HIGGSFIELD_IMAGE_MODEL", "gpt_image_2")
        self.video_model = video_model or os.environ.get("HIGGSFIELD_VIDEO_MODEL", "veo3_1_lite")

    def _cli(self):
        exe = shutil.which("higgsfield") or shutil.which("higgsfield.cmd")
        if not exe:
            raise RuntimeError("higgsfield CLI not found on PATH (npm i -g, then `higgsfield auth login`)")
        return exe

    def _run(self, model, args, retries=2):
        """higgsfield generate create <model> ... --wait ; return the result media URL or None.
        Retries on transient API errors (HTTP 5xx / 429 / timeout)."""
        import time
        cmd = [self._cli(), "generate", "create", model, *args, "--wait"]
        blob = ""
        for attempt in range(retries + 1):
            if self.rl:
                self.rl.acquire()
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=int(os.environ.get("HIGGSFIELD_TIMEOUT", "900")))
            blob = (p.stdout or "") + "\n" + (p.stderr or "")
            urls = _URL_RE.findall(blob)
            if urls:
                return urls[-1], blob
            if not re.search(r"HTTP 5\d\d|\b429\b|timeout|temporar", blob, re.IGNORECASE):
                break                                    # non-transient -> don't waste credits retrying
            time.sleep(3 * (attempt + 1))                # transient -> backoff and retry
        return None, blob

    @staticmethod
    def _download(url, out_path):
        import requests
        r = requests.get(url, timeout=180); r.raise_for_status()
        pathlib.Path(out_path).write_bytes(r.content)

    # ---- image (GPT Image 2 by default) ----
    def generate_image(self, prompt, out_path):
        out_path = pathlib.Path(out_path); out_path.parent.mkdir(parents=True, exist_ok=True)
        if self.fake:
            out_path.write_bytes(b"\x89PNG\r\n\x1a\n[FAKE HIGGSFIELD IMAGE] " + prompt[:60].encode())
            return True, {"model": "fake-image", "path": str(out_path)}
        url, blob = self._run(self.image_model, ["--prompt", prompt, "--aspect_ratio", "16:9", "--resolution", "2k"])
        if not url:
            return False, {"error": "no media url from higgsfield", "model": self.image_model, "detail": blob[-200:]}
        self._download(url, out_path)
        return True, {"model": self.image_model, "path": str(out_path), "url": url}

    # ---- video (Seedance 2.0 image-to-video) ----
    def animate_image(self, image_path, prompt, out_path, aspect_ratio="9:16",
                      resolution="720p", poll_seconds=20, timeout_seconds=600):
        out_path = pathlib.Path(out_path); out_path.parent.mkdir(parents=True, exist_ok=True)
        if self.fake:
            out_path.write_bytes(b"[FAKE HIGGSFIELD MP4 from " + str(image_path).encode() + b"] " + prompt[:60].encode())
            return True, {"model": "fake-video", "path": str(out_path)}
        url, blob = self._run(self.video_model, [
            "--prompt", prompt, "--start-image", str(image_path),
            "--duration", os.environ.get("HIGGSFIELD_VIDEO_SECONDS", "6")])   # Veo allows 4/6/8
        if not url:
            return False, {"error": "no media url from higgsfield", "model": self.video_model, "detail": blob[-200:]}
        self._download(url, out_path)
        return True, {"model": self.video_model, "path": str(out_path), "url": url}
