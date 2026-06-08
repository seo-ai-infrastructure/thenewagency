import json, pathlib
from lib.orchestration import WorkOrderRunner


def _runner(tmp_path):
    here = tmp_path/"auto"
    for d in ("inbox", "working", "done", "failed"):
        (here/d).mkdir(parents=True)
    return WorkOrderRunner(here, tmp_path, tmp_path/"area", {}), here


def test_claim_moves_inbox_to_working(tmp_path):
    R, here = _runner(tmp_path)
    wo = here/"inbox"/"wo_1.json"; wo.write_text(json.dumps({"work_order_id": "wo_1"}))
    dst = R.claim(wo)
    assert dst is not None and dst.exists()
    assert not wo.exists()                                  # inbox copy dropped
    assert (here/"working"/"wo_1.json").exists()


def test_claim_is_exclusive_no_clobber(tmp_path):
    # The whole point: a second worker (or a re-queued same-name file) must NOT overwrite an
    # in-progress work order. os.rename silently replaces on POSIX; os.link refuses on both OSes.
    R, here = _runner(tmp_path)
    wo = here/"inbox"/"wo_2.json"; wo.write_text(json.dumps({"work_order_id": "wo_2"}))   # v1
    assert R.claim(wo) is not None
    again = here/"inbox"/"wo_2.json"; again.write_text(json.dumps({"work_order_id": "wo_2", "v": 2}))
    assert R.claim(again) is None                          # working/wo_2.json exists -> refused
    assert json.loads((here/"working"/"wo_2.json").read_text()).get("v") is None   # original untouched
