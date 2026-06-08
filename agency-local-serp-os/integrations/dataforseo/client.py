"""DataForSEO client. Live + raw-response archiving, lane-aware item extraction, cost metering,
retry-with-backoff on transient failures, and a cooldown circuit breaker so a bad key can't burn
a burst of paid requests. Live HTTP needs DATAFORSEO_* in env; dry-run uses fixtures."""
import os, json, time, base64, pathlib

_STATE = pathlib.Path(__file__).resolve().parent / "state"
_CIRCUIT = _STATE / "circuit.json"
_AUTH_FAIL = (401, 403)
COOLDOWN_SEC = int(os.environ.get("DATAFORSEO_COOLDOWN_SEC", "300"))
MAX_TRIES = int(os.environ.get("DATAFORSEO_TRIES", "3"))


def _auth_header():
    cred = base64.b64encode(f"{os.environ['DATAFORSEO_LOGIN']}:{os.environ['DATAFORSEO_PASSWORD']}".encode()).decode()
    return {"Authorization": f"Basic {cred}", "Content-Type": "application/json"}


# ---- retry-with-backoff (#12) ----
def _should_retry(status):
    return status == 429 or 500 <= status < 600     # rate-limit / server errors are transient


def _retry_after(resp):
    try:
        return float(resp.headers.get("Retry-After", "") or 0) or None
    except (ValueError, TypeError, AttributeError):
        return None


def _post_with_retry(endpoint, headers, body, tries=MAX_TRIES, sleep=time.sleep, post=None):
    """Retry transient 429/5xx (honoring Retry-After, else exponential backoff). A non-retryable
    status, or the last attempt, raises via raise_for_status(). `post`/`sleep` injected for tests."""
    if post is None:
        import requests
        post = lambda e, h, b: requests.post(e, headers=h, json=b, timeout=180)
    resp = None
    for attempt in range(tries):
        resp = post(endpoint, headers, body)
        if resp.status_code < 400:
            return resp
        if not _should_retry(resp.status_code) or attempt == tries - 1:
            resp.raise_for_status()
            return resp
        sleep(_retry_after(resp) or (2 ** attempt))
    return resp


# ---- cooldown circuit breaker (#12) ----
def circuit_open(now=None):
    if not _CIRCUIT.exists():
        return False
    try:
        until = json.loads(_CIRCUIT.read_text()).get("open_until", 0)
    except Exception:
        return False
    return (now if now is not None else time.time()) < until


def trip_circuit(now=None):
    _STATE.mkdir(parents=True, exist_ok=True)
    _CIRCUIT.write_text(json.dumps({"open_until": (now if now is not None else time.time()) + COOLDOWN_SEC}))


def reset_circuit():
    _CIRCUIT.unlink(missing_ok=True)


def call(endpoint, task, raw_dir=None, tag=None):
    """Live call. Returns (items, meta). Retries transient failures; an auth failure (401/403)
    trips a cooldown circuit. Archives the raw JSON if raw_dir given."""
    import requests
    if circuit_open():
        raise RuntimeError("dataforseo circuit open — cooling down after a recent auth failure")
    try:
        r = _post_with_retry(endpoint, _auth_header(), [task])
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in _AUTH_FAIL:
            trip_circuit()
        raise
    payload = r.json()
    if raw_dir:
        p = pathlib.Path(raw_dir); p.mkdir(parents=True, exist_ok=True)
        (p / f"{tag or 'raw'}.json").write_text(json.dumps(payload))
    return extract_items(payload), extract_meta(payload)


def extract_items(payload):
    """Flat items list. AI Mode & AIO both arrive as an 'ai_overview' item; the lane (parse_as)
    is what disambiguates them downstream, not this function."""
    task = (payload.get("tasks") or [{}])[0]
    result = (task.get("result") or [])
    if not result:                     # AI Mode unavailable for this market -> empty (FIX #2)
        return []
    return result[0].get("items") or []


def extract_meta(payload):
    """Cost + error fields from a DataForSEO response (AI Mode ~2x; meter it). Tolerant of fixtures
    that omit them -> None / 0."""
    task = (payload.get("tasks") or [{}])[0]
    return {"cost": payload.get("cost"),
            "task_cost": task.get("cost"),
            "status_code": payload.get("status_code"),
            "tasks_error": payload.get("tasks_error", 0)}
