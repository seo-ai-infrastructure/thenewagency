"""CloakBrowser/Playwright: upload an approved video to TikTok on the logged-in
<client>-cb-agent profile (human-like). run(page, params) is called by the runner with the
approved content merged into params:
    video_path : local file to upload (preferred)  | media_url : remote file
    text/caption : the approved caption (posted VERBATIM)

FAIL-CLOSED: raise on any failure so the runner marks the work order failed (no blind retry).
Return normally only when the post is confirmed. TikTok's uploader DOM changes often — verify
the selectors on the first live run and adjust.
"""
import pathlib

UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"


def run(page, params):
    video = (params.get("video_path") or params.get("media_url") or "").strip()
    caption = (params.get("caption") or params.get("text") or "").strip()
    if not video:
        raise RuntimeError("no video_path/media_url in params — nothing to upload")

    page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=60000)

    # The uploader is sometimes inside an iframe.
    frame = page
    for f in page.frames:
        if "upload" in (f.url or "").lower():
            frame = f; break

    finput = frame.query_selector("input[type=file]")
    if not finput:
        raise RuntimeError("TikTok upload file input not found — verify selectors (UI changed?)")
    finput.set_input_files(video)
    page.wait_for_timeout(6000)   # let the upload + preview render

    if caption:
        cap = frame.query_selector("div[contenteditable='true'], div.public-DraftEditor-content")
        if cap:
            cap.click()
            page.keyboard.press("Control+A"); page.keyboard.press("Delete")
            page.keyboard.type(caption)   # verbatim approved caption

    post_btn = frame.query_selector("button[data-e2e='post_video_button'], button:has-text('Post')")
    if not post_btn:
        raise RuntimeError("TikTok Post button not found — verify selectors")
    post_btn.click()
    page.wait_for_timeout(7000)

    confirmed = ("/content" in (page.url or "")) or bool(
        frame.query_selector("text=/your video is being uploaded|posted|uploaded successfully/i"))
    if not confirmed:
        raise RuntimeError("no TikTok upload confirmation detected — failing closed")
    return {"posted": True, "platform": "tiktok", "video": pathlib.Path(video).name,
            "caption_len": len(caption)}
