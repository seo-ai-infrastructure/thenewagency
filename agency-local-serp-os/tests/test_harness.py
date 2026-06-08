def test_repo_root_on_path():
    import lib.env  # importable only if repo root is on sys.path
    assert hasattr(lib.env, "load_env")
