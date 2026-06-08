from lib import cadence


def _names(freq, client="c1", dry=False):
    return [n for n, _ in cadence.steps_for(freq, client, dry)]


def test_daily_chain_order():
    names = _names("daily")
    assert names[:3] == ["ingest_signals", "issue_workorders", "publish_gbp_daily"]
    # then it drains every publisher inbox
    assert names[3:] == [f"publish:{p}" for p in cadence.PUBLISHERS]


def test_weekly_generates_review_batch():
    steps = dict(cadence.steps_for("weekly", "c1"))
    assert "gen_gbp_batch" in steps and "--review" in steps["gen_gbp_batch"]
    assert _names("weekly") == ["ingest_signals", "gen_gbp_batch", "issue_workorders"]


def test_monthly_reaudits_and_replans():
    assert _names("monthly") == ["ingest_signals", "serp_estate_audit", "gaps_to_recs", "aeo_recs"]


def test_client_threaded_and_dry_propagates():
    for name, argv in cadence.steps_for("daily", "smiley-drain", dry=True):
        if name.startswith("publish:") or name == "publish_gbp_daily":
            assert "--dry-run" in argv
        if name != "serp_estate_audit":
            assert "smiley-drain" in argv      # client threaded to every client-aware step


def test_unknown_frequency_raises():
    import pytest
    with pytest.raises(ValueError):
        cadence.steps_for("hourly", "c1")


def test_run_cadence_is_graceful_one_failure_does_not_stop_others():
    calls = []
    def execute(name, argv):
        calls.append(name)
        if name == "issue_workorders":
            raise RuntimeError("boom")          # simulate a crashing step
        return (name != "publish_gbp_daily"), "ok"   # and one that returns not-ok
    log = cadence.run_cadence("daily", "c1", execute)
    # every step still ran
    assert [e["step"] for e in log] == _names("daily")
    by = {e["step"]: e["ok"] for e in log}
    assert by["issue_workorders"] is False          # exception -> ok False, not raised
    assert by["publish_gbp_daily"] is False
    assert by["ingest_signals"] is True
    assert by[f"publish:{cadence.PUBLISHERS[0]}"] is True
