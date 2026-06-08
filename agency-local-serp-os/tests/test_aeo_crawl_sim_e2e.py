"""End-to-end gate for the AEO crawl simulator automation. Runs the simulator in --dry-run mode
(no network, no API key), validates the history doc against the AEO audit schema, asserts key
semantic properties, and cleans up every artifact it creates so the working tree stays clean."""
import sys, json, glob, subprocess, pathlib
from lib import schema

ROOT = pathlib.Path(__file__).resolve().parents[1]
HIST = ROOT / "automations" / "ai-crawl-simulator" / "history"
SNAP = ROOT / "clients" / "example-hvac-client" / "facts" / "agent_snapshot.md"
RECS = ROOT / "clients" / "example-hvac-client" / "web" / "approvals" / "pending"


def test_aeo_crawl_sim_dry_run():
    # Snapshot what already exists before the run
    before_hist = set(glob.glob(str(HIST / "*.json")))
    snap_existed = SNAP.exists()
    snap_before = SNAP.read_text(encoding="utf-8") if snap_existed else None
    before_recs = set(glob.glob(str(RECS / "rec_*.json")))

    try:
        result = subprocess.run(
            [sys.executable, "automations/ai-crawl-simulator/run.py", "--dry-run"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"run.py exited {result.returncode}\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

        # A new history JSON was written
        after_hist = set(glob.glob(str(HIST / "*.json")))
        new_hist = sorted(after_hist - before_hist)
        assert new_hist, "ai-crawl-simulator wrote no history/*.json file"

        # Load and schema-validate the newest history doc
        doc = json.loads(pathlib.Path(new_hist[-1]).read_text(encoding="utf-8"))
        schema.validate(doc, schema.AEO_AUDIT)

        # Required top-level keys
        assert "run_id" in doc
        assert "generated_at" in doc
        assert doc["client"] == "example-hvac-client"

        # Crawlability: purity < 1.0 because fixtures contain boilerplate lines
        purity = doc["crawlability"]["markdown_purity"]["purity"]
        assert purity < 1.0, f"Expected purity < 1.0 (boilerplate present), got {purity}"

        # Evaluation: hours and guarantee are missing from client fixture
        eval_doc = doc["evaluation"]
        assert eval_doc is not None, "evaluation should not be None"
        missing = eval_doc["missing_entities"]
        assert "hours" in missing, f"Expected 'hours' in missing_entities, got {missing}"

        # Entity conquest must be non-empty (competitor has hours/guarantee the client lacks)
        conquest = eval_doc["entity_conquest"]
        assert conquest, f"entity_conquest should be non-empty, got {conquest}"

        # agent_snapshot.md was written
        assert SNAP.exists(), "clients/example-hvac-client/facts/agent_snapshot.md was not created"

    finally:
        # Remove every artifact the run created that didn't exist before
        for f in set(glob.glob(str(HIST / "*.json"))) - before_hist:
            pathlib.Path(f).unlink(missing_ok=True)
        if snap_existed:
            # Restore original content if snapshot already existed
            if snap_before is not None:
                SNAP.write_text(snap_before, encoding="utf-8")
        else:
            SNAP.unlink(missing_ok=True)
        for f in set(glob.glob(str(RECS / "rec_*.json"))) - before_recs:
            pathlib.Path(f).unlink(missing_ok=True)
        for f in glob.glob(str(RECS / "rec_*.json.tmp")):   # clean any orphaned atomic-write temp files
            pathlib.Path(f).unlink(missing_ok=True)
