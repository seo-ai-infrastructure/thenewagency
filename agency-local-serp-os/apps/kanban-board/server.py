#!/usr/bin/env python3
"""Live Kanban board server for agency-local-serp-os. Localhost-only, stdlib-only.

A projection of the filesystem (the SSOT): it scans the real work-order and approval folders.
Interactive actions are wired to the REAL machinery, not a parallel abstraction:
  - Approve / Reject  -> lib.approvals (same hashed/scoped/expiring artifact verify_approval needs)
  - Create work order -> a TYPED work order (execution_method/workflow_id/profile/period) your
                         DuoPlus / Zernio / CloakBrowser runners actually pick up
  - Move              -> bounded recovery only; logged to history as a manual_override

  python apps/kanban-board/server.py [--host 127.0.0.1] [--port 8787]
Open http://127.0.0.1:8787 . The browser polls every 3s.
"""
import sys, os, json, subprocess, datetime, pathlib, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve().parent
def find_root(s):
    for d in [s, *s.parents]:
        if (d/"lib").exists(): return d
    raise SystemExit("repo root not found")
ROOT = find_root(HERE); sys.path.insert(0, str(ROOT))
import yaml
from lib import board_scan, approvals, mission_control
from lib.env import load_env; load_env()      # so creators run with ANTHROPIC_API_KEY etc.

# Orderable content tasks (each runs a creator -> a pending draft a human then approves).
CREATORS = {
    "wp_article": {"label": "WordPress article",      "script": "automations/article-writer/run.py",  "args": ["--kind", "wp"],       "input": "--topic", "slug": True},
    "linkedin":   {"label": "LinkedIn Pulse article", "script": "automations/article-writer/run.py",  "args": ["--kind", "linkedin"], "input": "--topic", "slug": True},
    "quora":      {"label": "Quora answer",           "script": "automations/article-writer/run.py",  "args": ["--kind", "quora"],    "input": "--topic", "slug": True},
    "facebook":   {"label": "Facebook post",          "script": "automations/article-writer/run.py",  "args": ["--kind", "facebook"], "input": "--topic", "slug": True},
    "reddit":     {"label": "Reddit post",            "script": "automations/article-writer/run.py",  "args": ["--kind", "reddit"],   "input": "--topic", "slug": True},
    "edge_html":  {"label": "Edge HTML + Schema",     "script": "scripts/gen_edge_html.py",            "args": [],                      "input": "--topic", "slug": True},
    "podcast":    {"label": "Podcast episode",        "script": "automations/podcast-producer/run.py", "args": [],                      "input": "--topic", "slug": True},
    "tool":       {"label": "Custom tool / widget",   "script": "automations/tool-builder/run.py",     "args": [],                      "input": "--tool",  "slug": True},
    "gbp_post":   {"label": "GBP post — update", "script": "automations/content-writer/run.py", "args": ["--kind", "post"],   "input": "--brief", "location": True},
    "gbp_event":  {"label": "GBP post — event",  "script": "automations/content-writer/run.py", "args": ["--kind", "event"], "input": "--brief", "location": True},
    "gbp_offer":  {"label": "GBP post — offer",  "script": "automations/content-writer/run.py", "args": ["--kind", "offer"], "input": "--brief", "location": True},
    "gbp_week":   {"label": "GBP weekly batch (5 posts, review)", "script": "scripts/gen_gbp_posts.py", "args": ["--count", "5", "--review"], "input": None},
    "youtube_video":    {"label": "Upload YouTube video / short",        "script": "automations/video-producer/run.py", "args": ["--workflow", "youtube_upload", "--area", "browser"], "input": "--brief", "also_title": True, "scope_cb": True, "bg": True},
    "reddit_comment":   {"label": "Comment — Reddit (thread URL)",       "script": "automations/comment-writer/run.py", "args": ["--kind", "reddit"],   "input": "--brief", "target": True},
    "facebook_comment": {"label": "Comment — Facebook (post/group URL)", "script": "automations/comment-writer/run.py", "args": ["--kind", "facebook"], "input": "--brief", "target": True},
    "linkedin_comment": {"label": "Comment — LinkedIn (post URL)",       "script": "automations/comment-writer/run.py", "args": ["--kind", "linkedin"], "input": "--brief", "target": True},
    "youtube_comment":  {"label": "Comment — YouTube (video URL)",       "script": "automations/comment-writer/run.py", "args": ["--kind", "youtube"],  "input": "--brief", "target": True},
    "pinterest_pin":    {"label": "Pinterest pin",            "script": "automations/video-producer/run.py", "args": ["--workflow", "pinterest_pin", "--area", "browser", "--still-only"], "input": "--brief", "also_title": True, "scope_cb": True, "link": True, "url_label": "Destination link (optional)", "bg": True},
    "eventbrite":       {"label": "Eventbrite event (local)", "script": "automations/event-writer/run.py",   "args": [],                  "input": "--brief"},
    "patch":            {"label": "Patch.com local article",  "script": "automations/article-writer/run.py", "args": ["--kind", "patch"], "input": "--topic", "slug": True},
    "nextdoor":         {"label": "Nextdoor post",            "script": "automations/article-writer/run.py", "args": ["--kind", "nextdoor"], "input": "--topic", "slug": True},
    "review_reply":     {"label": "Google review reply",      "script": "automations/content-writer/run.py", "args": ["--kind", "review_reply"], "input": "--review", "location": True, "review_id": True, "url_label": "Review ID"},
    "gbp_image":        {"label": "GBP image upload",         "script": "automations/video-producer/run.py", "args": ["--workflow", "gbp_photo_upload", "--area", "rpa", "--still-only"], "input": "--brief", "location": True, "bg": True},
}
_INPUT_LABEL = {"--topic": "Topic", "--brief": "Brief / theme", "--tool": "Tool name",
                "--review": "Customer's review (paste it)", None: "(no input — generates a batch)"}

def tasks_list():
    return [{"id": k, "label": v["label"], "input_label": _INPUT_LABEL.get(v.get("input"), "Topic"),
             "needs_input": v.get("input") is not None, "needs_slug": bool(v.get("slug")),
             "needs_target": bool(v.get("target")) or bool(v.get("link")) or bool(v.get("review_id")),
             "url_label": v.get("url_label", "Target URL"),
             "url_required": bool(v.get("target")) or bool(v.get("review_id"))}
            for k, v in CREATORS.items()]

def create_content(client, task_id, topic, slug, target=""):
    spec = CREATORS.get(task_id)
    if not spec: raise ValueError(f"unknown content task {task_id}")
    if (spec.get("target") or spec.get("review_id")) and not (target or "").strip():
        raise ValueError("target URL is required for comment tasks" if spec.get("target")
                         else "a Review ID is required for this task")
    cmd = [sys.executable, str(ROOT/spec["script"]), "--client", client] + list(spec.get("args", []))
    if spec.get("input") and topic:   cmd += [spec["input"], topic]
    if spec.get("also_title") and topic: cmd += ["--title", topic]
    if spec.get("slug") and slug:     cmd += ["--slug", slug]
    if spec.get("target") and target: cmd += ["--target", target.strip()]
    if spec.get("link") and (target or "").strip(): cmd += ["--link", target.strip()]   # pinterest dest link (optional)
    if spec.get("review_id") and (target or "").strip(): cmd += ["--review-id", target.strip()]
    if spec.get("scope_cb"):          cmd += ["--scope", f"{client}-cb-agent"]
    if spec.get("location"):
        gbp = ROOT/"clients"/client/"rpa"/"google_business.yaml"
        if gbp.exists():
            cmd += ["--location", str((yaml.safe_load(gbp.read_text()) or {}).get("default_location_id", "locations/REPLACE"))]
    if spec.get("bg"):     # slow task (e.g. Higgsfield video) -> run detached; draft appears when ready
        subprocess.Popen(cmd, cwd=str(ROOT))
        return {"ok": True, "task": spec["label"], "output": "started — appears in NEEDS APPROVAL when ready"}
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=220)
    lines = (r.stdout or "").strip().splitlines()
    return {"ok": r.returncode == 0, "task": spec["label"],
            "output": lines[-1] if lines else (r.stderr or "")[-300:],
            "error": (r.stderr or "")[-300:] if r.returncode else ""}

STATIC = HERE/"static"
INBOX_DIR = {"duoplus_rpa": "duoplus-rpa-orchestrator",
             "google_business_api": "zernio-publisher",
             "cloakbrowser": "cloakbrowser-runner",
             "wordpress_api": "wordpress-publisher",
             "cloudflare_edge": "edge-deployer",
             "castopod_api": "podcast-publisher"}
AREA_OF = {"duoplus_rpa": "rpa", "google_business_api": "rpa", "cloakbrowser": "browser",
           "wordpress_api": "web", "cloudflare_edge": "web", "castopod_api": "web"}
AREAS = ("rpa", "browser", "web")

def now_iso(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def this_week():
    c = datetime.date.today().isocalendar(); return f"{c.year}-W{c.week:02d}"
def today(): return datetime.date.today().isoformat()   # default approval/wo period = date (daily-granular)

# ---------------- catalog (for the Create form) ----------------
def catalog():
    out = {}
    for area in AREAS:
        for wf_path in sorted(ROOT.glob(f"clients/*/{area}/workflows.yaml")):
            client = wf_path.parts[wf_path.parts.index("clients")+1]
            base = wf_path.parent
            entry = out.setdefault(client, {"workflows": [], "profiles": {}, "locations": []})
            for w in (yaml.safe_load(wf_path.read_text()) or {}).get("workflows", []):
                entry["workflows"].append({"id": w["workflow_id"], "area": area,
                    "execution_method": w.get("execution_method"),
                    "approval_required": bool(w.get("approval_required")),
                    "customer_facing": bool(w.get("customer_facing"))})
            pf = base/"profiles.yaml"
            if pf.exists():
                for p in (yaml.safe_load(pf.read_text()) or {}).get("profiles", []):
                    entry["profiles"].setdefault(area, []).append(p["profile_id"])
            gb = base/"google_business.yaml"
            if gb.exists():
                g = yaml.safe_load(gb.read_text()) or {}
                for loc in g.get("locations", []):
                    entry["locations"].append(loc.get("id"))
            if area == "web":      # content slugs to target for wordpress/edge/podcast work orders
                scopes = set()
                for store in ("pending", "approved"):
                    for f in (base/"approvals"/store).glob("*.json"):
                        if f.name != ".gitkeep":
                            scopes.add(f.name.split("__")[0])
                entry["web_scopes"] = sorted(scopes)
    return out

# ---------------- typed work-order creation ----------------
def build_work_order(client, workflow_id, target, period, task_params):
    wf = None; area = None
    for a in AREAS:
        wfp = ROOT/"clients"/client/a/"workflows.yaml"
        if wfp.exists():
            for w in (yaml.safe_load(wfp.read_text()) or {}).get("workflows", []):
                if w["workflow_id"] == workflow_id:
                    wf, area = w, a; break
        if wf: break
    if not wf:
        raise ValueError(f"workflow {workflow_id} not found for client {client}")
    method = wf.get("execution_method")
    if method not in INBOX_DIR:
        raise ValueError(f"workflow {workflow_id} has unsupported execution_method {method}")
    period = period or today()
    base = ROOT/"clients"/client/AREA_OF[method]
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    wo = {"execution_method": method, "client_id": client, "workflow_id": workflow_id,
          "period": period, "order_index": 0, "manual": True, "issued_by": "board",
          "customer_facing": bool(wf.get("customer_facing")),
          "task_params": task_params or {}}
    if method == "google_business_api":
        scope = str(target).replace("/", "_")
        gb = yaml.safe_load((base/"google_business.yaml").read_text()) if (base/"google_business.yaml").exists() else {}
        wo.update({"work_order_id": f"wo_manual_{ts}_{scope}", "profile_id": scope,
                   "account_id": gb.get("account_id", "REPLACE"), "location_id": target})
    else:  # duoplus_rpa | cloakbrowser
        wo.update({"work_order_id": f"wo_manual_{ts}_{target}", "profile_id": target})
        if method == "duoplus_rpa":
            profs = {p["profile_id"]: p for p in (yaml.safe_load((base/"profiles.yaml").read_text()) or {}).get("profiles", [])}
            wo["phone_id"] = profs.get(target, {}).get("phone_id", "phone_unknown")
    if wf.get("approval_required"):
        wo["approval_ref"] = str(base/"approvals"/"approved"/f"{wo['profile_id']}__{workflow_id}__{period}.json")
    else:
        wo["approval_ref"] = None
    inbox = ROOT/"automations"/INBOX_DIR[method]/"inbox"; inbox.mkdir(parents=True, exist_ok=True)
    out = inbox/f"{wo['work_order_id']}.json"
    tmp = out.with_suffix(".json.tmp"); tmp.write_text(json.dumps(wo, indent=2)); tmp.replace(out)  # atomic
    return wo["work_order_id"], str(out.relative_to(ROOT))

# ---------------- recovery move (bounded + logged) ----------------
def move_wo(automation, filename, to):
    if to not in ("inbox", "working", "done", "failed"):
        raise ValueError("bad target column")
    if automation not in INBOX_DIR.values():          # only real automation dirs
        raise ValueError("unknown automation")
    if filename != pathlib.Path(filename).name or not filename.endswith(".json"):
        raise ValueError("bad filename")              # no path separators / traversal
    sub = ROOT/"automations"/automation
    src = None
    for folder in ("inbox", "working", "done", "failed"):
        cand = sub/folder/filename
        if cand.exists(): src = cand; break
    if not src: raise FileNotFoundError(filename)
    dst = sub/to/filename; dst.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dst)
    wid = filename[:-5] if filename.endswith(".json") else filename
    h = sub/"history"/"runs.jsonl"; h.parent.mkdir(parents=True, exist_ok=True)
    with h.open("a") as f:
        f.write(json.dumps({"ts": now_iso(), "work_order_id": wid, "status": to,
                            "reason": "manual_override via board"}) + "\n")
    return str(dst.relative_to(ROOT))

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
    """Rewrite order_index 0..N on the named inbox WOs (advisory triage order).
    Validates the whole list before writing so a bad filename can't leave partial state.
    Filenames not present in the inbox are skipped (they may have moved since the client read)."""
    if automation not in INBOX_DIR.values():
        raise ValueError("unknown automation")
    for filename in order:
        if filename != pathlib.Path(filename).name or not filename.endswith(".json"):
            raise ValueError("bad filename")
    inbox = ROOT/"automations"/automation/"inbox"
    written = 0
    for i, filename in enumerate(order):
        p = inbox/filename
        if not p.exists():
            continue
        wo = json.loads(p.read_text()); wo["order_index"] = i
        tmp = p.with_suffix(".json.tmp"); tmp.write_text(json.dumps(wo, indent=2)); tmp.replace(p)
        written += 1
    return written

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
    # attachments are a lightweight annotation — allowed on WOs in any folder, unlike save_wo (inbox-only)
    sub, folder, path = _safe_wo_path(automation, filename)
    url = (url or "").strip()
    is_http = url.startswith("http://") or url.startswith("https://")
    is_relative = url.startswith("/") and not url.startswith("//")   # repo-relative, not protocol-relative
    if not (is_http or is_relative):
        raise ValueError("attachment url must be http(s) or a repo-relative path")
    wo = json.loads(path.read_text())
    atts = wo.get("attachments") or []
    atts.append({"label": (label or url).strip(), "url": url})
    wo["attachments"] = atts
    tmp = path.with_suffix(".json.tmp"); tmp.write_text(json.dumps(wo, indent=2)); tmp.replace(path)
    return atts

# ---------------- HTTP ----------------
class Handler(BaseHTTPRequestHandler):
    def _guard(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):     # DNS-rebinding guard (it can write files)
            self._send(403, {"error": "localhost only"}); return False
        return True

    def _csrf_ok(self):
        # Block cross-site POSTs even though Host is localhost: a page on another origin in a browser
        # on this machine could otherwise fetch() these state-changing endpoints (CSRF). Modern
        # browsers send Sec-Fetch-Site; all send Origin on cross-origin POST.
        sfs = self.headers.get("Sec-Fetch-Site")
        if sfs and sfs not in ("same-origin", "same-site", "none"):
            return False
        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
            return False
        return True
    def _send(self, code, obj, ctype="application/json", extra_headers=None):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")
    def log_message(self, *a): pass

    def do_GET(self):
        if not self._guard(): return
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"): return self._file("index.html", "text/html")
        if path == "/app.js": return self._file("app.js", "application/javascript")
        if path == "/styles.css": return self._file("styles.css", "text/css")
        if path == "/mission-control.js": return self._file("mission-control.js", "application/javascript")
        if path == "/mission-control.css": return self._file("mission-control.css", "text/css")
        if path == "/vendor/apexcharts.min.js":          # vendored chart lib (fixed name, no traversal)
            p = STATIC/"vendor"/"apexcharts.min.js"
            if not p.exists(): return self._send(404, {"error": "vendor asset missing"})
            return self._send(200, p.read_bytes(), "application/javascript")
        if path == "/vendor/leaflet/leaflet.js":          # vendored map lib (fixed name, no traversal)
            p = STATIC/"vendor"/"leaflet"/"leaflet.js"
            if not p.exists(): return self._send(404, {"error": "vendor asset missing"})
            return self._send(200, p.read_bytes(), "application/javascript")
        if path == "/vendor/leaflet/leaflet.css":
            p = STATIC/"vendor"/"leaflet"/"leaflet.css"
            if not p.exists(): return self._send(404, {"error": "vendor asset missing"})
            return self._send(200, p.read_bytes(), "text/css")
        if path == "/api/mc/export.csv":                  # FULL dashboard CSV (client deliverable)
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            client = (qs.get("client") or [None])[0]
            csv_text = mission_control.dashboard_csv(ROOT, client)
            slug = "".join(c if c.isalnum() else "-" for c in (client or "client").lower()).strip("-") or "client"
            fn = f"dashboard-{slug}.csv"
            return self._send(200, ("﻿" + csv_text).encode("utf-8"), "text/csv; charset=utf-8",
                              {"Content-Disposition": f'attachment; filename="{fn}"'})
        if path.startswith("/api/mc/"):                  # read-only dashboard projections
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            client = (qs.get("client") or [None])[0]
            view = path[len("/api/mc/"):]
            fn = {"command_center": mission_control.command_center,
                  "search_intelligence": mission_control.search_intelligence,
                  "ai_search": mission_control.ai_search,
                  "aeo": mission_control.aeo,
                  "competition_intell": mission_control.competition_intell,
                  "threat_intelligence": mission_control.threat_intelligence}.get(view)
            if not fn: return self._send(404, {"error": "unknown view"})
            return self._send(200, fn(ROOT, client))
        if path == "/api/state":
            by = board_scan.grouped(ROOT)
            cols = [{"key": k, "name": n, "accent": a, "cards": by.get(k, [])} for k, n, a in board_scan.COLS]
            calendar = board_scan.content_calendar(ROOT)
            clients = sorted({c.get("client") for col in cols for c in col["cards"] if c.get("client")}
                             | {e["client"] for e in calendar})
            return self._send(200, {"generated": now_iso(),
                                    "counts": {k: len(by.get(k, [])) for k, *_ in board_scan.COLS},
                                    "columns": cols, "calendar": calendar, "clients": clients})
        if path == "/api/catalog": return self._send(200, catalog())
        if path == "/api/tasks": return self._send(200, tasks_list())
        return self._send(404, {"error": "not found"})

    def _file(self, name, ctype):
        p = STATIC/name
        if not p.exists(): return self._send(404, {"error": name})
        self._send(200, p.read_bytes(), ctype)

    def do_POST(self):
        if not self._guard(): return
        if not self._csrf_ok():
            return self._send(403, {"error": "cross-site POST blocked"})
        path = urllib.parse.urlparse(self.path).path
        try:
            b = self._body()
            if path == "/api/approve":
                out, h = approvals.approve_draft(ROOT, b["client"], b.get("area", "rpa"),
                    b["scope"], b["workflow"], b.get("period") or today(),
                    int(b.get("days", 7)), b.get("edit"))
                return self._send(200, {"ok": True, "file": out.name, "hash": h[:12]})
            if path == "/api/reject":
                dst = approvals.reject_draft(ROOT, b["client"], b.get("area", "rpa"),
                    b["scope"], b["workflow"], b.get("reason", ""), period=b.get("period"))
                return self._send(200, {"ok": True, "file": dst.name})
            if path == "/api/create":
                wid, rel = build_work_order(b["client"], b["workflow_id"], b.get("target"),
                    b.get("period"), b.get("task_params") or {})
                return self._send(200, {"ok": True, "work_order_id": wid, "inbox": rel})
            if path == "/api/create_content":
                return self._send(200, create_content(b["client"], b["task"], b.get("topic", ""),
                                                       b.get("slug", ""), b.get("target", "")))
            if path == "/api/move":
                rel = move_wo(b["automation"], b["filename"], b["to"])
                return self._send(200, {"ok": True, "moved_to": rel})
            return self._send(404, {"error": "not found"})
        except Exception as e:
            return self._send(400, {"error": f"{type(e).__name__}: {e}"})

def main():
    host = sys.argv[sys.argv.index("--host")+1] if "--host" in sys.argv else "127.0.0.1"
    port = int(sys.argv[sys.argv.index("--port")+1]) if "--port" in sys.argv else 8787
    print(f"Kanban board: http://{host}:{port}  (root: {ROOT})")
    ThreadingHTTPServer((host, port), Handler).serve_forever()

if __name__ == "__main__": main()
