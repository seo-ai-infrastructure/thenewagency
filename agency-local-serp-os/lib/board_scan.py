"""Shared filesystem scanner: projects work-order + approval state into board cards.
Read-only. Includes clients/*/rpa/approvals AND clients/*/browser/approvals."""
import json, re, time, datetime, pathlib

SUBSYS = {"duoplus-rpa-orchestrator": "duoplus", "zernio-publisher": "zernio",
          "cloakbrowser-runner": "cloakbrowser", "wordpress-publisher": "wordpress",
          "edge-deployer": "edge", "podcast-publisher": "podcast"}
SYS = {"duoplus": ("DUOPLUS", "#38bdf8"), "zernio": ("ZERNIO", "#a78bfa"),
       "cloakbrowser": ("CLOAK", "#fbbf24"), "approval": ("DRAFT", "#34d399"),
       "wordpress": ("WP", "#21759b"), "edge": ("EDGE", "#f38020"), "podcast": ("POD", "#8b5cf6")}
DEFAULT_CLIENT = {"duoplus": "example-hvac-client", "zernio": "example-hvac-client",
                  "cloakbrowser": "agency", "wordpress": "example-hvac-client",
                  "edge": "example-hvac-client", "podcast": "example-hvac-client"}
COLS = [("approval", "NEEDS APPROVAL", "#fbbf24"), ("queued", "QUEUED", "#38bdf8"),
        ("progress", "IN PROGRESS", "#a78bfa"), ("done", "DONE", "#34d399"),
        ("held", "FAILED / HELD", "#f87171")]

def age(ts):
    secs = max(0, time.time() - ts)
    for u, n in (("d", 86400), ("h", 3600), ("m", 60)):
        if secs >= n: return f"{int(secs//n)}{u}"
    return "now"

def _hist(subdir):
    out = {}; h = subdir/"history"/"runs.jsonl"
    if h.exists():
        for line in h.read_text().splitlines():
            try: r = json.loads(line)
            except Exception: continue
            if r.get("work_order_id"): out[r["work_order_id"]] = r
    return out

def collect(root):
    root = pathlib.Path(root); cards = []
    for dirname, system in SUBSYS.items():
        sub = root/"automations"/dirname
        if not sub.exists(): continue
        reasons = _hist(sub)
        for col, folder in (("queued", "inbox"), ("progress", "working"), ("done", "done"), ("held", "failed")):
            for p in sorted((sub/folder).glob("wo_*.json")):
                try: wo = json.loads(p.read_text())
                except Exception: continue
                sub_t = wo.get("profile_id", "")
                if wo.get("location_id"): sub_t = f"{sub_t} · {wo['location_id']}"
                r = reasons.get(wo.get("work_order_id", ""), {})
                reason = r.get("reason") or r.get("note") or ""
                if r.get("stage"): reason = f"{reason} ({r['stage']})"
                cards.append({"col": col, "system": system,
                    "client": wo.get("client_id") or DEFAULT_CLIENT.get(system, ""),
                    "title": wo.get("workflow_id", "?"), "sub": sub_t, "period": wo.get("period", ""),
                    "age": age(p.stat().st_mtime), "reason": reason, "preview": "",
                    "kind": "wo", "automation": dirname, "filename": p.name,
                    "wo_id": wo.get("work_order_id", ""), "manual": wo.get("manual", False)})
    for area in ("rpa", "browser", "web"):
        for ap in sorted(root.glob(f"clients/*/{area}/approvals")):
            client = ap.parts[ap.parts.index("clients")+1]
            for p in sorted((ap/"pending").glob("*draft.json")):
                try: d = json.loads(p.read_text())
                except Exception: continue
                scope = d.get("scope_id", ""); wf = d.get("workflow_id", "")
                text = (d.get("content") or {}).get("text", "")
                try: ts = datetime.datetime.fromisoformat(d.get("created", "")).timestamp()
                except Exception: ts = p.stat().st_mtime
                cards.append({"col": "approval", "system": "approval", "client": client,
                    "title": f"{d.get('kind','draft')} · {wf}", "sub": f"{area}/{scope}",
                    "period": d.get("period", ""),     # drafts may declare an approval period (e.g. GBP post date)
                    "age": age(ts), "_ts": ts, "reason": "", "preview": text[:160] + ("…" if len(text) > 160 else ""),
                    "kind": "draft", "area": area, "scope": scope, "workflow": wf, "client_": client})
            for p in sorted((ap/"pending").glob("rec_*.json")):   # SERP-gap recommendations (info cards)
                try: d = json.loads(p.read_text())
                except Exception: continue
                g = d.get("gap", {})
                try: ts = datetime.datetime.fromisoformat(d.get("created", "")).timestamp()
                except Exception: ts = p.stat().st_mtime
                cards.append({"col": "approval", "system": "approval", "client": client,
                    "title": f"recommendation · {g.get('feature_type', '')}",
                    "sub": f"{area}/{g.get('keyword', '')}", "period": "", "age": age(ts), "_ts": ts,
                    "reason": d.get("suggested_action", ""), "preview": (d.get("note") or "")[:160],
                    "kind": "recommendation", "area": area, "scope": d.get("recommendation_id", ""), "workflow": ""})
            for p in sorted((ap/"approved").glob("*.json")):
                if p.name == ".gitkeep": continue
                try: a = json.loads(p.read_text())
                except Exception: continue
                note = ""
                try:
                    if datetime.datetime.fromisoformat(a.get("expires_at", "")) < datetime.datetime.now(datetime.timezone.utc):
                        note = "EXPIRED"
                except Exception: pass
                cards.append({"col": "queued", "system": "approval", "client": client,
                    "title": f"approved · {a.get('workflow_id','')}", "sub": f"{area}/{a.get('profile_id','')}",
                    "period": a.get("period", ""), "age": age(p.stat().st_mtime), "reason": note,
                    "preview": "", "kind": "approved", "area": area,
                    "workflow": a.get("workflow_id", ""), "scope": a.get("profile_id", "")})
    return cards

def grouped(root):
    cards = collect(root)
    by = {c[0]: [x for x in cards if x["col"] == c[0]] for c in COLS}
    # oldest-first (smallest timestamp): the drafts most at risk of being forgotten.
    by["approval"].sort(key=lambda x: x.get("_ts", 0))
    return by


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def content_calendar(root):
    """Scheduled GBP content by date. Reads clients/*/content/gbp_calendar/*.json (rich: text +
    cluster) and cross-checks the approval store for each post's status; also picks up manually
    created dated GBP posts straight from the approval store. Returns date-sorted entries:
        {date, client, kind, title, preview, status, cta}   status: scheduled|posted|draft"""
    root = pathlib.Path(root)
    entries, seen = [], set()

    def _status(client, scope, date):
        appr = root / "clients" / client / "rpa" / "approvals"
        art = f"{scope}__gbp_post_publish__{date}.json"
        if (appr / "consumed" / art).exists(): return "posted"
        if (appr / "approved" / art).exists(): return "scheduled"
        return "draft"

    for cal in sorted(root.glob("clients/*/content/gbp_calendar/*.json")):
        client = cal.parts[cal.parts.index("clients") + 1]
        try: data = json.loads(cal.read_text())
        except Exception: continue
        scope = str(data.get("location_id", "")).replace("/", "_")
        for p in (data.get("posts") or []):
            d = p.get("date")
            if not d or (client, d) in seen: continue
            seen.add((client, d))
            entries.append({"date": d, "client": client, "kind": "GBP post",
                            "title": p.get("cluster", "post"), "preview": (p.get("text") or "")[:90],
                            "status": _status(client, scope, d), "cta": bool(p.get("cta"))})

    for state, st in (("approved", "scheduled"), ("consumed", "posted")):
        for p in sorted(root.glob(f"clients/*/rpa/approvals/{state}/*__gbp_post_publish__*.json")):
            client = p.parts[p.parts.index("clients") + 1]
            period = p.stem.split("__")[-1]
            if not _DATE.match(period) or (client, period) in seen: continue
            seen.add((client, period))
            entries.append({"date": period, "client": client, "kind": "GBP post",
                            "title": "manual post", "preview": "", "status": st, "cta": False})

    # --- generic content (articles, edge HTML, podcast, social) from the web + browser areas ---
    # dated by its period if that's a date, else by created/approved date; status from the store.
    for area in ("web", "browser"):
        for store, status in (("pending", "draft"), ("approved", "scheduled"), ("consumed", "posted")):
            for p in sorted(root.glob(f"clients/*/{area}/approvals/{store}/*.json")):
                if p.name == ".gitkeep" or p.name.endswith(".tmp"): continue
                client = p.parts[p.parts.index("clients") + 1]
                try: d = json.loads(p.read_text())
                except Exception: continue
                period = str(d.get("period") or "")
                date = period if _DATE.match(period) else (d.get("created") or d.get("approved") or "")[:10]
                if not _DATE.match(date or ""): continue
                scope = d.get("scope_id") or d.get("profile_id") or p.stem
                kind = d.get("kind") or d.get("workflow_id") or "content"
                k = (client, date, area, scope, kind, status)
                if k in seen: continue
                seen.add(k)
                title = (d.get("content") or {}).get("title") or d.get("workflow_id") or kind
                entries.append({"date": date, "client": client, "kind": kind, "title": title,
                                "preview": ((d.get("content") or {}).get("text") or "")[:90],
                                "status": status, "cta": False})

    entries.sort(key=lambda e: e["date"])
    return entries
