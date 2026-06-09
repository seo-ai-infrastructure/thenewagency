from unittest.mock import MagicMock, patch

from integrations.cloakbrowser.client import CloakBrowserClient


class NoopLimiter:
    def acquire(self):
        return None


def test_agent_task_landing_policy_requires_success_for_public_actions():
    assert CloakBrowserClient._landed_from_success(None, require_success=False) is True
    assert CloakBrowserClient._landed_from_success(False, require_success=False) is False
    assert CloakBrowserClient._landed_from_success(None, require_success=True) is False
    assert CloakBrowserClient._landed_from_success(True, require_success=True) is True


def test_fake_agent_task_reports_success_for_dry_runs():
    client = CloakBrowserClient(NoopLimiter(), fake=True)
    landed, report = client.run_agent_task({"fake": True}, "do the thing", {}, require_success=True)
    assert landed is True
    assert report["success"] is True


def test_cb_manager_launch_attaches_to_mapped_persistent_profile(monkeypatch):
    monkeypatch.setenv("CLOAKBROWSER_EXECUTION_MODE", "cb_manager")
    monkeypatch.setenv("CB_CREW_API_BASE", "http://cb-api.test")
    client = CloakBrowserClient(NoopLimiter())
    post_resp = MagicMock(status_code=200, text="ok")
    cdp_resp = MagicMock(status_code=200)
    cdp_resp.json.return_value = {"websocketUrl": "ws://127.0.0.1/devtools/browser/abc"}
    with patch("integrations.cloakbrowser.client.requests.post", return_value=post_resp) as post, \
         patch("integrations.cloakbrowser.client.requests.get", return_value=cdp_resp) as get, \
         patch.object(client, "_connect_cdp", return_value={"context": object(), "page": object()}):
        ctx = client.launch({"profile_id": "example-hvac-client-cb-agent", "cb_profile_id": "cb-123"})
    assert ctx["managed_by_cb"] is True
    assert ctx["cb_profile_id"] == "cb-123"
    post.assert_called_once_with("http://cb-api.test/api/profiles/cb-123/launch", timeout=30)
    get.assert_called_once_with("http://cb-api.test/api/profiles/cb-123/cdp", timeout=30)


def test_cb_manager_launch_fails_without_live_cdp(monkeypatch):
    monkeypatch.setenv("CLOAKBROWSER_EXECUTION_MODE", "cb_manager")
    client = CloakBrowserClient(NoopLimiter())
    post_resp = MagicMock(status_code=200, text="ok")
    cdp_resp = MagicMock(status_code=200)
    cdp_resp.json.return_value = {}
    with patch("integrations.cloakbrowser.client.requests.post", return_value=post_resp), \
         patch("integrations.cloakbrowser.client.requests.get", return_value=cdp_resp):
        try:
            client.launch({"profile_id": "example-hvac-client-cb-agent", "cb_profile_id": "cb-123"})
        except RuntimeError as exc:
            assert "no live CDP websocket" in str(exc)
        else:
            raise AssertionError("expected no-CDP launch to fail closed")


def test_cb_manager_close_disconnects_without_closing_profile():
    client = CloakBrowserClient(NoopLimiter())
    browser = MagicMock()
    playwright = MagicMock()
    client.close({"managed_by_cb": True, "browser": browser, "playwright": playwright})
    browser.disconnect.assert_called_once()
    browser.close.assert_not_called()
    playwright.stop.assert_called_once()
