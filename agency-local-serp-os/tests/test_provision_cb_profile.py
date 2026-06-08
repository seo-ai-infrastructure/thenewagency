import importlib.util, pathlib
import yaml


def _load():
    p = pathlib.Path("scripts/provision_cb_profile.py").resolve()
    spec = importlib.util.spec_from_file_location("provision_cb", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def _template(tmp_path):
    t = pathlib.Path(tmp_path, "clients", "example-hvac-client", "browser", "scripts")
    t.mkdir(parents=True)
    (t.parent/"workflows.yaml").write_text("version: 1\nworkflows: []\n")
    (t.parent/"policy.yaml").write_text("version: 1\nenabled: true\n")
    (t/"tiktok_upload.py").write_text("def run(page, params): return {}\n")
    (t/"youtube_upload.py").write_text("def run(page, params): return {}\n")


def test_provision_registers_cb_agent_and_seeds_config(tmp_path):
    m = _load()
    _template(tmp_path)
    pid, created, _ = m.provision("acme-co", root=tmp_path)
    assert created is True and pid == "acme-co-cb-agent"
    data = yaml.safe_load((tmp_path/"clients/acme-co/browser/profiles.yaml").read_text())
    prof = data["profiles"][0]
    assert prof["profile_id"] == "acme-co-cb-agent"
    assert prof["user_data_dir"] == "~/cloak-profiles/acme-co-cb-agent"
    for wf in ("facebook_post", "reddit_post", "quora_answer_post", "tiktok_upload", "youtube_upload"):
        assert wf in prof["allowed_workflows"]
    # seeded from template
    assert (tmp_path/"clients/acme-co/browser/workflows.yaml").exists()
    assert (tmp_path/"clients/acme-co/browser/scripts/tiktok_upload.py").exists()
    assert (tmp_path/"clients/acme-co/browser/approvals/pending").is_dir()


def test_provision_is_idempotent(tmp_path):
    m = _load()
    _template(tmp_path)
    m.provision("acme-co", root=tmp_path)
    pid, created, _ = m.provision("acme-co", root=tmp_path)
    assert created is False
    data = yaml.safe_load((tmp_path/"clients/acme-co/browser/profiles.yaml").read_text())
    assert len(data["profiles"]) == 1     # not duplicated
