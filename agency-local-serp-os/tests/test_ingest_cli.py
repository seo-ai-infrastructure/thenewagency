import pathlib


def test_cli_delegates_to_runner():
    src = pathlib.Path("scripts/ingest_signals.py").read_text()
    assert "search-signals-ingest" in src and "run.py" in src
