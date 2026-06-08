from unittest.mock import patch, MagicMock
from integrations.elevenlabs import client as el


class _RL:
    def acquire(self): pass


def test_tts_returns_audio_bytes():
    c = el.ElevenLabsClient(_RL())
    resp = MagicMock(status_code=200); resp.content = b"MP3DATA"
    with patch.object(el.requests, "post", return_value=resp) as post:
        landed, audio = c.tts("hello world", "voice1", "KEY")
    assert landed is True and audio == b"MP3DATA"
    args, kwargs = post.call_args
    assert "text-to-speech/voice1" in args[0]
    assert kwargs["headers"]["xi-api-key"] == "KEY"
    assert kwargs["json"]["text"] == "hello world"


def test_tts_reports_error():
    c = el.ElevenLabsClient(_RL())
    resp = MagicMock(status_code=401); resp.json.return_value = {"detail": "unauthorized"}
    with patch.object(el.requests, "post", return_value=resp):
        landed, err = c.tts("x", "v", "BAD")
    assert landed is False and "detail" in err


def test_fake_mode_no_network():
    c = el.ElevenLabsClient(_RL(), fake=True)
    with patch.object(el.requests, "post", side_effect=AssertionError("network in fake")):
        landed, audio = c.tts("x", "v", "k")
    assert landed is True and isinstance(audio, bytes)
