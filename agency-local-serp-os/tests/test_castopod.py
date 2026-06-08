from unittest.mock import patch, MagicMock
from integrations.castopod import client as cp


class _RL:
    def acquire(self): pass


def test_create_episode_posts_with_auth_and_fields():
    c = cp.CastopodClient(_RL())
    resp = MagicMock(status_code=201); resp.json.return_value = {"id": "ep_5", "title": "Ep 1"}
    with patch.object(cp.requests, "post", return_value=resp) as post:
        landed, res = c.create_episode("https://pod.example.com/", "TOK", "pod1", "Ep 1",
                                       "https://cdn/x.mp3", description="d", number=5)
    assert landed is True and res["id"] == "ep_5"
    kwargs = post.call_args.kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer TOK"
    assert kwargs["json"]["title"] == "Ep 1" and kwargs["json"]["episode_number"] == 5


def test_create_episode_detects_error():
    c = cp.CastopodClient(_RL())
    resp = MagicMock(status_code=422); resp.json.return_value = {"error": "invalid"}
    with patch.object(cp.requests, "post", return_value=resp):
        landed, res = c.create_episode("https://pod.example.com", "T", "p", "t", "u")
    assert landed is False


def test_fake_mode_no_network():
    c = cp.CastopodClient(_RL(), fake=True)
    with patch.object(cp.requests, "post", side_effect=AssertionError("network in fake")):
        landed, res = c.create_episode("b", "t", "p", "Title", "u")
    assert landed is True and res["_fake"] is True
