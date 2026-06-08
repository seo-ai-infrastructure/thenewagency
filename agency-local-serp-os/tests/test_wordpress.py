from unittest.mock import patch, MagicMock
from integrations.wordpress import client as wp


class _RL:
    def acquire(self):
        pass


def _resp(json_obj, status=200):
    r = MagicMock(status_code=status)
    r.json.return_value = json_obj
    r.raise_for_status.return_value = None
    return r


def test_create_post_builds_rest_call_and_reports_landed():
    c = wp.WordPressClient(_RL())
    resp = _resp({"id": 451, "link": "https://site.com/?p=451", "status": "publish"})
    with patch.object(wp.requests, "request", return_value=resp) as req:
        landed, res = c.create_post("https://site.com/", "admin", "app pass word",
                                    title="AC Repair", content="<p>hi</p>", status="publish",
                                    slug="ac-repair", categories=[3])
    assert landed is True and res["id"] == 451
    args, kwargs = req.call_args
    assert args[0] == "POST"
    assert args[1] == "https://site.com/wp-json/wp/v2/posts"   # no double slash, wp-json appended
    assert kwargs["auth"] == ("admin", "app pass word")        # app password spaces preserved
    assert kwargs["json"]["title"] == "AC Repair"
    assert kwargs["json"]["status"] == "publish"
    assert kwargs["json"]["slug"] == "ac-repair"
    assert kwargs["json"]["categories"] == [3]


def test_create_post_detects_wp_error():
    c = wp.WordPressClient(_RL())
    resp = _resp({"code": "rest_cannot_create", "message": "nope"}, status=201)
    with patch.object(wp.requests, "request", return_value=resp):
        landed, res = c.create_post("https://site.com", "u", "p", "t", "body")
    assert landed is False and res["code"] == "rest_cannot_create"


def test_default_status_is_draft():
    c = wp.WordPressClient(_RL())
    resp = _resp({"id": 1, "status": "draft"})
    with patch.object(wp.requests, "request", return_value=resp) as req:
        c.create_post("https://site.com", "u", "p", "t", "body")
    assert req.call_args.kwargs["json"]["status"] == "draft"


def test_fake_mode_makes_no_network_call():
    c = wp.WordPressClient(_RL(), fake=True)
    with patch.object(wp.requests, "request", side_effect=AssertionError("network in fake mode")):
        landed, res = c.create_post("https://site.com", "u", "p", "t", "body", status="publish")
    assert landed is True and res["_fake"] is True and res["status"] == "publish"
