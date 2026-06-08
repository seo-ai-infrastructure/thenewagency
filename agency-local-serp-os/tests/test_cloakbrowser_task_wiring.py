import importlib.util
import pathlib

import pytest
import yaml


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_board_server():
    p = ROOT / "apps" / "kanban-board" / "server.py"
    spec = importlib.util.spec_from_file_location("kanban_server", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_example_browser_profile_matches_creator_scope():
    client = "example-hvac-client"
    expected = f"{client}-cb-agent"
    data = yaml.safe_load((ROOT / "clients" / client / "browser" / "profiles.yaml").read_text())
    profile_ids = {p["profile_id"] for p in data["profiles"]}
    assert expected in profile_ids

    schedules = yaml.safe_load((ROOT / "clients" / client / "browser" / "schedules.yaml").read_text())
    scheduled_profiles = {p for s in schedules["schedules"] for p in s.get("profiles", [])}
    assert scheduled_profiles <= profile_ids


def test_comment_tasks_require_target_url():
    server = _load_board_server()
    assert any(t["id"] == "reddit_comment" and t["needs_target"] for t in server.tasks_list())
    with pytest.raises(ValueError, match="target URL is required"):
        server.create_content("example-hvac-client", "reddit_comment", "helpful reply", "", "")
