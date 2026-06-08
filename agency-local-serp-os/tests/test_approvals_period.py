import json, pathlib
from lib import approvals


def test_approve_finds_period_stamped_review_draft(tmp_path):
    # gen_gbp_posts --review writes scope__workflow__DATE__draft.json; approve(period=DATE) must
    # resolve it (and produce the date-keyed approved artifact post_daily_gbp looks for).
    pend = pathlib.Path(tmp_path, "clients", "c1", "rpa", "approvals", "pending")
    pend.mkdir(parents=True)
    stamped = pend/"loc1__gbp_post_publish__2026-06-07__draft.json"
    stamped.write_text(json.dumps({"content": {"text": "post body"}, "period": "2026-06-07"}))
    out, _ = approvals.approve_draft(str(tmp_path), "c1", "rpa", "loc1", "gbp_post_publish", "2026-06-07")
    assert out.name == "loc1__gbp_post_publish__2026-06-07.json"
    assert json.loads(out.read_text())["content"]["text"] == "post body"
    assert not stamped.exists()                            # the stamped draft was consumed


def test_generic_draft_still_resolves_when_no_stamped_exists(tmp_path):
    pend = pathlib.Path(tmp_path, "clients", "c1", "web", "approvals", "pending")
    pend.mkdir(parents=True)
    (pend/"my-slug__wp_article_publish__draft.json").write_text(json.dumps({"content": {"text": "a"}}))
    out, _ = approvals.approve_draft(str(tmp_path), "c1", "web", "my-slug", "wp_article_publish", "2026-06-09")
    assert out.name == "my-slug__wp_article_publish__2026-06-09.json"
