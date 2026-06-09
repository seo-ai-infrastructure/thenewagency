# Kanban Board & Manual Order Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add drag-and-drop, a rich order-editor modal, and a per-persona "Fractional Employees" swimlane board to `apps/kanban-board/`, without breaking the filesystem-as-SSOT model or the signed-approval gate.

**Architecture:** Backend stays the stdlib-only localhost HTTP server (`server.py`) projecting the filesystem via `lib/board_scan.py`. New file-touching endpoints reuse the existing `move_wo` safety guards (localhost, CSRF, basename-only `.json`). Frontend splits the monolithic `static/app.js` into focused modules and adds Sortable.js (vendored, no build step) for drag.

**Tech Stack:** Python 3 stdlib (`http.server`), PyYAML, pytest; vanilla JS + Sortable.js; plain `<script>` tags (no bundler).

**Spec:** `docs/superpowers/specs/2026-06-09-kanban-order-upgrade-design.md`

---

## File Structure

**Backend (modify):**
- `apps/kanban-board/server.py` — add `_safe_wo_path`, `reorder_inbox`, `wo_detail`, `save_wo`, `attach_link`, `fractional_board`; add GET/POST routes; add Sortable + new-JS file routes.
- `lib/board_scan.py` — add `profile_id` to `wo` cards; sort `queued` by `order_index`.

**Backend (test):**
- `tests/test_board_server.py` — extend with reorder / wo_detail / save / attach / fractional tests.

**Frontend (create):**
- `apps/kanban-board/static/vendor/sortable/Sortable.min.js` — vendored lib.
- `apps/kanban-board/static/board-common.js` — shared helpers (`apiCall`, `esc`, `SYS`, `initials`, `cardHTML`, `COL_FOLDER`).
- `apps/kanban-board/static/board.js` — main board render + drag.
- `apps/kanban-board/static/order-modal.js` — rich order-editor modal.
- `apps/kanban-board/static/fractional.js` — swimlane board render + drag.

**Frontend (modify):**
- `apps/kanban-board/static/app.js` — reduce to view-switch shell.
- `apps/kanban-board/static/index.html` — script tags, nav tab, modal markup, fractional view container.
- `apps/kanban-board/static/styles.css` — card chips, drag styles, modal, swimlanes.

**Conventions:** run pytest from repo root. Commit after every green task.

---

## Task 1: Board scan — `profile_id` on cards + `order_index` sort

**Files:**
- Modify: `lib/board_scan.py`
- Test: `tests/test_board_scan.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_board_scan.py` (create the file with this import block if it does not already import these):

```python
import json, pathlib
from lib import board_scan

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_wo_card_has_profile_id_and_queued_sorts_by_order_index(tmp_path):
    sub = ROOT / "automations" / "zernio-publisher" / "inbox"
    sub.mkdir(parents=True, exist_ok=True)
    a = sub / "wo_scan_b.json"; a.write_text(json.dumps(
        {"work_order_id": "wo_scan_b", "workflow_id": "wf", "profile_id": "p1", "order_index": 5}))
    b = sub / "wo_scan_a.json"; b.write_text(json.dumps(
        {"work_order_id": "wo_scan_a", "workflow_id": "wf", "profile_id": "p2", "order_index": 1}))
    try:
        by = board_scan.grouped(ROOT)
        ours = [c for c in by["queued"] if c.get("wo_id", "").startswith("wo_scan_")]
        assert all("profile_id" in c for c in ours)
        # order_index 1 (wo_scan_a) must come before order_index 5 (wo_scan_b)
        idx = [c["wo_id"] for c in ours]
        assert idx.index("wo_scan_a") < idx.index("wo_scan_b")
    finally:
        a.unlink(missing_ok=True); b.unlink(missing_ok=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_board_scan.py::test_wo_card_has_profile_id_and_queued_sorts_by_order_index -v`
Expected: FAIL — `KeyError: 'profile_id'` or ordering assertion fails.

- [ ] **Step 3: Implement**

In `lib/board_scan.py`, inside `collect()`, the `wo` card dict (currently ending at `"manual": wo.get("manual", False)}`) — add two keys:

```python
                cards.append({"col": col, "system": system,
                    "client": wo.get("client_id") or DEFAULT_CLIENT.get(system, ""),
                    "title": wo.get("workflow_id", "?"), "sub": sub_t, "period": wo.get("period", ""),
                    "age": age(p.stat().st_mtime), "reason": reason, "preview": "",
                    "kind": "wo", "automation": dirname, "filename": p.name,
                    "wo_id": wo.get("work_order_id", ""), "manual": wo.get("manual", False),
                    "profile_id": wo.get("profile_id", ""),
                    "order_index": wo.get("order_index", 0)})
```

In `grouped()`, after the `by["approval"].sort(...)` line, add a stable sort of the queued column by `order_index`:

```python
    by["approval"].sort(key=lambda x: x.get("_ts", 0))
    by["queued"].sort(key=lambda x: x.get("order_index", 0))
    return by
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_board_scan.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/board_scan.py tests/test_board_scan.py
git commit -m "feat(board): expose profile_id on cards and sort QUEUED by order_index"
```

---

## Task 2: `reorder_inbox` + `_safe_wo_path` helper

**Files:**
- Modify: `apps/kanban-board/server.py`
- Test: `tests/test_board_server.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_board_server.py`:

```python
def test_reorder_inbox_writes_sequential_order_index():
    srv = _srv()
    inbox = ROOT / "automations" / "zernio-publisher" / "inbox"; inbox.mkdir(parents=True, exist_ok=True)
    f1 = inbox / "wo_ro_1.json"; f1.write_text(json.dumps({"work_order_id": "wo_ro_1", "order_index": 9}))
    f2 = inbox / "wo_ro_2.json"; f2.write_text(json.dumps({"work_order_id": "wo_ro_2", "order_index": 9}))
    try:
        n = srv.reorder_inbox("zernio-publisher", ["wo_ro_2.json", "wo_ro_1.json"])
        assert n == 2
        assert json.loads(f2.read_text())["order_index"] == 0
        assert json.loads(f1.read_text())["order_index"] == 1
    finally:
        f1.unlink(missing_ok=True); f2.unlink(missing_ok=True)


def test_reorder_inbox_rejects_bad_inputs():
    srv = _srv()
    with pytest.raises(ValueError): srv.reorder_inbox("not-an-automation", ["wo_x.json"])
    with pytest.raises(ValueError): srv.reorder_inbox("zernio-publisher", ["../evil.json"])
    with pytest.raises(ValueError): srv.reorder_inbox("zernio-publisher", ["wo_x.txt"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_board_server.py::test_reorder_inbox_writes_sequential_order_index -v`
Expected: FAIL — `AttributeError: module 'ks' has no attribute 'reorder_inbox'`.

- [ ] **Step 3: Implement**

In `apps/kanban-board/server.py`, after the `move_wo` function (around line 200), add:

```python
COL_FOLDER = {"queued": "inbox", "progress": "working", "done": "done", "held": "failed"}

def _safe_wo_path(automation, filename):
    """Resolve a WO file by basename across the four state folders. Traversal-proof."""
    if automation not in INBOX_DIR.values():
        raise ValueError("unknown automation")
    if filename != pathlib.Path(filename).name or not filename.endswith(".json"):
        raise ValueError("bad filename")
    sub = ROOT/"automations"/automation
    for folder in ("inbox", "working", "done", "failed"):
        cand = sub/folder/filename
        if cand.exists():
            return sub, folder, cand
    raise FileNotFoundError(filename)

def reorder_inbox(automation, order):
    """Rewrite order_index 0..N on the named inbox WOs (advisory triage order)."""
    if automation not in INBOX_DIR.values():
        raise ValueError("unknown automation")
    inbox = ROOT/"automations"/automation/"inbox"
    written = 0
    for i, filename in enumerate(order):
        if filename != pathlib.Path(filename).name or not filename.endswith(".json"):
            raise ValueError("bad filename")
        p = inbox/filename
        if not p.exists():
            continue
        wo = json.loads(p.read_text()); wo["order_index"] = i
        tmp = p.with_suffix(".json.tmp"); tmp.write_text(json.dumps(wo, indent=2)); tmp.replace(p)
        written += 1
    return written
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_board_server.py -k reorder -v`
Expected: PASS (both reorder tests).

- [ ] **Step 5: Commit**

```bash
git add apps/kanban-board/server.py tests/test_board_server.py
git commit -m "feat(board): add reorder_inbox + _safe_wo_path helper"
```

---

## Task 3: `wo_detail` — WO + history + logs + attachments

**Files:**
- Modify: `apps/kanban-board/server.py`
- Test: `tests/test_board_server.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_board_server.py`:

```python
def test_wo_detail_assembles_history_and_logs():
    srv = _srv()
    sub = ROOT / "automations" / "zernio-publisher"
    f = sub / "inbox" / "wo_det_1.json"; f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"work_order_id": "wo_det_1", "execution_method": "google_business_api",
                             "client_id": "c", "workflow_id": "wf",
                             "attachments": [{"label": "brief", "url": "https://x/y"}]}))
    hist = sub / "history" / "runs.jsonl"; hist_before = hist.read_text() if hist.exists() else None
    hist.parent.mkdir(parents=True, exist_ok=True)
    with hist.open("a") as h:
        h.write(json.dumps({"work_order_id": "wo_det_1", "ts": "2026-06-09T00:00:00+00:00",
                            "status": "done", "task_report": {"ok": True}}) + "\n")
    try:
        d = srv.wo_detail("zernio-publisher", "wo_det_1.json")
        assert d["editable"] is True and d["folder"] == "inbox"
        assert d["wo"]["work_order_id"] == "wo_det_1"
        assert len(d["history"]) == 1 and d["history"][0]["status"] == "done"
        assert "done" in d["logs"] and "\"ok\": true" in d["logs"]
        assert d["attachments"] == [{"label": "brief", "url": "https://x/y"}]
    finally:
        f.unlink(missing_ok=True)
        if hist_before is not None: hist.write_text(hist_before)
        else: hist.unlink(missing_ok=True)


def test_wo_detail_rejects_traversal():
    srv = _srv()
    with pytest.raises(ValueError): srv.wo_detail("zernio-publisher", "../../etc/passwd")
    with pytest.raises(ValueError): srv.wo_detail("not-an-automation", "wo_x.json")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_board_server.py::test_wo_detail_assembles_history_and_logs -v`
Expected: FAIL — `AttributeError: ... 'wo_detail'`.

- [ ] **Step 3: Implement**

In `apps/kanban-board/server.py`, after `reorder_inbox`, add:

```python
def wo_detail(automation, filename):
    """Full detail for one WO: the JSON, its history records, derived log text, attachments.
    Logs are derived from history (path-safe) — no arbitrary evidence-file reads in v1."""
    sub, folder, path = _safe_wo_path(automation, filename)
    wo = json.loads(path.read_text())
    wid = wo.get("work_order_id", filename[:-5])
    history = []
    h = sub/"history"/"runs.jsonl"
    if h.exists():
        for line in h.read_text().splitlines():
            try: r = json.loads(line)
            except Exception: continue
            if r.get("work_order_id") == wid: history.append(r)
    chunks = []
    for r in history:
        c = f"[{r.get('ts','')}] {r.get('status','')}"
        if r.get("reason"): c += f" — {r['reason']}"
        if r.get("stage"):  c += f" (stage: {r['stage']})"
        if r.get("task_report") is not None:
            c += "\n" + json.dumps(r["task_report"], indent=2)
        chunks.append(c)
    return {"wo": wo, "folder": folder, "editable": folder == "inbox",
            "history": history, "logs": "\n\n".join(chunks),
            "attachments": wo.get("attachments", [])}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_board_server.py -k wo_detail -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/kanban-board/server.py tests/test_board_server.py
git commit -m "feat(board): add wo_detail (json + history + logs + attachments)"
```

---

## Task 4: `save_wo` + `attach_link`

**Files:**
- Modify: `apps/kanban-board/server.py`
- Test: `tests/test_board_server.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_board_server.py`:

```python
def test_save_wo_validates_and_writes_inbox_only():
    srv = _srv()
    inbox = ROOT / "automations" / "zernio-publisher" / "inbox"; inbox.mkdir(parents=True, exist_ok=True)
    f = inbox / "wo_save_1.json"
    f.write_text(json.dumps({"work_order_id": "wo_save_1", "execution_method": "google_business_api",
                             "client_id": "c", "workflow_id": "wf"}))
    try:
        good = {"work_order_id": "wo_save_1", "execution_method": "google_business_api",
                "client_id": "c", "workflow_id": "wf2"}
        srv.save_wo("zernio-publisher", "wo_save_1.json", good)
        assert json.loads(f.read_text())["workflow_id"] == "wf2"
        # missing required field
        with pytest.raises(ValueError):
            srv.save_wo("zernio-publisher", "wo_save_1.json", {"work_order_id": "wo_save_1"})
        # work_order_id must match filename (no rename / path change)
        with pytest.raises(ValueError):
            srv.save_wo("zernio-publisher", "wo_save_1.json",
                        {**good, "work_order_id": "wo_other"})
    finally:
        f.unlink(missing_ok=True)


def test_save_wo_refuses_non_inbox():
    srv = _srv()
    done = ROOT / "automations" / "zernio-publisher" / "done"; done.mkdir(parents=True, exist_ok=True)
    f = done / "wo_save_done.json"
    f.write_text(json.dumps({"work_order_id": "wo_save_done", "execution_method": "google_business_api",
                             "client_id": "c", "workflow_id": "wf"}))
    try:
        with pytest.raises(ValueError):
            srv.save_wo("zernio-publisher", "wo_save_done.json",
                        {"work_order_id": "wo_save_done", "execution_method": "google_business_api",
                         "client_id": "c", "workflow_id": "wf"})
    finally:
        f.unlink(missing_ok=True)


def test_attach_link_appends_and_validates_url():
    srv = _srv()
    inbox = ROOT / "automations" / "zernio-publisher" / "inbox"; inbox.mkdir(parents=True, exist_ok=True)
    f = inbox / "wo_att_1.json"; f.write_text(json.dumps({"work_order_id": "wo_att_1"}))
    try:
        atts = srv.attach_link("zernio-publisher", "wo_att_1.json", "spec", "https://example/spec")
        assert atts == [{"label": "spec", "url": "https://example/spec"}]
        assert json.loads(f.read_text())["attachments"][0]["url"] == "https://example/spec"
        with pytest.raises(ValueError):
            srv.attach_link("zernio-publisher", "wo_att_1.json", "bad", "javascript:alert(1)")
    finally:
        f.unlink(missing_ok=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_board_server.py -k "save_wo or attach_link" -v`
Expected: FAIL — `AttributeError: ... 'save_wo'`.

- [ ] **Step 3: Implement**

In `apps/kanban-board/server.py`, after `wo_detail`, add:

```python
REQUIRED_WO = ("execution_method", "client_id", "workflow_id", "work_order_id")

def save_wo(automation, filename, wo):
    """Overwrite an inbox WO. Validated, traversal-proof, atomic. Inbox-only (gated/in-flight = RO)."""
    sub, folder, path = _safe_wo_path(automation, filename)
    if folder != "inbox":
        raise ValueError("only inbox work orders are editable")
    if not isinstance(wo, dict):
        raise ValueError("work order must be a JSON object")
    for k in REQUIRED_WO:
        if not wo.get(k):
            raise ValueError(f"missing required field: {k}")
    wid = str(wo["work_order_id"])
    if wid != pathlib.Path(wid).name or "/" in wid or "\\" in wid:
        raise ValueError("work_order_id must not contain path separators")
    if wid + ".json" != filename:
        raise ValueError("work_order_id must match the filename (rename not supported)")
    tmp = path.with_suffix(".json.tmp"); tmp.write_text(json.dumps(wo, indent=2)); tmp.replace(path)
    return str(path.relative_to(ROOT))

def attach_link(automation, filename, label, url):
    """Append an attachment reference {label,url} to a WO. Links only — no upload store."""
    sub, folder, path = _safe_wo_path(automation, filename)
    url = (url or "").strip()
    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("/")):
        raise ValueError("attachment url must be http(s) or a repo-relative path")
    wo = json.loads(path.read_text())
    atts = wo.get("attachments") or []
    atts.append({"label": (label or url).strip(), "url": url})
    wo["attachments"] = atts
    tmp = path.with_suffix(".json.tmp"); tmp.write_text(json.dumps(wo, indent=2)); tmp.replace(path)
    return atts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_board_server.py -k "save_wo or attach_link" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/kanban-board/server.py tests/test_board_server.py
git commit -m "feat(board): add save_wo + attach_link (inbox-only, validated, atomic)"
```

---

## Task 5: `fractional_board` — persona swimlane data

**Files:**
- Modify: `apps/kanban-board/server.py`
- Test: `tests/test_board_server.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_board_server.py`:

```python
def test_fractional_board_lists_browser_personas():
    srv = _srv()
    fb = srv.fractional_board()
    ids = {i["profile_id"] for i in fb["identities"]}
    # roster comes from clients/*/browser/profiles.yaml (example client persona exists in repo)
    assert "example-hvac-client-cb-agent" in ids
    lane = next(i for i in fb["identities"] if i["profile_id"] == "example-hvac-client-cb-agent")
    assert set(lane["columns"].keys()) == {"queued", "progress", "done", "held"}
    assert lane["client"] == "example-hvac-client"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_board_server.py::test_fractional_board_lists_browser_personas -v`
Expected: FAIL — `AttributeError: ... 'fractional_board'`.

- [ ] **Step 3: Implement**

In `apps/kanban-board/server.py`, after `attach_link`, add:

```python
def fractional_board(client=None):
    """Swimlane data: one lane per CloakBrowser persona (roster from browser/profiles.yaml),
    with that persona's cloakbrowser work-orders bucketed into the four state columns."""
    cols = ("queued", "progress", "done", "held")
    identities = {}
    for pf in sorted(ROOT.glob("clients/*/browser/profiles.yaml")):
        c = pf.parts[pf.parts.index("clients")+1]
        if client and c != client: continue
        for p in (yaml.safe_load(pf.read_text()) or {}).get("profiles", []):
            pid = p["profile_id"]
            identities[pid] = {"profile_id": pid, "client": c, "label": pid,
                               "paused": bool(p.get("paused")),
                               "columns": {k: [] for k in cols}}
    by = board_scan.grouped(ROOT)
    for col in cols:
        for card in by.get(col, []):
            if card.get("system") != "cloakbrowser": continue
            if client and card.get("client") != client: continue
            pid = card.get("profile_id") or "?"
            lane = identities.setdefault(pid, {"profile_id": pid, "client": card.get("client", ""),
                       "label": pid, "paused": False, "columns": {k: [] for k in cols}})
            lane["columns"][col].append(card)
    return {"generated": now_iso(),
            "identities": sorted(identities.values(), key=lambda x: x["profile_id"])}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_board_server.py::test_fractional_board_lists_browser_personas -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/kanban-board/server.py tests/test_board_server.py
git commit -m "feat(board): add fractional_board persona-swimlane projection"
```

---

## Task 6: Wire HTTP routes + serve new static assets

**Files:**
- Modify: `apps/kanban-board/server.py`

- [ ] **Step 1: Add GET routes**

In `do_GET`, alongside the existing static-file routes (after the `/mission-control.css` line), add the new JS module routes:

```python
        if path == "/board-common.js": return self._file("board-common.js", "application/javascript")
        if path == "/board.js": return self._file("board.js", "application/javascript")
        if path == "/order-modal.js": return self._file("order-modal.js", "application/javascript")
        if path == "/fractional.js": return self._file("fractional.js", "application/javascript")
```

After the leaflet vendor block, add the Sortable vendor route:

```python
        if path == "/vendor/sortable/Sortable.min.js":     # vendored drag lib (fixed name, no traversal)
            p = STATIC/"vendor"/"sortable"/"Sortable.min.js"
            if not p.exists(): return self._send(404, {"error": "vendor asset missing"})
            return self._send(200, p.read_bytes(), "application/javascript")
```

After the `/api/state` block (before `/api/catalog`), add the new read endpoints:

```python
        if path == "/api/fractional":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return self._send(200, fractional_board((qs.get("client") or [None])[0]))
        if path == "/api/wo":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                return self._send(200, wo_detail((qs.get("automation") or [""])[0],
                                                 (qs.get("filename") or [""])[0]))
            except Exception as e:
                return self._send(400, {"error": f"{type(e).__name__}: {e}"})
```

- [ ] **Step 2: Add POST routes**

In `do_POST`, inside the `try` block (alongside `/api/move`), add:

```python
            if path == "/api/reorder":
                n = reorder_inbox(b["automation"], b.get("order") or [])
                return self._send(200, {"ok": True, "reordered": n})
            if path == "/api/wo/save":
                rel = save_wo(b["automation"], b["filename"], b["wo"])
                return self._send(200, {"ok": True, "file": rel})
            if path == "/api/wo/attach":
                atts = attach_link(b["automation"], b["filename"], b.get("label", ""), b.get("url", ""))
                return self._send(200, {"ok": True, "attachments": atts})
```

- [ ] **Step 3: Smoke-test the server boots and routes resolve**

Run:
```bash
python - <<'PY'
import importlib.util, pathlib
ROOT = pathlib.Path('.').resolve()
spec = importlib.util.spec_from_file_location("ks", ROOT/"apps"/"kanban-board"/"server.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print("fractional ok:", bool(m.fractional_board()["identities"]))
print("routes present:", all(hasattr(m, n) for n in
      ["reorder_inbox","wo_detail","save_wo","attach_link","fractional_board"]))
PY
```
Expected: `fractional ok: True` and `routes present: True`.

- [ ] **Step 4: Run the full backend test suite**

Run: `python -m pytest tests/test_board_server.py tests/test_board_scan.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/kanban-board/server.py
git commit -m "feat(board): wire reorder/wo/wo-save/wo-attach/fractional routes + Sortable asset"
```

---

## Task 7: Vendor Sortable.js + split `app.js` into modules

**Files:**
- Create: `apps/kanban-board/static/vendor/sortable/Sortable.min.js`
- Create: `apps/kanban-board/static/board-common.js`
- Create: `apps/kanban-board/static/board.js`
- Modify: `apps/kanban-board/static/app.js`
- Modify: `apps/kanban-board/static/index.html`

- [ ] **Step 1: Vendor Sortable.js**

Download the pinned release into the vendor folder (single file, no deps):

```bash
mkdir -p apps/kanban-board/static/vendor/sortable
curl -fsSL https://cdn.jsdelivr.net/npm/sortablejs@1.15.6/Sortable.min.js \
  -o apps/kanban-board/static/vendor/sortable/Sortable.min.js
test -s apps/kanban-board/static/vendor/sortable/Sortable.min.js && echo "vendored OK"
```
Expected: `vendored OK`. (On Windows without curl: `Invoke-WebRequest <url> -OutFile apps/kanban-board/static/vendor/sortable/Sortable.min.js`.)

- [ ] **Step 2: Create `board-common.js` (shared helpers, moved from app.js)**

```js
// Shared helpers for the board + fractional views.
const SYS = {duoplus:["DUOPLUS","#38bdf8"],zernio:["ZERNIO","#a78bfa"],
             cloakbrowser:["CLOAK","#fbbf24"],approval:["DRAFT","#34d399"],
             wordpress:["WP","#21759b"],edge:["EDGE","#f38020"],podcast:["POD","#8b5cf6"]};
const COL_FOLDER = {queued:"inbox", progress:"working", done:"done", held:"failed"};
const esc = s => (s??"").toString().replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const initials = s => (s||"?").split(/[-_ .]/).filter(Boolean).slice(0,2)
                         .map(w=>w[0].toUpperCase()).join("") || "?";

async function apiCall(path, body=null) {
  const headers = {"Content-Type":"application/json"};
  const token = localStorage.getItem("sb-token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const opts = body ? {method:"POST", headers, body:JSON.stringify(body)} : {headers};
  const r = await fetch(path, opts);
  if (r.status === 401) { document.getElementById("auth-modal").classList.remove("mc-hide"); return null; }
  return r.json();
}

// One card. Whole card opens the rich modal (openWO, defined in order-modal.js) for wo/draft cards.
function cardHTML(c){
  const [label,color] = SYS[c.system]||["?","#888"];
  const meta = [c.period, c.age && c.age+" old"].filter(Boolean).join(" · ");
  const chip = c.profile_id ? `<span class="who" title="${esc(c.profile_id)}">${esc(initials(c.profile_id))}</span>` : "";
  const data = c.kind==="wo"
    ? `data-kind="wo" data-automation="${esc(c.automation)}" data-filename="${esc(c.filename)}" data-col="${esc(c.col)}"`
    : `data-kind="${esc(c.kind)}"`;
  const open = (c.kind==="wo")
    ? `onclick="openWO('${esc(c.automation)}','${esc(c.filename)}')"`
    : (c.kind==="draft"
        ? `onclick="openDraft('${esc(c.client)}','${esc(c.area)}','${esc(c.scope)}','${esc(c.workflow)}','${esc(c.period||'')}')"`
        : "");
  return `<div class="card" ${data} style="--sys:${color}" ${open}>
    <div class="card-top"><span class="tag">${label}${c.manual?" ·man":""}</span>
      <span class="client">${chip}${esc(c.client)}</span></div>
    <div class="title">${esc(c.title)}</div><div class="sub">${esc(c.sub)}</div>
    ${c.preview?`<div class="preview">${esc(c.preview)}</div>`:""}
    ${c.reason?`<div class="reason">${esc(c.reason)}</div>`:""}
    <div class="meta">${esc(meta)}</div></div>`;
}
```

- [ ] **Step 3: Create `board.js` (main board render — moved from app.js, drag added in Task 8)**

Move these functions **verbatim** out of the current `app.js` into `board.js`: `refresh`, `render`, `renderCalendar`, `fmtDay`, and the order-creation modal block (`openModal`, `setMode`, `updateTaskUI`, `fillWorkflows`, `fillTargets`, `createContent`, `create`, `publishApproved`, plus the `$`, `CATALOG`, `LAST`, `FILTER`, `TASKS`, `MODE` module vars and the `$("add").onclick`… event bindings at the bottom). Then **delete** the old per-card `approve`/`reject`/`move` functions and the inline button branches — those now live in `order-modal.js` (Task 9). Leave the `setView`/nav block in `app.js` (Step 4).

At the top of `board.js` keep the poll bootstrap line that already exists:

```js
setInterval(refresh, 3000);    // board poll (no-ops while the board view is hidden)
```

- [ ] **Step 4: Reduce `app.js` to the view-switch shell**

`app.js` should now contain ONLY the view-switch logic (the existing `setView`, `VALID_VIEWS`, nav `onclick` bindings, `hashchange` listener, and the initial `setView(...)` call), plus a hook for the new fractional view added in Task 10. Remove everything moved in Step 3. The existing tail:

```js
const _initial = (location.hash || "").replace("#","");
setView(VALID_VIEWS.includes(_initial) ? _initial : "mc");
```
stays in `app.js`.

- [ ] **Step 5: Update `index.html` script tags**

Replace the single `<script src="/app.js"></script>` line with the module set, loaded in dependency order, and add Sortable:

```html
<script src="/vendor/sortable/Sortable.min.js"></script>
<script src="/board-common.js"></script>
<script src="/order-modal.js"></script>
<script src="/board.js"></script>
<script src="/fractional.js"></script>
<script src="/app.js"></script>
```
(Keep `mission-control.js` loaded before these, as today.)

- [ ] **Step 6: Verify the board still renders (regression check)**

Start the server and confirm the board view loads with no console errors and cards appear.

Run: `python apps/kanban-board/server.py --port 8788` (leave running in a background shell), then use the preview tools: `preview_start` on `http://127.0.0.1:8788`, navigate to `#board`, `preview_console_logs` (expect no errors), `preview_snapshot` (expect columns + cards).

Expected: board renders, no `ReferenceError`. Order-creation modal still opens via "+ Add Work Order".

- [ ] **Step 7: Commit**

```bash
git add apps/kanban-board/static/vendor/sortable/Sortable.min.js \
        apps/kanban-board/static/board-common.js apps/kanban-board/static/board.js \
        apps/kanban-board/static/app.js apps/kanban-board/static/index.html
git commit -m "refactor(board): split app.js into modules + vendor Sortable.js"
```

---

## Task 8: Drag-and-drop on the main board (safe moves + reorder)

**Files:**
- Modify: `apps/kanban-board/static/board.js`
- Modify: `apps/kanban-board/static/styles.css`

- [ ] **Step 1: Add the drag wiring in `board.js`**

At the end of `render()` (after `g("board").innerHTML = ...` and before `renderCalendar(...)`), call a new `wireDrag()`. Add the function:

```js
function wireDrag(){
  document.querySelectorAll("#board .col .cards").forEach(list=>{
    if(list._sortable) return;                          // idempotent across polls
    list._sortable = Sortable.create(list, {
      group: "board", animation: 150, draggable: ".card[data-kind='wo']",
      filter: ".card:not([data-kind='wo'])",            // drafts/approved are not draggable
      ghostClass: "drag-ghost", onEnd: onDragEnd });
  });
}

async function onDragEnd(evt){
  const card = evt.item;
  if(card.dataset.kind !== "wo") return;
  const fromCol = evt.from.closest(".col").dataset.col;
  const toCol   = evt.to.closest(".col").dataset.col;
  const automation = card.dataset.automation, filename = card.dataset.filename;
  if(fromCol !== toCol){
    const r = await apiCall("/api/move", {automation, filename, to: COL_FOLDER[toCol]});
    if(!r || !r.ok){ alert("Move failed: "+((r&&r.error)||"unknown")); }
    refresh(); return;
  }
  if(toCol === "queued"){                               // reorder persists order_index
    const order = [...evt.to.querySelectorAll(".card[data-kind='wo']")].map(el=>el.dataset.filename);
    const r = await apiCall("/api/reorder", {automation, order});
    if(!r || !r.ok){ alert("Reorder failed: "+((r&&r.error)||"unknown")); refresh(); }
  }
}
```

For the column to expose `data-col`, update the column template in `render()` — the `<section class="col" ...>` — to include it:

```js
  g("board").innerHTML = cols.map(col=>`
    <section class="col" data-col="${esc(col.key)}" style="--accent:${col.accent}">
      <h2>${esc(col.name)}<span class="count">${col.cards.length}</span></h2>
      <div class="cards">${col.cards.length?col.cards.map(cardHTML).join(""):'<div class="empty">— clear —</div>'}</div>
    </section>`).join("");
  wireDrag();
```

- [ ] **Step 2: Add drag CSS**

Append to `apps/kanban-board/static/styles.css`:

```css
.card[data-kind="wo"]{cursor:grab}
.card[data-kind="wo"]:active{cursor:grabbing}
.drag-ghost{opacity:.4; outline:2px dashed var(--sys,#888)}
.col .cards{min-height:40px}
.card .who{display:inline-flex; align-items:center; justify-content:center;
  width:18px; height:18px; margin-right:5px; border-radius:50%;
  background:var(--sys,#888); color:#0b1220; font-size:10px; font-weight:700; vertical-align:middle}
```

- [ ] **Step 3: Manual verification (drag move + reorder)**

With the server running (Task 7 Step 6), use preview tools:
- `preview_eval`: `window.location.reload()`.
- Confirm at least one `wo` card exists in QUEUED (create one via "+ Add Work Order" if needed).
- `preview_snapshot` to capture the board; verify `.card[data-kind='wo']` carries `data-automation`/`data-filename`.
- Because pixel-drag is unreliable headless, verify the endpoints the drag calls instead:
  `preview_eval`:
  ```js
  await (await fetch('/api/reorder',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({automation:'zernio-publisher',order:[]})})).json()
  ```
  Expected: `{ok:true, reordered:0}`.
- Drafts/approved cards must NOT be draggable: confirm `cardHTML` emitted them without `data-kind="wo"` (snapshot).

- [ ] **Step 4: Commit**

```bash
git add apps/kanban-board/static/board.js apps/kanban-board/static/styles.css
git commit -m "feat(board): Sortable drag — column moves + QUEUED reorder"
```

---

## Task 9: Rich order-editor modal

**Files:**
- Create: `apps/kanban-board/static/order-modal.js`
- Modify: `apps/kanban-board/static/index.html`
- Modify: `apps/kanban-board/static/styles.css`

- [ ] **Step 1: Add the modal markup to `index.html`**

Before the existing `<div id="modal" ...>` (the order-creation modal), add the detail modal:

```html
<div id="wo-modal" class="modal hidden"><div class="sheet wo-sheet">
  <div class="wo-head"><h3 id="wo-title">Work order</h3>
    <button id="wo-close" class="btn" type="button">✕</button></div>
  <div class="tabs">
    <button class="wo-tab active" data-tab="overview" type="button">Overview</button>
    <button class="wo-tab" data-tab="history" type="button">History</button>
    <button class="wo-tab" data-tab="logs" type="button">Logs</button>
    <button class="wo-tab" data-tab="attach" type="button">Attachments</button>
  </div>
  <div id="wo-pane-overview" class="wo-pane">
    <p id="wo-ro-note" class="note hidden">In-flight / completed order — read-only.</p>
    <textarea id="wo-json" rows="16" spellcheck="false"></textarea>
    <div class="row"><button id="wo-save" class="btn primary" type="button">Save</button></div>
  </div>
  <div id="wo-pane-history" class="wo-pane hidden"></div>
  <div id="wo-pane-logs" class="wo-pane hidden"><pre id="wo-logs"></pre></div>
  <div id="wo-pane-attach" class="wo-pane hidden">
    <div id="wo-atts"></div>
    <div class="row">
      <input id="wo-att-label" placeholder="Label"><input id="wo-att-url" placeholder="https://…">
      <button id="wo-att-add" class="btn" type="button">Add link</button></div>
  </div>
</div></div>

<div id="draft-modal" class="modal hidden"><div class="sheet">
  <div class="wo-head"><h3>Review draft</h3><button id="draft-close" class="btn" type="button">✕</button></div>
  <label>Edit text (blank = keep draft as-is)<textarea id="draft-edit" rows="6"></textarea></label>
  <label>Reject reason (only used when rejecting)<input id="draft-reason"></label>
  <div class="row"><button id="draft-reject" class="btn bad" type="button">Reject</button>
    <button id="draft-approve" class="btn ok" type="button">Approve</button></div>
</div></div>
```

- [ ] **Step 2: Create `order-modal.js`**

```js
// Rich order-editor modal: WO JSON / history / logs / attachments, plus inline draft review.
let WO_CTX = null;   // {automation, filename}
let DRAFT_CTX = null;

async function openWO(automation, filename){
  WO_CTX = {automation, filename};
  const d = await apiCall("/api/wo", null && {}) || await fetch(
    `/api/wo?automation=${encodeURIComponent(automation)}&filename=${encodeURIComponent(filename)}`).then(r=>r.json());
  if(d.error){ alert("Open failed: "+d.error); return; }
  document.getElementById("wo-title").textContent = (d.wo.work_order_id||filename) + "  ·  " + d.folder;
  document.getElementById("wo-json").value = JSON.stringify(d.wo, null, 2);
  const ro = !d.editable;
  document.getElementById("wo-json").readOnly = ro;
  document.getElementById("wo-save").disabled = ro;
  document.getElementById("wo-ro-note").classList.toggle("hidden", !ro);
  renderHistory(d.history||[]);
  document.getElementById("wo-logs").textContent = d.logs || "— no log records —";
  renderAtts(d.attachments||[]);
  woTab("overview");
  document.getElementById("wo-modal").classList.remove("hidden");
}

function woTab(name){
  ["overview","history","logs","attach"].forEach(t=>
    document.getElementById("wo-pane-"+t).classList.toggle("hidden", t!==name));
  document.querySelectorAll(".wo-tab").forEach(b=>b.classList.toggle("active", b.dataset.tab===name));
}
function renderHistory(h){
  const el = document.getElementById("wo-pane-history");
  el.innerHTML = h.length ? h.map(r=>`<div class="hist-row">
      <span class="hist-st st-${esc(r.status||'')}">${esc(r.status||'?')}</span>
      <span class="hist-ts">${esc(r.ts||'')}</span>
      ${r.reason?`<div class="hist-reason">${esc(r.reason)}</div>`:""}</div>`).join("")
    : '<div class="empty">— no history yet —</div>';
}
function renderAtts(atts){
  const el = document.getElementById("wo-atts");
  el.innerHTML = atts.length ? atts.map(a=>`<div class="att-row">
      <a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.label||a.url)}</a></div>`).join("")
    : '<div class="empty">— no attachments —</div>';
}

async function saveWO(){
  let wo;
  try { wo = JSON.parse(document.getElementById("wo-json").value); }
  catch(e){ alert("Invalid JSON: "+e.message); return; }
  const r = await apiCall("/api/wo/save", {...WO_CTX, wo});
  if(!r || !r.ok){ alert("Save failed: "+((r&&r.error)||"unknown")); return; }
  alert("Saved → "+r.file); refresh();
}
async function addAtt(){
  const label = document.getElementById("wo-att-label").value.trim();
  const url   = document.getElementById("wo-att-url").value.trim();
  if(!url){ alert("URL required"); return; }
  const r = await apiCall("/api/wo/attach", {...WO_CTX, label, url});
  if(!r || !r.ok){ alert("Attach failed: "+((r&&r.error)||"unknown")); return; }
  document.getElementById("wo-att-label").value=""; document.getElementById("wo-att-url").value="";
  renderAtts(r.attachments);
}

// ---- inline draft review (replaces the old prompt()/alert() approve/reject) ----
function openDraft(client, area, scope, workflow, period){
  DRAFT_CTX = {client, area, scope, workflow, period};
  document.getElementById("draft-edit").value = "";
  document.getElementById("draft-reason").value = "";
  document.getElementById("draft-modal").classList.remove("hidden");
}
async function approveDraft(){
  const c = DRAFT_CTX, body = {client:c.client, area:c.area, scope:c.scope, workflow:c.workflow};
  if(c.period) body.period = c.period;
  const edit = document.getElementById("draft-edit").value; if(edit) body.edit = edit;
  const r = await apiCall("/api/approve", body);
  alert(r && r.ok ? `Approved (hash ${r.hash}…)` : "Error: "+((r&&r.error)||"failed"));
  document.getElementById("draft-modal").classList.add("hidden"); refresh();
}
async function rejectDraft(){
  const c = DRAFT_CTX, body = {client:c.client, area:c.area, scope:c.scope, workflow:c.workflow,
                               reason: document.getElementById("draft-reason").value || ""};
  if(c.period) body.period = c.period;
  const r = await apiCall("/api/reject", body);
  if(!r || !r.ok) alert("Error: "+((r&&r.error)||"failed"));
  document.getElementById("draft-modal").classList.add("hidden"); refresh();
}

document.getElementById("wo-close").onclick = ()=>document.getElementById("wo-modal").classList.add("hidden");
document.getElementById("wo-save").onclick  = saveWO;
document.getElementById("wo-att-add").onclick = addAtt;
document.querySelectorAll(".wo-tab").forEach(b=>b.onclick=()=>woTab(b.dataset.tab));
document.getElementById("draft-close").onclick  = ()=>document.getElementById("draft-modal").classList.add("hidden");
document.getElementById("draft-approve").onclick = approveDraft;
document.getElementById("draft-reject").onclick  = rejectDraft;
```

> Note: the first line of `openWO` simplifies to a direct `fetch` for the GET (apiCall is POST/GET-by-presence-of-body). Replace it with this clean version:
> ```js
> const d = await fetch(`/api/wo?automation=${encodeURIComponent(automation)}&filename=${encodeURIComponent(filename)}`,
>   {headers: localStorage.getItem("sb-token") ? {Authorization:`Bearer ${localStorage.getItem("sb-token")}`} : {}}
>   ).then(r=>r.json());
> ```
> Use this version; delete the `apiCall("/api/wo", null && {}) ||` fragment.

- [ ] **Step 3: Add modal CSS**

Append to `apps/kanban-board/static/styles.css`:

```css
.wo-sheet{max-width:760px; width:92vw}
.wo-head{display:flex; align-items:center; justify-content:space-between; margin-bottom:.5rem}
.wo-tab{background:none; border:none; color:#94a3b8; padding:.4rem .7rem; cursor:pointer; border-bottom:2px solid transparent}
.wo-tab.active{color:#e2e8f0; border-bottom-color:#38bdf8}
.wo-pane{margin-top:.7rem}
#wo-json{width:100%; font-family:"JetBrains Mono",monospace; font-size:12px; background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:6px; padding:.6rem}
#wo-logs{white-space:pre-wrap; max-height:50vh; overflow:auto; background:#0f172a; padding:.6rem; border-radius:6px; font-size:12px}
.hist-row{padding:.4rem 0; border-bottom:1px solid #1e293b}
.hist-st{font-weight:700; margin-right:.5rem} .hist-ts{color:#94a3b8; font-size:12px}
.hist-reason{color:#cbd5e1; font-size:12px; margin-top:.2rem}
.att-row{padding:.3rem 0}
```

- [ ] **Step 4: Manual verification (modal open / save / attach / draft)**

With the server running, `preview_eval`: `window.location.reload()`, then:
- Click a `wo` card → `wo-modal` opens, Overview shows formatted JSON.
- `preview_eval` to test save round-trip on an inbox WO:
  ```js
  await openWO('zernio-publisher','<an inbox filename>.json'); 'opened'
  ```
  then verify `#wo-json` is populated and `#wo-save` enabled for an inbox file (and disabled for a `done/` file).
- Attach: type a label+URL, click "Add link", confirm it appears and re-open shows it persisted.
- Click a draft card (NEEDS APPROVAL) → `draft-modal` opens with Approve/Reject (no browser `prompt`).

Expected: all four flows work; `preview_console_logs` shows no errors.

- [ ] **Step 5: Commit**

```bash
git add apps/kanban-board/static/order-modal.js apps/kanban-board/static/index.html apps/kanban-board/static/styles.css
git commit -m "feat(board): rich order-editor modal + inline draft review"
```

---

## Task 10: Fractional Employees swimlane board

**Files:**
- Create: `apps/kanban-board/static/fractional.js`
- Modify: `apps/kanban-board/static/index.html`
- Modify: `apps/kanban-board/static/app.js`
- Modify: `apps/kanban-board/static/styles.css`

- [ ] **Step 1: Add nav button + view container in `index.html`**

In the `<nav class="mc-nav">`, after the Kanban Board button, add:

```html
    <button id="nav-fr" class="navbtn" type="button">Fractional Employees</button>
```

After the `<div id="view-board" ...>…</div>` block, add:

```html
<div id="view-fr" class="view mc-hide">
  <div class="fr-head"><h2>FRACTIONAL EMPLOYEES <span id="fr-sub" class="gen"></span></h2></div>
  <div id="fr-board" class="fr-board"></div>
</div>
```

- [ ] **Step 2: Create `fractional.js`**

```js
// Fractional Employees: one swimlane per CloakBrowser persona. Same drag rules as the main board.
const FR_COLS = [["queued","QUEUED"],["progress","IN PROGRESS"],["done","DONE"],["held","FAILED / HELD"]];
let FR_LAST = null;

async function refreshFractional(){
  if(document.getElementById("view-fr").classList.contains("mc-hide")) return;
  FR_LAST = await apiCall("/api/fractional"); renderFractional();
}
function renderFractional(){
  const s = FR_LAST; if(!s) return;
  const ids = s.identities || [];
  document.getElementById("fr-sub").textContent = ids.length ? `· ${ids.length} personas` : "";
  document.getElementById("fr-board").innerHTML = `
    <div class="fr-colhead"><div class="fr-lane-label"></div>${
      FR_COLS.map(([,n])=>`<div class="fr-ch">${esc(n)}</div>`).join("")}</div>` +
    (ids.length ? ids.map(laneHTML).join("")
      : '<div class="empty">No personas — add one in clients/&lt;client&gt;/browser/profiles.yaml</div>');
  wireFractionalDrag();
}
function laneHTML(lane){
  return `<div class="fr-lane${lane.paused?" paused":""}">
    <div class="fr-lane-label"><span class="who">${esc(initials(lane.profile_id))}</span>
      <div><b>${esc(lane.profile_id)}</b><div class="fr-client">${esc(lane.client)}${lane.paused?" · paused":""}</div></div></div>
    ${FR_COLS.map(([key])=>`<div class="fr-cell"><div class="cards" data-col="${key}">${
      (lane.columns[key]||[]).map(cardHTML).join("") || '<div class="empty">—</div>'}</div></div>`).join("")}
  </div>`;
}
function wireFractionalDrag(){
  document.querySelectorAll("#fr-board .cards").forEach(list=>{
    if(list._sortable) return;
    list._sortable = Sortable.create(list, {
      group:"fr", animation:150, draggable:".card[data-kind='wo']",
      filter:".card:not([data-kind='wo'])", ghostClass:"drag-ghost",
      onEnd: async (evt)=>{
        const card = evt.item; if(card.dataset.kind!=="wo") return;
        const fromCol = evt.from.dataset.col, toCol = evt.to.dataset.col;
        if(fromCol===toCol) return;                       // within-lane reorder = visual only here
        const r = await apiCall("/api/move",
          {automation:card.dataset.automation, filename:card.dataset.filename, to:COL_FOLDER[toCol]});
        if(!r || !r.ok) alert("Move failed: "+((r&&r.error)||"unknown"));
        refreshFractional();
      }});
  });
}
setInterval(refreshFractional, 3000);   // no-ops while the view is hidden
```

- [ ] **Step 3: Wire the nav tab into `app.js`'s `setView`**

In `app.js`, extend `setView` to handle the `fr` view and add it to `VALID_VIEWS` + nav binding. Update `setView` body to toggle the fractional view and (de)activate its nav button:

```js
  $("view-fr").classList.toggle("mc-hide", v !== "fr");
  $("nav-fr").classList.toggle("active", v === "fr");
```
Add `"fr"` to `VALID_VIEWS`:
```js
const VALID_VIEWS = ["mc","si","ai","ci","ti","board","fr"];
```
Add the nav binding:
```js
$("nav-fr").onclick = () => setView("fr");
```
And trigger an immediate pull when the view opens — at the end of `setView`, after the existing `if(isBoard) refresh();`:
```js
  if(v === "fr") refreshFractional();
```

- [ ] **Step 4: Add swimlane CSS**

Append to `apps/kanban-board/static/styles.css`:

```css
.fr-board{display:flex; flex-direction:column; gap:8px; padding:8px}
.fr-colhead,.fr-lane{display:grid; grid-template-columns:180px repeat(4,1fr); gap:8px}
.fr-ch{color:#94a3b8; font-size:12px; font-weight:700; padding:4px 6px; text-transform:uppercase}
.fr-lane{background:#0f172a; border:1px solid #1e293b; border-radius:8px; padding:8px; align-items:stretch}
.fr-lane.paused{opacity:.55}
.fr-lane-label{display:flex; gap:8px; align-items:center}
.fr-client{color:#94a3b8; font-size:11px}
.fr-cell .cards{min-height:48px; display:flex; flex-direction:column; gap:6px}
```

- [ ] **Step 5: Manual verification (swimlanes render + nav)**

With the server running, `preview_eval`: `window.location.reload()`:
- Click "Fractional Employees" nav → `#view-fr` shows, `#view-board` hidden.
- `preview_snapshot`: expect a column header row and at least one lane for `example-hvac-client-cb-agent`.
- `preview_eval`: `(await (await fetch('/api/fractional')).json()).identities.length` → expect `>= 1`.
- Deep-link: `preview_eval`: `location.hash='#fr'` then snapshot — fractional view active.

Expected: lanes render with persona chips; no console errors.

- [ ] **Step 6: Commit**

```bash
git add apps/kanban-board/static/fractional.js apps/kanban-board/static/index.html \
        apps/kanban-board/static/app.js apps/kanban-board/static/styles.css
git commit -m "feat(board): Fractional Employees swimlane board (lane per persona)"
```

---

## Task 11: Full verification pass + legend/title polish

**Files:**
- Modify: `apps/kanban-board/static/index.html` (legend hint only)

- [ ] **Step 1: Add a drag hint to the board legend**

In `index.html`, in the `.legend` block, change the trailing muted span to:

```html
    <span class="muted">polls every 3s · drag work-orders to move · click a card to edit</span>
```

- [ ] **Step 2: Run the entire backend test suite**

Run: `python -m pytest tests/test_board_server.py tests/test_board_scan.py -v`
Expected: all PASS.

- [ ] **Step 3: End-to-end manual smoke (all features)**

With `python apps/kanban-board/server.py --port 8788` running and preview pointed at it:
1. Board view renders, no console errors (`preview_console_logs`).
2. Create a work order via "+ Add Work Order" → appears in QUEUED.
3. Open it (click) → modal shows JSON/history/logs/attachments; add an attachment link; Save an edit.
4. `/api/reorder` and `/api/move` respond `{ok:true}` (via `preview_eval` fetch checks).
5. Draft card → inline approve/reject modal (no `prompt`).
6. Fractional Employees tab → persona lanes render.
7. `preview_screenshot` of the board and of the fractional view to attach as proof.

Expected: every step passes; capture the two screenshots.

- [ ] **Step 4: Update the graphify knowledge graph (repo convention)**

Run: `graphify update .`
Expected: completes without error (AST-only, no API cost). If `graphify` is unavailable, skip.

- [ ] **Step 5: Commit**

```bash
git add apps/kanban-board/static/index.html
git commit -m "chore(board): legend drag/click hint + verification pass"
```

---

## Self-review notes (coverage check)

- Spec §"Drag-and-drop" → Tasks 1 (order_index sort), 2 (reorder endpoint), 8 (UI). ✅
- Spec §"Order-editor modal" → Tasks 3 (wo_detail), 4 (save/attach), 9 (UI). ✅
- Spec §"Fractional Employees board" → Tasks 5 (data), 10 (UI). ✅
- Spec §"Card upgrade" → Task 7 (`cardHTML` chip), 8 (CSS). ✅
- Spec §"New/changed HTTP endpoints" → Task 6 routes + Sortable asset. ✅
- Spec §"Security" → guards reused in Tasks 2–5; validated in tests (Tasks 2,3,4). ✅
- Spec §"Testing" → backend pytest Tasks 1–5; manual preview steps Tasks 7–11. ✅
- Spec §"Out of scope" → no timeline/uploads/WIP-limits/cross-board/RPA-personas tasks present. ✅
```