#!/usr/bin/env python3
"""Kanban board over the work-order + approval lifecycle.

The board is a *projection of the filesystem* (the SSOT) — it never holds its own state, so it
can't drift from reality. Columns map to the real lifecycle across all three execution
subsystems and every client's approval store:

  NEEDS APPROVAL  approvals/pending/*draft.json     (a human must sign off — easy to lose)
  QUEUED          inbox/*.json + approvals/approved  (ready / approved, not yet run)
  IN PROGRESS     working/*.json                     (executing now)
  DONE            done/*.json                         (completed)
  FAILED / HELD   failed/*.json                       (needs attention; reason from history)

  python scripts/board.py [--out PATH]      # default: board/index.html
"""
import sys, json, time, datetime, pathlib, html

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = pathlib.Path(sys.argv[sys.argv.index("--out")+1]) if "--out" in sys.argv else ROOT/"board"/"index.html"

SUBSYS = {"duoplus-rpa-orchestrator": "duoplus",
          "zernio-publisher": "zernio",
          "cloakbrowser-runner": "cloakbrowser",
          "wordpress-publisher": "wordpress",
          "edge-deployer": "edge",
          "podcast-publisher": "podcast"}
SYS = {"duoplus":     ("DUOPLUS", "#38bdf8"),
       "zernio":      ("ZERNIO",  "#a78bfa"),
       "cloakbrowser":("CLOAK",   "#fbbf24"),
       "approval":    ("DRAFT",   "#34d399"),
       "wordpress":   ("WP",      "#21759b"),
       "edge":        ("EDGE",    "#f38020"),
       "podcast":     ("POD",     "#8b5cf6")}
DEFAULT_CLIENT = {"duoplus": "example-hvac-client", "zernio": "example-hvac-client",
                  "cloakbrowser": "agency", "wordpress": "example-hvac-client",
                  "edge": "example-hvac-client", "podcast": "example-hvac-client"}

def age(ts):
    secs = max(0, time.time() - ts)
    for unit, n in (("d", 86400), ("h", 3600), ("m", 60)):
        if secs >= n: return f"{int(secs//n)}{unit}"
    return "just now"

def history_reasons(subdir):
    """work_order_id -> latest {status, reason, stage, note} from history/runs.jsonl."""
    out = {}
    h = subdir/"history"/"runs.jsonl"
    if h.exists():
        for line in h.read_text().splitlines():
            try: r = json.loads(line)
            except Exception: continue
            wid = r.get("work_order_id")
            if wid: out[wid] = r
    return out

def wo_card(p, system, col, reasons):
    wo = json.loads(p.read_text())
    client = wo.get("client_id") or DEFAULT_CLIENT.get(system, "")
    sub = wo.get("profile_id", "")
    if wo.get("location_id"): sub = f"{sub} · {wo['location_id']}"
    r = reasons.get(wo.get("work_order_id", ""), {})
    reason = r.get("reason") or r.get("note") or ""
    if r.get("stage"): reason = f"{reason} ({r['stage']})"
    return {"col": col, "system": system, "client": client,
            "title": wo.get("workflow_id", "?"), "sub": sub,
            "period": wo.get("period", ""), "age": age(p.stat().st_mtime),
            "reason": reason, "preview": "", "command": ""}

def draft_card(p, client, area):
    d = json.loads(p.read_text())
    scope = d.get("scope_id", "")
    wf = d.get("workflow_id", "")
    text = (d.get("content") or {}).get("text", "")
    created = d.get("created", "")
    try: ts = datetime.datetime.fromisoformat(created).timestamp()
    except Exception: ts = p.stat().st_mtime
    week = datetime.date.today().isocalendar()
    period_hint = f"{week.year}-W{week.week:02d}"
    cmd = f"python scripts/approve_draft.py {client} {scope} {wf} {period_hint}"
    return {"col": "approval", "system": "approval", "client": client,
            "title": f"{d.get('kind','draft')} · {wf}", "sub": scope,
            "period": "", "age": age(ts), "_ts": ts, "reason": "",
            "preview": text[:140] + ("…" if len(text) > 140 else ""),
            "command": cmd if area == "rpa" else f"# {area} draft — approve via the {area} flow"}

def approved_card(p, client):
    a = json.loads(p.read_text())
    exp = a.get("expires_at", "")
    note = ""
    try:
        if datetime.datetime.fromisoformat(exp) < datetime.datetime.now(datetime.timezone.utc):
            note = "EXPIRED"
    except Exception: pass
    return {"col": "queued", "system": "approval", "client": client,
            "title": f"approved · {a.get('workflow_id','')}", "sub": a.get("profile_id", ""),
            "period": a.get("period", ""), "age": age(p.stat().st_mtime),
            "reason": note, "preview": "", "command": ""}

def collect():
    cards = []
    # subsystem work orders
    for dirname, system in SUBSYS.items():
        sub = ROOT/"automations"/dirname
        if not sub.exists(): continue
        reasons = history_reasons(sub)
        for col, folder in (("queued", "inbox"), ("progress", "working"),
                            ("done", "done"), ("held", "failed")):
            for p in sorted((sub/folder).glob("wo_*.json")):
                cards.append(wo_card(p, system, col, reasons))
    # approval stores (drafts -> needs approval; approved -> queued)
    for area in ("rpa", "browser", "web"):
        for ap in sorted(ROOT.glob(f"clients/*/{area}/approvals")):
            client = ap.parts[ap.parts.index("clients")+1]
            for p in sorted((ap/"pending").glob("*draft.json")):
                cards.append(draft_card(p, client, area))
            for p in sorted((ap/"approved").glob("*.json")):
                if p.name == ".gitkeep": continue
                cards.append(approved_card(p, client))
    return cards

COLS = [("approval", "NEEDS APPROVAL", "human sign-off", "#fbbf24"),
        ("queued",   "QUEUED",          "ready to run",   "#38bdf8"),
        ("progress", "IN PROGRESS",     "executing",      "#a78bfa"),
        ("done",     "DONE",            "completed",      "#34d399"),
        ("held",     "FAILED / HELD",   "needs attention","#f87171")]

def render(cards):
    by = {c[0]: [x for x in cards if x["col"] == c[0]] for c in COLS}
    # oldest-first in the approval column (smallest timestamp = most at risk of being lost)
    by["approval"].sort(key=lambda x: x.get("_ts", 0))
    e = html.escape
    cols_html = ""
    for key, name, desc, accent in COLS:
        items = by.get(key, [])
        cards_html = ""
        for c in items:
            slabel, scolor = SYS[c["system"]]
            meta = " · ".join(x for x in [c["period"], c["age"] + " old"] if x)
            preview = f'<div class="preview">{e(c["preview"])}</div>' if c["preview"] else ""
            reason = f'<div class="reason">{e(c["reason"])}</div>' if c["reason"] else ""
            command = f'<code class="cmd">{e(c["command"])}</code>' if c["command"] else ""
            cards_html += f'''
              <div class="card" style="--sys:{scolor}">
                <div class="card-top"><span class="tag">{e(slabel)}</span><span class="client">{e(c["client"])}</span></div>
                <div class="title">{e(c["title"])}</div>
                <div class="sub">{e(c["sub"])}</div>
                {preview}{reason}
                <div class="meta">{e(meta)}</div>
                {command}
              </div>'''
        if not items:
            cards_html = '<div class="empty">— clear —</div>'
        cols_html += f'''
          <section class="col" style="--accent:{accent}">
            <header><h2>{e(name)}</h2><span class="count">{len(items)}</span><span class="desc">{e(desc)}</span></header>
            <div class="cards">{cards_html}</div>
          </section>'''
    need = len(by.get("approval", []))
    banner = (f'<div class="banner">{need} item(s) need your approval — they will not move until you sign off</div>'
              if need else '<div class="banner ok">nothing waiting on you</div>')
    now = datetime.datetime.now().strftime("%a %d %b %Y · %H:%M")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agency SERP OS — Board</title>
<style>
:root{{--bg:#0b0f14;--panel:#11171f;--card:#161d27;--line:#222c39;--ink:#e6edf3;--dim:#7d8a9a;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--ink);font-family:'Sora',sans-serif;
  background-image:radial-gradient(circle at 20% -10%,rgba(56,189,248,.06),transparent 40%),radial-gradient(circle at 90% 0,rgba(167,139,250,.05),transparent 35%);
  min-height:100vh;padding:20px;}}
.head{{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:6px}}
.head h1{{font-family:'JetBrains Mono',monospace;font-size:18px;letter-spacing:.06em;font-weight:700}}
.head .gen{{color:var(--dim);font-size:12px;font-family:'JetBrains Mono',monospace}}
.banner{{margin:14px 0;padding:10px 14px;border-radius:8px;font-weight:600;font-size:14px;
  background:rgba(251,191,36,.12);border:1px solid rgba(251,191,36,.4);color:#fcd34d}}
.banner.ok{{background:rgba(52,211,153,.10);border-color:rgba(52,211,153,.35);color:#6ee7b7}}
.board{{display:grid;grid-template-columns:repeat(5,minmax(240px,1fr));gap:14px;margin-top:8px}}
@media(max-width:1100px){{.board{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:680px){{.board{{grid-template-columns:1fr}}}}
.col{{background:var(--panel);border:1px solid var(--line);border-top:3px solid var(--accent);border-radius:10px;padding:12px;min-height:120px}}
.col header{{display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap}}
.col h2{{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:.08em;color:var(--accent)}}
.col .count{{font-family:'JetBrains Mono',monospace;font-weight:700;background:var(--card);border:1px solid var(--line);border-radius:20px;padding:1px 9px;font-size:12px}}
.col .desc{{color:var(--dim);font-size:11px;width:100%}}
.cards{{display:flex;flex-direction:column;gap:10px}}
.card{{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--sys);border-radius:8px;padding:10px 11px}}
.card-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:5px}}
.tag{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;letter-spacing:.06em;color:var(--sys)}}
.client{{font-size:10px;color:var(--dim)}}
.title{{font-weight:600;font-size:13.5px;line-height:1.3}}
.sub{{color:var(--dim);font-size:12px;margin-top:2px;word-break:break-all}}
.preview{{margin-top:7px;font-size:12px;line-height:1.45;color:#c8d3df;background:#0d131b;border:1px solid var(--line);border-radius:6px;padding:7px 8px}}
.reason{{margin-top:6px;font-size:11.5px;color:#fca5a5;font-family:'JetBrains Mono',monospace}}
.meta{{margin-top:7px;font-size:11px;color:var(--dim);font-family:'JetBrains Mono',monospace}}
.cmd{{display:block;margin-top:8px;font-family:'JetBrains Mono',monospace;font-size:11px;color:#fcd34d;background:#0d131b;border:1px dashed rgba(251,191,36,.4);border-radius:6px;padding:7px 8px;white-space:pre-wrap;word-break:break-all;cursor:text}}
.empty{{color:var(--dim);font-size:12px;font-style:italic;padding:6px 2px}}
.legend{{margin-top:18px;display:flex;gap:14px;flex-wrap:wrap;color:var(--dim);font-size:11px;font-family:'JetBrains Mono',monospace}}
.legend span b{{color:var(--ink)}}
.dot{{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:middle}}
</style></head><body>
<div class="head"><h1>AGENCY · SERP OS — BOARD</h1><span class="gen">generated {now} · projection of the filesystem</span></div>
{banner}
<div class="board">{cols_html}</div>
<div class="legend">
  <span><i class="dot" style="background:#38bdf8"></i><b>DuoPlus</b> phone RPA</span>
  <span><i class="dot" style="background:#a78bfa"></i><b>Zernio</b> GBP + social API</span>
  <span><i class="dot" style="background:#fbbf24"></i><b>CloakBrowser</b> browser agents</span>
  <span><i class="dot" style="background:#34d399"></i><b>Draft</b> awaiting approval</span>
  <span>· re-run <b>python scripts/board.py</b> to refresh</span>
</div>
</body></html>'''

def main():
    cards = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(cards))
    counts = {}
    for c in cards: counts[c["col"]] = counts.get(c["col"], 0) + 1
    print(f"board -> {OUT}")
    print("  " + " | ".join(f"{k}:{counts.get(k,0)}" for k, *_ in COLS))

if __name__ == "__main__": main()
