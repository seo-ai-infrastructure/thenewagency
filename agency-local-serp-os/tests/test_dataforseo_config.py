import pathlib
import yaml, pytest, jsonschema
from lib import schema
from integrations.dataforseo import client as dfs

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_endpoints_yaml_validates_against_schema():           # FIX #7
    doc = yaml.safe_load((ROOT / "integrations/dataforseo/endpoints.yaml").read_text())
    schema.validate(doc, schema.ENDPOINTS)                    # raises if the config drifted
    assert doc["apis"] and all("endpoint" in a and "parse_as" in a for a in doc["apis"].values())


def test_endpoints_schema_rejects_renamed_key():
    bad = {"apis": {"x": {"endpoint": "https://x", "keyword_source": "k",
                          "cadence": "weekly", "params": {}}}}   # parse_as renamed away
    with pytest.raises(jsonschema.ValidationError):
        schema.validate(bad, schema.ENDPOINTS)


def test_extract_meta_captures_cost_and_errors():             # FIX #8
    payload = {"cost": 0.02, "status_code": 20000, "tasks_error": 0,
               "tasks": [{"cost": 0.02, "result": [{"items": []}]}]}
    m = dfs.extract_meta(payload)
    assert m["cost"] == 0.02 and m["task_cost"] == 0.02 and m["tasks_error"] == 0


def test_extract_meta_tolerates_fixtures_without_cost():
    m = dfs.extract_meta({"tasks": [{}]})
    assert m["cost"] is None and m["task_cost"] is None and m["tasks_error"] == 0


# ---- retries + circuit breaker (#12) ----
import time
import requests


class _Resp:
    def __init__(self, status, headers=None):
        self.status_code = status; self.headers = headers or {}; self.response = self
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code), response=self)


def test_should_retry_only_transient():
    assert dfs._should_retry(429) and dfs._should_retry(500) and dfs._should_retry(503)
    assert not dfs._should_retry(200) and not dfs._should_retry(403)


def test_post_retries_transient_then_succeeds():
    seq, n = [_Resp(429), _Resp(200)], []
    r = dfs._post_with_retry("u", {}, [], tries=3, sleep=lambda *_: None,
                             post=lambda e, h, b: (n.append(1), seq.pop(0))[1])
    assert r.status_code == 200 and len(n) == 2


def test_post_raises_non_retryable_without_retrying():
    n = []
    with pytest.raises(requests.HTTPError):
        dfs._post_with_retry("u", {}, [], tries=3, sleep=lambda *_: None,
                             post=lambda e, h, b: (n.append(1), _Resp(403))[1])
    assert len(n) == 1


def test_post_honors_retry_after():
    waits, seq = [], [_Resp(429, {"Retry-After": "7"}), _Resp(200)]
    dfs._post_with_retry("u", {}, [], tries=3, sleep=lambda s: waits.append(s),
                         post=lambda e, h, b: seq.pop(0))
    assert waits == [7.0]


def test_circuit_trips_and_cools_down(tmp_path, monkeypatch):
    monkeypatch.setattr(dfs, "_STATE", tmp_path)
    monkeypatch.setattr(dfs, "_CIRCUIT", tmp_path / "circuit.json")
    assert dfs.circuit_open() is False
    dfs.trip_circuit()
    assert dfs.circuit_open() is True
    assert dfs.circuit_open(now=time.time() + dfs.COOLDOWN_SEC + 1) is False
