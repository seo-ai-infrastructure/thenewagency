import json, hashlib, pathlib
from lib import approvals


def _write_draft(tmp_path, client, area, scope, wf, content):
    pend = pathlib.Path(tmp_path, "clients", client, area, "approvals", "pending")
    pend.mkdir(parents=True, exist_ok=True)
    (pend / f"{scope}__{wf}__draft.json").write_text(json.dumps(
        {"content": content, "draft_id": "d1", "provenance": {"area": area}}))


def test_approve_draft_preserves_rich_content(tmp_path):
    content = {"title": "AC Repair Guide", "text": "<p>body</p>", "slug": "ac-repair",
               "status": "publish", "categories": [3], "excerpt": "short"}
    _write_draft(tmp_path, "c1", "web", "ac-repair", "wp_article_publish", content)
    out, h = approvals.approve_draft(str(tmp_path), "c1", "web", "ac-repair",
                                     "wp_article_publish", "2026-06-07")
    art = json.loads(out.read_text())
    for k in ("title", "slug", "status", "categories", "excerpt", "text"):
        assert art["content"][k] == content[k]
    # hash is over the preserved payload (so verify_approval will accept it)
    assert art["content_hash"] == hashlib.sha256(
        json.dumps(art["content"], sort_keys=True).encode()).hexdigest() == h


def test_human_edit_overrides_only_text_keeps_other_fields(tmp_path):
    content = {"title": "T", "text": "orig body", "slug": "s", "status": "publish"}
    _write_draft(tmp_path, "c1", "web", "s", "wp_article_publish", content)
    out, _ = approvals.approve_draft(str(tmp_path), "c1", "web", "s",
                                     "wp_article_publish", "2026-06-07", edit="edited body")
    art = json.loads(out.read_text())
    assert art["content"]["text"] == "edited body"     # edit wins on the body
    assert art["content"]["title"] == "T"              # other rich fields preserved
    assert art["content"]["status"] == "publish"


def test_gbp_text_only_draft_still_works(tmp_path):
    # backward-compat: a GBP-style draft (text + media_url only) approves exactly as before
    content = {"text": "Summer AC tune-up special", "media_url": "https://x/y.jpg"}
    _write_draft(tmp_path, "c1", "rpa", "loc_1", "gbp_post_publish", content)
    out, _ = approvals.approve_draft(str(tmp_path), "c1", "rpa", "loc_1",
                                     "gbp_post_publish", "2026-W23")
    art = json.loads(out.read_text())
    assert art["content"]["text"] == "Summer AC tune-up special"
    assert art["content"]["media_url"] == "https://x/y.jpg"
