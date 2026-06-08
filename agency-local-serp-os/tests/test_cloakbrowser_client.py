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
