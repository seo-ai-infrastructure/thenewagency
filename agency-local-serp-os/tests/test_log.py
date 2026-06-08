import json
from lib import log


def test_plain_logger_prints_prefixed(capsys, monkeypatch):
    monkeypatch.delenv("LOG_JSON", raising=False)
    log.get_logger("tlog_plain").info("hello")          # fresh logger name -> fresh handler on capsys stdout
    assert "[tlog_plain] hello" in capsys.readouterr().out


def test_json_logger_emits_object_with_extra(capsys, monkeypatch):
    monkeypatch.setenv("LOG_JSON", "1")
    log.get_logger("tlog_json").info("done", extra={"run_id": "r1", "n": 3})
    d = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert d["msg"] == "done" and d["level"] == "INFO" and d["run_id"] == "r1" and d["n"] == 3
