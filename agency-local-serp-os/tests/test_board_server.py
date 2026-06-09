"""Tests for the board server's state-changing logic: typed work-order construction per
execution_method, the bounded recovery move, and the CSRF guard. (#19, #20)"""
import importlib.util, json, pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _srv():
    spec = importlib.util.spec_from_file_location("ks", ROOT / "apps" / "kanban-board" / "server.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def _build(srv, wf, target, period="2026-06-20", params=None):
    wid, rel = srv.build_work_order("example-hvac-client", wf, target, period, params or {})
    p = ROOT / rel
    wo = json.loads(p.read_text())
    p.unlink()          # clean the inbox file we just created
    return wo


# ---- build_work_order: one per execution_method ----

def test_build_gbp_api_work_order():
    wo = _build(_srv(), "gbp_post_publish", "14079618992035666030")
    assert wo["execution_method"] == "google_business_api"
    assert wo["profile_id"] == "14079618992035666030" and wo["location_id"] == "14079618992035666030"
    assert wo["account_id"]
    assert wo["approval_ref"].endswith("14079618992035666030__gbp_post_publish__2026-06-20.json")


def test_build_wordpress_work_order():
    wo = _build(_srv(), "wp_article_publish", "my-slug")
    assert wo["execution_method"] == "wordpress_api" and wo["profile_id"] == "my-slug"
    assert "web/approvals/approved/my-slug__wp_article_publish__2026-06-20.json" in wo["approval_ref"].replace("\\", "/")


def test_build_cloakbrowser_work_order():
    wo = _build(_srv(), "facebook_post", "example-hvac-client-cb-agent")
    assert wo["execution_method"] == "cloakbrowser"
    assert wo["profile_id"] == "example-hvac-client-cb-agent"


def test_build_duoplus_work_order_resolves_phone():
    wo = _build(_srv(), "approved_content_post", "profile_001")
    assert wo["execution_method"] == "duoplus_rpa" and wo["profile_id"] == "profile_001"
    assert wo["phone_id"] == "duoplus_phone_001"     # resolved from profiles.yaml


def test_build_rejects_unknown_workflow():
    with pytest.raises(ValueError):
        _srv().build_work_order("example-hvac-client", "no_such_workflow", "x", "2026-06-20", {})


# ---- move_wo: bounds + log append ----

def test_move_wo_rejects_bad_inputs():
    srv = _srv()
    with pytest.raises(ValueError): srv.move_wo("zernio-publisher", "wo_x.json", "nowhere")   # bad column
    with pytest.raises(ValueError): srv.move_wo("not-an-automation", "wo_x.json", "done")      # unknown automation
    with pytest.raises(ValueError): srv.move_wo("zernio-publisher", "../../etc/passwd", "done")  # traversal
    with pytest.raises(ValueError): srv.move_wo("zernio-publisher", "wo_x.txt", "done")          # not .json


def test_move_wo_moves_and_logs():
    srv = _srv()
    sub = ROOT / "automations" / "zernio-publisher"
    src = sub / "inbox" / "wo_movetest.json"; src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(json.dumps({"work_order_id": "wo_movetest"}))
    hist = sub / "history" / "runs.jsonl"; hist_before = hist.read_text() if hist.exists() else None
    try:
        rel = srv.move_wo("zernio-publisher", "wo_movetest.json", "working")
        assert (sub / "working" / "wo_movetest.json").exists() and not src.exists()
        last = json.loads(hist.read_text().strip().splitlines()[-1])
        assert last["work_order_id"] == "wo_movetest" and last["status"] == "working"
        assert "manual_override" in last["reason"]
    finally:
        (sub / "working" / "wo_movetest.json").unlink(missing_ok=True)
        src.unlink(missing_ok=True)
        if hist_before is not None: hist.write_text(hist_before)
        else: hist.unlink(missing_ok=True)


# ---- CSRF guard (#19) ----

def test_csrf_guard_blocks_cross_site():
    srv = _srv()
    f = type("F", (), {})()
    f.headers = {"Sec-Fetch-Site": "cross-site"};          assert srv.Handler._csrf_ok(f) is False
    f.headers = {"Origin": "http://evil.example"};          assert srv.Handler._csrf_ok(f) is False
    f.headers = {"Sec-Fetch-Site": "same-origin"};          assert srv.Handler._csrf_ok(f) is True
    f.headers = {"Origin": "http://127.0.0.1:8787"};        assert srv.Handler._csrf_ok(f) is True
    f.headers = {};                                          assert srv.Handler._csrf_ok(f) is True  # curl/no browser


def test_reorder_inbox_writes_sequential_order_index():
    srv = _srv()
    inbox = ROOT / "automations" / "zernio-publisher" / "inbox"; inbox.mkdir(parents=True, exist_ok=True)
    f1 = inbox / "wo_ro_1.json"; f1.write_text(json.dumps({"work_order_id": "wo_ro_1", "order_index": 9}))
    f2 = inbox / "wo_ro_2.json"; f2.write_text(json.dumps({"work_order_id": "wo_ro_2", "order_index": 9}))
    try:
        n = srv.reorder_inbox("zernio-publisher", ["wo_ro_2.json", "wo_ro_1.json"])
        assert n == 2
        assert json.loads(f2.read_text())["order_index"] == 0
        assert json.loads(f1.read_text())["order_index"] == 1
    finally:
        f1.unlink(missing_ok=True); f2.unlink(missing_ok=True)


def test_reorder_inbox_rejects_bad_inputs():
    srv = _srv()
    with pytest.raises(ValueError): srv.reorder_inbox("not-an-automation", ["wo_x.json"])
    with pytest.raises(ValueError): srv.reorder_inbox("zernio-publisher", ["../evil.json"])
    with pytest.raises(ValueError): srv.reorder_inbox("zernio-publisher", ["wo_x.txt"])


def test_reorder_inbox_rejects_before_any_write():
    srv = _srv()
    inbox = ROOT / "automations" / "zernio-publisher" / "inbox"; inbox.mkdir(parents=True, exist_ok=True)
    f1 = inbox / "wo_ro_partial.json"
    f1.write_text(json.dumps({"work_order_id": "wo_ro_partial", "order_index": 9}))
    try:
        with pytest.raises(ValueError):
            srv.reorder_inbox("zernio-publisher", ["wo_ro_partial.json", "../evil.json"])
        assert json.loads(f1.read_text())["order_index"] == 9
    finally:
        f1.unlink(missing_ok=True)
