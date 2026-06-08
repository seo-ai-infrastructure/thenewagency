"""Outbound notifier (Telegram and/or Discord). Notify-OUT only — never an approval channel.
Reads env: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID, and/or DISCORD_WEBHOOK_URL. If none set, it
no-ops silently. NOTIFY_DEBUG=1 prints instead of sending (used by dry-runs/tests). A send
failure (e.g. no network) is swallowed so it can never break a pipeline run."""
import os, json, urllib.request, urllib.parse

EMOJI = {"info": "•", "approval": "🟡", "error": "🔴", "ok": "🟢", "digest": "📋"}

def send(text, level="info"):
    text = f"{EMOJI.get(level,'•')} {text}"
    if os.environ.get("NOTIFY_DEBUG"):
        print(f"[notify:{level}] {text}"); return True
    sent = False
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
            urllib.request.urlopen(urllib.request.Request(
                f"https://api.telegram.org/bot{tok}/sendMessage", data=data), timeout=10).read()
            sent = True
        except Exception as e: print(f"[notify] telegram failed: {e}")
    hook = os.environ.get("DISCORD_WEBHOOK_URL")
    if hook:
        try:
            urllib.request.urlopen(urllib.request.Request(
                hook, data=json.dumps({"content": text}).encode(),
                headers={"Content-Type": "application/json"}), timeout=10).read()
            sent = True
        except Exception as e: print(f"[notify] discord failed: {e}")
    return sent
