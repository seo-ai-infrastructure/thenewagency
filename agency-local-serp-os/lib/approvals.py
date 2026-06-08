"""The approval gate — single source of truth for hashing/scope/expiry. Used by the CLI
(approve_draft.py), the board server, and the asset->post bridge. Producing an approval here
is the ONLY supported way to get a verify_approval-valid artifact."""
import json, hashlib, datetime, pathlib

def _area(root, client, area): return pathlib.Path(root)/"clients"/client/area

def _make(root, client, area, scope, workflow, period, payload, days=7, provenance=None):
    """Hash a content payload into a scoped, expiring, single-use approved artifact (atomic)."""
    h = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    now = datetime.datetime.now(datetime.timezone.utc)
    art = {"approval_id": "approval_"+now.strftime("%Y%m%dT%H%M%SZ"),
           "profile_id": scope, "workflow_id": workflow, "period": period, "status": "approved",
           "created": now.isoformat(), "expires_at": (now+datetime.timedelta(days=days)).isoformat(),
           "content": payload, "content_hash": h, "provenance": provenance or {}}
    out = _area(root, client, area)/"approvals"/"approved"/f"{scope}__{workflow}__{period}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp"); tmp.write_text(json.dumps(art, indent=2)); tmp.replace(out)
    return out, h

def list_pending(root, client, area):
    d = _area(root, client, area)/"approvals"/"pending"
    return sorted(p for p in d.glob("*draft.json")) if d.exists() else []

def _pending_path(base, scope, workflow, period=None):
    """A period-stamped draft (e.g. gen_gbp_posts --review writes scope__workflow__DATE__draft.json)
    takes precedence; otherwise the generic single draft."""
    pdir = base/"approvals"/"pending"
    if period:
        stamped = pdir/f"{scope}__{workflow}__{period}__draft.json"
        if stamped.exists(): return stamped
    return pdir/f"{scope}__{workflow}__draft.json"

def approve_draft(root, client, area, scope, workflow, period, days=7, edit=None):
    base = _area(root, client, area)
    pend = _pending_path(base, scope, workflow, period)
    if not pend.exists(): raise FileNotFoundError(f"no pending draft at {pend}")
    draft = json.loads(pend.read_text())
    co = draft.get("content", {})
    payload = dict(co)                      # preserve ALL content fields (title/body/slug/meta/...)
    if edit is not None:
        payload["text"] = edit             # a human text-edit overrides the primary body/text
    payload.setdefault("text", co.get("text", ""))
    out, h = _make(root, client, area, scope, workflow, period, payload, days,
                   provenance={**draft.get("provenance", {}), "approved_from_draft": draft.get("draft_id")})
    pend.unlink()
    return out, h

def write_approval(root, client, area, scope, workflow, period, content, days=7, provenance=None):
    """Emit an approval directly from a content dict (used by the asset->post bridge)."""
    return _make(root, client, area, scope, workflow, period, content, days, provenance)

def reject_draft(root, client, area, scope, workflow, reason="", period=None):
    base = _area(root, client, area)
    pend = _pending_path(base, scope, workflow, period)
    if not pend.exists(): raise FileNotFoundError(f"no pending draft at {pend}")
    d = json.loads(pend.read_text()); d["status"] = "rejected"; d["rejected_reason"] = reason
    d["rejected_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    dst = base/"approvals"/"rejected"/f"{scope}__{workflow}__draft.json"
    dst.parent.mkdir(parents=True, exist_ok=True); dst.write_text(json.dumps(d, indent=2)); pend.unlink()
    return dst
