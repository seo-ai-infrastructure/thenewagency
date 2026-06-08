import json, pathlib
from unittest.mock import patch
import importlib.util


def _load_runner():
    p = pathlib.Path("automations/search-signals-ingest/run.py").resolve()
    spec = importlib.util.spec_from_file_location("ingest_run", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_runner_writes_snapshot_with_available_sources(tmp_path):
    run = _load_runner()
    sources = {"bing": {"site_url": "https://x/"}, "clarity": {"enabled": True}}
    with patch.object(run, "bing_query_stats", return_value=[{"query": "q", "impressions": 1, "clicks": 0,
                       "avg_impression_position": 1, "avg_click_position": 1}]), \
         patch.object(run, "clarity_live_insights", return_value={"RageClickCount": {"subTotal": "3"}}):
        snap = run.ingest("example-hvac-client", "2026-06-06", sources, root=str(tmp_path))
    assert snap["search"]["bing"][0]["query"] == "q"
    assert snap["derived"]["cro_flags"]["rage_clicks"] == 3
    written = tmp_path / "clients" / "example-hvac-client" / "signals" / "2026-06-06.json"
    assert json.loads(written.read_text())["client"] == "example-hvac-client"
