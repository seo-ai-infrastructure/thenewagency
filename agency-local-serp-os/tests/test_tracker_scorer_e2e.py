"""End-to-end gate: the 'run_all_dry.py works' check as a test. Runs the tracker (--dry) and the
scorer on fixtures, validates every record against its schema, and asserts one score per lane.
Cleans up the history/state artifacts it creates so the working tree stays clean."""
import sys, json, glob, subprocess, pathlib
from lib import schema

ROOT = pathlib.Path(__file__).resolve().parents[1]
TH = ROOT / "automations" / "local-mobile-serp-feature-tracker" / "history"
SH = ROOT / "automations" / "serp-estate-scoring" / "history"
CO = ROOT / "automations" / "local-mobile-serp-feature-tracker" / "costs"
LR = ROOT / "automations" / "local-mobile-serp-feature-tracker" / "state" / "last_run.json"


def _jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def test_tracker_then_scorer_dry_validates_and_scores_each_lane():
    before_t = set(glob.glob(str(TH / "*.jsonl")))
    before_s = set(glob.glob(str(SH / "*.jsonl")))
    before_sat = set(glob.glob(str(SH / "*.saturation.json")))
    before_c = set(glob.glob(str(CO / "*.jsonl")))
    lr_before = LR.read_text() if LR.exists() else None
    try:
        rt = subprocess.run([sys.executable, "automations/local-mobile-serp-feature-tracker/run.py", "--dry-run"],
                            cwd=str(ROOT), capture_output=True, text=True)
        assert rt.returncode == 0, rt.stderr
        new_t = sorted(set(glob.glob(str(TH / "*.jsonl"))) - before_t)
        assert new_t, "tracker wrote no history"
        snapshot = _jsonl(new_t[-1])
        assert snapshot
        for rec in snapshot:
            schema.validate(rec, schema.SNAPSHOT)        # every record matches the v3 schema
        snapshot_lanes = {r["query_class"] for r in snapshot}

        rs = subprocess.run([sys.executable, "automations/serp-estate-scoring/run.py"],
                            cwd=str(ROOT), capture_output=True, text=True)
        assert rs.returncode == 0, rs.stderr
        new_s = sorted(set(glob.glob(str(SH / "*.jsonl"))) - before_s)
        assert new_s, "scorer wrote no history"
        scores = _jsonl(new_s[-1])
        for s in scores:
            schema.validate(s, schema.ESTATE)            # every score matches estate_score v1
        # exactly one score record per query_class present in the snapshot (lanes never blended)
        assert {s["query_class"] for s in scores} == snapshot_lanes
        assert len(scores) == len(snapshot_lanes)

        # the scorer also tracks SERP saturation (multi-presence toward the 4-6+ goal)
        new_sat = sorted(set(glob.glob(str(SH / "*.saturation.json"))) - before_sat)
        assert new_sat, "scorer wrote no saturation tracking"
        sat = json.loads(open(new_sat[-1], encoding="utf-8").read())
        schema.validate(sat, schema.SATURATION)          # matches serp_saturation v1
        assert sat["n_serps"] > 0 and sat["goal_min"] == 4
        assert len(sat["serps"]) == sat["n_serps"]
    finally:
        for f in set(glob.glob(str(SH / "*.saturation.json"))) - before_sat:
            pathlib.Path(f).unlink(missing_ok=True)
        for f in set(glob.glob(str(TH / "*.jsonl"))) - before_t:
            pathlib.Path(f).unlink(missing_ok=True)
        for f in set(glob.glob(str(SH / "*.jsonl"))) - before_s:
            pathlib.Path(f).unlink(missing_ok=True)
        for f in set(glob.glob(str(CO / "*.jsonl"))) - before_c:
            pathlib.Path(f).unlink(missing_ok=True)
        if lr_before is not None:
            LR.write_text(lr_before)
        else:
            LR.unlink(missing_ok=True)        # last_run.json didn't exist before -> don't leave it
