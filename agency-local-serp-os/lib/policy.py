"""Policy enforcement — checked in CODE before any action, fail-closed.
Reads the client's policy.yaml (kill switch, blocked/allowed action classes)."""
import yaml, pathlib

def load(client_rpa_dir):
    return yaml.safe_load((pathlib.Path(client_rpa_dir) / "policy.yaml").read_text())

def kill_switch_active(pol):
    return pol.get("enabled", True) is False         # enabled:false == global stop

def check(workflow, profile, pol):
    """Returns (ok, reason). Fail-closed: anything unclear is denied."""
    if kill_switch_active(pol):
        return False, "global kill switch active (policy.enabled=false)"
    if profile and profile.get("paused"):
        return False, f"profile {profile.get('profile_id')} paused"
    ac = workflow.get("action_class")
    if not ac:                                        # fail closed: no class = deny
        return False, f"workflow {workflow.get('workflow_id')} has no action_class"
    if ac in pol.get("blocked_action_classes", []):
        return False, f"action_class '{ac}' is BLOCKED by policy"
    allowed = pol.get("allowed_action_classes")
    if allowed and ac not in allowed:
        return False, f"action_class '{ac}' not in allowed_action_classes"
    if workflow["workflow_id"] not in (profile or {}).get("allowed_workflows", []) and profile is not None:
        return False, f"workflow not permitted for {profile.get('profile_id')}"
    return True, "ok"
