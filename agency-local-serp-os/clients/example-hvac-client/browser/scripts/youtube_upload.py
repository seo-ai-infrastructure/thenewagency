"""CloakBrowser/Playwright: upload an approved video to YouTube (Shorts or long-form) on the
logged-in <client>-cb-agent profile (human-like). run(page, params) with approved content merged in:
    video_path : local file to upload      title : approved title (<=100 chars)
    description/text : approved description  shorts : bool (adds #Shorts)

FAIL-CLOSED: raise on any failure (the runner then marks it failed, no blind retry). YouTube Studio
is a multi-step SPA wizard — verify selectors on the first live run and adjust. Return only when the
publish step completes.
"""
import pathlib

STUDIO_URL = "https://studio.youtube.com/"


def run(page, params):
    video = (params.get("video_path") or "").strip()
    title = (params.get("title") or params.get("text") or "").strip()[:100]
    desc = (params.get("description") or params.get("text") or "").strip()
    if params.get("shorts") and "#shorts" not in desc.lower():
        desc = (desc + "\n\n#Shorts").strip()
    if not video:
        raise RuntimeError("no video_path in params — nothing to upload")

    page.goto(STUDIO_URL, wait_until="domcontentloaded", timeout=60000)

    # Open the upload dialog (Create -> Upload videos), then feed the file input.
    for sel in ("ytcp-button#create-icon", "button[aria-label='Create']", "#create-icon"):
        b = page.query_selector(sel)
        if b:
            b.click(); page.wait_for_timeout(1000); break
    up = page.query_selector("tp-yt-paper-item#text-item-0, a[test-id='upload-beta']")
    if up:
        up.click(); page.wait_for_timeout(1500)

    finput = page.query_selector("input[type=file]")
    if not finput:
        raise RuntimeError("YouTube upload file input not found — verify selectors (Studio changed?)")
    finput.set_input_files(video)
    page.wait_for_timeout(6000)

    # Title + description (contenteditable boxes in the details step).
    boxes = page.query_selector_all("div#textbox, ytcp-social-suggestions-textbox div#textbox")
    if boxes:
        boxes[0].click(); page.keyboard.press("Control+A"); page.keyboard.press("Delete")
        page.keyboard.type(title or pathlib.Path(video).stem)
        if len(boxes) > 1 and desc:
            boxes[1].click(); page.keyboard.type(desc)

    # Advance the wizard (Details -> Video elements -> Checks -> Visibility) then publish.
    for _ in range(3):
        nxt = page.query_selector("ytcp-button#next-button, #next-button button")
        if nxt:
            nxt.click(); page.wait_for_timeout(1500)
    # Set Public, then Publish.
    pub_radio = page.query_selector("tp-yt-paper-radio-button[name='PUBLIC'], #public-radio-button")
    if pub_radio:
        pub_radio.click(); page.wait_for_timeout(800)
    done = page.query_selector("ytcp-button#done-button, #done-button button")
    if not done:
        raise RuntimeError("YouTube Publish/Done button not found — verify selectors")
    done.click(); page.wait_for_timeout(5000)

    confirmed = bool(page.query_selector("text=/video published|processing will continue|uploaded/i")) \
        or "youtu.be" in (page.content() or "")
    if not confirmed:
        raise RuntimeError("no YouTube publish confirmation detected — failing closed")
    return {"posted": True, "platform": "youtube", "video": pathlib.Path(video).name,
            "shorts": bool(params.get("shorts"))}
