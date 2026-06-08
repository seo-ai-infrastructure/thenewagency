"""Unit tests for the Command Center aggregation layer (lib/mission_control).
Read-only: it projects on-disk saturation + signals + config into one dashboard payload.
Hermetic — builds a tmp repo root with minimal fixtures; no network."""
import json
import pytest
from lib import mission_control as mc


def _make_root(tmp_path):
    root = tmp_path
    # one client with a full sources.yaml
    cfg = root / "clients" / "c1" / "config"
    cfg.mkdir(parents=True)
    (cfg / "sources.yaml").write_text(
        "version: 1\n"
        "gsc:\n  site_url: \"https://ex.com/\"\n"
        "ga4:\n  property_id: \"REPLACE_GA4_NUMERIC_ID\"\n"
        "bing:\n  site_url: \"https://ex.com/\"\n"
        "clarity:\n  enabled: true\n"
        "gbp_insights:\n  zernio_account_id: \"acct123\"\n")
    # a daily signals snapshot
    sig = root / "clients" / "c1" / "signals"
    sig.mkdir(parents=True)
    (sig / "2026-06-06.json").write_text(json.dumps({
        "client": "c1", "date": "2026-06-06",
        "search": {"gsc": [], "bing": [
            {"query": "ac repair", "impressions": 10, "clicks": 1,
             "avg_impression_position": 5, "avg_click_position": 3}]},
        "local": {"gbp": {"calls": 4, "website_clicks": 3, "direction_requests": 0,
                          "impressions": 234,
                          "raw": {"CALL_CLICKS": {"total": 4, "values": [
                              {"date": "2026-06-01", "value": 1},
                              {"date": "2026-06-02", "value": 3}]}}}},
        "behavior": {"ga4": [], "clarity": {
            "Traffic": {"totalSessionCount": "9", "totalBotSessionCount": "12"},
            "ScrollDepth": {"averageScrollDepth": 58.2},
            "RageClickCount": {"subTotal": "0"}, "DeadClickCount": {"subTotal": "1"}}},
        "derived": {"gbp_calls": 4, "gbp_website_clicks": 3, "organic_conversions": None,
                    "cro_flags": {"rage_clicks": 0, "dead_clicks": 1}},
    }))
    # tracker history: one below-goal SERP (presence 1) + one meeting-goal SERP (presence 4)
    th = root / "automations" / "local-mobile-serp-feature-tracker" / "history"
    th.mkdir(parents=True)
    recs = [
        {"query_class": "local_finder", "keyword": "ac repair", "location_name": "FTL",
         "os": "ios", "ownership_class": "owned", "feature_type": "local_finder", "lead_value": "high"},
        {"query_class": "local_finder", "keyword": "ac repair", "location_name": "FTL",
         "os": "ios", "ownership_class": "competitor", "feature_type": "organic", "lead_value": "high"},
    ] + [
        {"query_class": "organic_mobile", "keyword": "good kw", "location_name": "FTL",
         "os": "ios", "ownership_class": "owned", "feature_type": ft, "lead_value": "high"}
        for ft in ("organic", "local_pack", "images", "ai_overview")
    ]
    (th / "mobile_serp_20260606T000000Z.jsonl").write_text(
        "\n".join(json.dumps(r) for r in recs))
    st = root / "automations" / "local-mobile-serp-feature-tracker" / "state"
    st.mkdir(parents=True)
    (st / "last_run.json").write_text(json.dumps({
        "run_id": "mobile_serp_20260606T000000Z", "finished_at": "2026-06-06T00:00:00+00:00",
        "n_records": 6, "n_calls": 2, "cost": 0.12, "dry": False}))
    return root


def test_list_clients_finds_configured_clients(tmp_path):
    _make_root(tmp_path)
    (tmp_path / "clients" / "no-config").mkdir(parents=True)   # no sources.yaml -> excluded
    assert mc.list_clients(tmp_path) == ["c1"]


def test_command_center_title_and_client(tmp_path):
    root = _make_root(tmp_path)
    cc = mc.command_center(root, "c1")
    assert cc["title"] == "LEIA Mission Control"
    assert cc["client"] == "c1" and cc["clients"] == ["c1"]


def test_saturation_block_computed_from_tracker_history(tmp_path):
    root = _make_root(tmp_path)
    sat = mc.command_center(root, "c1")["saturation"]
    assert sat["n_serps"] == 2 and sat["goal_min"] == 2
    assert sat["n_meeting_goal"] == 1                      # only the 'good kw' SERP (4 owned)
    assert sat["pct_meeting_goal"] == 0.5
    assert "local_finder" in sat["by_lane"] and "organic_mobile" in sat["by_lane"]
    # the worst SERP surfaces first in the action queue with its unclaimed features
    assert sat["action_queue"][0]["keyword"] == "ac repair"
    assert "organic" in sat["action_queue"][0]["features_unclaimed"]


def test_source_cards_reflect_connection_and_data(tmp_path):
    root = _make_root(tmp_path)
    cards = {c["key"]: c for c in mc.command_center(root, "c1")["source_cards"]}
    assert set(cards) >= {"gbp", "bing", "clarity", "gsc"}
    assert cards["gbp"]["has_data"] is True and cards["gbp"]["headline"]["value"] == 4
    assert cards["clarity"]["has_data"] is True
    # GSC is configured (site_url) but returned no rows -> connected yet no data
    assert cards["gsc"]["connected"] is True and cards["gsc"]["has_data"] is False


def test_action_skyline_includes_serp_and_cro_items(tmp_path):
    root = _make_root(tmp_path)
    sky = mc.command_center(root, "c1")["action_skyline"]
    sources = {item["source"] for item in sky}
    assert "serp" in sources                                # claim-more-features action
    assert "clarity" in sources                             # dead_clicks == 1 -> CRO action


def test_ownership_matrix_powers_heatmap(tmp_path):
    # the keyword x feature ownership grid (heatmap): each cell = best ownership the client
    # holds for that (keyword, feature). Powers the SERP-saturation heatmap visual.
    root = _make_root(tmp_path)
    m = mc.command_center(root, "c1")["ownership_matrix"]
    assert "organic" in m["features"] and "local_finder" in m["features"]
    row = [r for r in m["rows"] if r["keyword"] == "ac repair"][0]
    assert row["cells"]["local_finder"] == "owned"
    assert row["cells"]["organic"] == "competitor"
    assert row["distinct_features_present"] == 1   # distinct features held (named to avoid clash with saturation slot-count)


def test_freshness_reads_signals_date(tmp_path):
    root = _make_root(tmp_path)
    fr = mc.command_center(root, "c1")["freshness"]
    assert fr["signals_date"] == "2026-06-06"
    assert isinstance(fr["stale"], bool)
    assert fr["tracker_run_id"] == "mobile_serp_20260606T000000Z"


def test_cost_block_reads_last_run(tmp_path):
    root = _make_root(tmp_path)
    cost = mc.command_center(root, "c1")["cost"]
    assert cost["last_run_cost"] == 0.12 and isinstance(cost["circuit_open"], bool)


def _root_with_prior(tmp_path):
    """_make_root + an OLDER signals snapshot (fewer calls) and an OLDER, worse tracker run,
    so period-over-period deltas have a baseline to compare against."""
    root = _make_root(tmp_path)
    (root / "clients" / "c1" / "signals" / "2026-06-05.json").write_text(json.dumps({
        "client": "c1", "date": "2026-06-05",
        "search": {"gsc": [], "bing": []},
        "local": {"gbp": {"calls": 2, "website_clicks": 1, "direction_requests": 0,
                          "impressions": 100, "raw": {}}},
        "behavior": {"ga4": [], "clarity": {}},
        "derived": {"cro_flags": {}}}))
    th = root / "automations" / "local-mobile-serp-feature-tracker" / "history"
    (th / "mobile_serp_20260605T000000Z.jsonl").write_text(json.dumps(
        {"query_class": "local_finder", "keyword": "ac repair", "location_name": "FTL",
         "os": "ios", "ownership_class": "competitor", "feature_type": "organic",
         "lead_value": "high"}))     # previous run: 0 SERPs meet goal
    return root


def test_saturation_has_delta_vs_previous_run(tmp_path):
    root = _root_with_prior(tmp_path)
    d = mc.command_center(root, "c1")["saturation"]["delta"]
    assert d["n_meeting_goal"]["abs"] == 1 and d["n_meeting_goal"]["dir"] == "up"


def test_source_card_headline_delta_vs_previous_snapshot(tmp_path):
    root = _root_with_prior(tmp_path)
    cards = {c["key"]: c for c in mc.command_center(root, "c1")["source_cards"]}
    gd = cards["gbp"]["headline"]["delta"]
    assert gd["abs"] == 2 and gd["dir"] == "up"          # calls 4 vs previous 2


def test_delta_is_null_without_prior(tmp_path):
    root = _make_root(tmp_path)                            # a single snapshot / run
    cc = mc.command_center(root, "c1")
    assert cc["saturation"]["delta"] is None
    assert cc["source_cards"][0]["headline"]["delta"] is None


def test_empty_root_is_graceful(tmp_path):
    cc = mc.command_center(tmp_path, None)                  # no clients, no data
    assert cc["saturation"]["n_serps"] == 0
    assert cc["clients"] == [] and cc["client"] is None
    assert cc["source_cards"] == [] and cc["action_skyline"] == []


def test_unknown_or_traversal_client_is_ignored(tmp_path):
    # a crafted/unknown ?client= must not be used to build filesystem paths — fall back to a real client
    root = _make_root(tmp_path)
    cc = mc.command_center(root, "../../etc")
    assert cc["client"] == "c1"


def test_command_center_on_repo_root_smoke():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]      # the real repo, real client data
    cc = mc.command_center(root)
    assert cc["title"] == "LEIA Mission Control"
    for k in ("saturation", "ownership_matrix", "source_cards", "action_skyline",
              "freshness", "cost"):
        assert k in cc
