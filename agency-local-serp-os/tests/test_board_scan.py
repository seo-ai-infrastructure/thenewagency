"""board_scan projects the filesystem into board columns — a wrong glob silently shows the wrong
state. Fixture-driven: build a temp tree of inboxes + approvals, assert the column counts. (#21)"""
import json, pathlib
from lib import board_scan


def _wo(path, wid):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"work_order_id": wid, "execution_method": "google_business_api",
                                "client_id": "c1", "profile_id": "loc", "workflow_id": "gbp_post_publish"}))


def test_columns_project_from_tree(tmp_path):
    z = tmp_path / "automations" / "zernio-publisher"
    _wo(z / "inbox" / "wo_q.json", "wo_q")
    _wo(z / "working" / "wo_p.json", "wo_p")
    _wo(z / "done" / "wo_d.json", "wo_d")
    _wo(z / "failed" / "wo_f.json", "wo_f")
    pend = tmp_path / "clients" / "c1" / "rpa" / "approvals" / "pending"; pend.mkdir(parents=True)
    (pend / "loc__gbp_post_publish__draft.json").write_text(json.dumps(
        {"scope_id": "loc", "workflow_id": "gbp_post_publish", "kind": "gbp_post", "content": {"text": "hi"}}))
    appr = tmp_path / "clients" / "c1" / "rpa" / "approvals" / "approved"; appr.mkdir(parents=True)
    (appr / "loc__gbp_post_publish__2026-06-20.json").write_text(json.dumps(
        {"workflow_id": "gbp_post_publish", "profile_id": "loc", "period": "2026-06-20",
         "expires_at": "2099-01-01T00:00:00+00:00"}))

    by = board_scan.grouped(str(tmp_path))
    cols = {k: len(v) for k, v in by.items()}
    assert cols["progress"] == 1                 # working/
    assert cols["done"] == 1                      # done/
    assert cols["held"] == 1                       # failed/
    assert cols["approval"] == 1                   # the pending draft
    assert cols["queued"] == 2                     # inbox wo + the approved artifact


def test_empty_tree_has_no_cards(tmp_path):
    by = board_scan.grouped(str(tmp_path))
    assert all(len(v) == 0 for v in by.values())


def test_content_calendar_reads_dated_drafts(tmp_path):
    # a web-area pending draft with a date period shows on the generalized calendar
    pend = tmp_path / "clients" / "c1" / "web" / "approvals" / "pending"; pend.mkdir(parents=True)
    (pend / "slug__wp_article_publish__draft.json").write_text(json.dumps(
        {"scope_id": "slug", "workflow_id": "wp_article_publish", "kind": "wp_article",
         "period": "2026-06-20", "content": {"title": "T", "text": "body"}}))
    cal = board_scan.content_calendar(str(tmp_path))
    assert any(e["date"] == "2026-06-20" and e["client"] == "c1" for e in cal)
