"""End-to-end gate: the SERP tracker dry-run produces schema-valid feature records across the
configured lanes. (The serp-estate-scoring automation was redesigned into an SoV-distribution +
work-order generator and no longer writes per-lane estate history; lib.estate_scoring and
lib.serp_saturation remain covered by their own unit tests.) Cleans up the artifacts it creates."""
import sys, json, glob, subprocess, pathlib
from lib import schema

ROOT = pathlib.Path(__file__).resolve().parents[1]
TH = ROOT / "automations" / "local-mobile-serp-feature-tracker" / "history"
CO = ROOT / "automations" / "local-mobile-serp-feature-tracker" / "costs"
LR = ROOT / "automations" / "local-mobile-serp-feature-tracker" / "state" / "last_run.json"


def _jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def test_tracker_dry_validates_each_lane():
    before_t = set(glob.glob(str(TH / "*.jsonl")))
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
        # the three lanes are all represented (local_finder / organic_mobile / ai_mode)
        assert {r["query_class"] for r in snapshot} == {"local_finder", "organic_mobile", "ai_mode"}
    finally:
        for f in set(glob.glob(str(TH / "*.jsonl"))) - before_t:
            pathlib.Path(f).unlink(missing_ok=True)
        for f in set(glob.glob(str(CO / "*.jsonl"))) - before_c:
            pathlib.Path(f).unlink(missing_ok=True)
        if lr_before is not None:
            LR.write_text(lr_before)
        else:
            LR.unlink(missing_ok=True)        # last_run.json didn't exist before -> don't leave it
