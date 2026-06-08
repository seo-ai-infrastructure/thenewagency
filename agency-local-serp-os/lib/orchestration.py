"""Shared work-order machinery for any gated automation (DuoPlus RPA, Zernio publisher, ...).
Holds the parts that are identical across subsystems: claim, idempotency, policy + approval
gate, immutable hashed evidence, history. Subsystem-specific execution (phone vs API) stays
in each automation's run.py."""
import os, json, hashlib, datetime, pathlib
from lib import policy as pol
from lib import notify

def now_iso(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

class WorkOrderRunner:
    def __init__(self, here, root, rpa, policy, notify=False):
        self.here = pathlib.Path(here); self.root = pathlib.Path(root); self.rpa = pathlib.Path(rpa)
        self.policy = policy
        self.notify = notify
        self.HIST = self.here/"history"/"runs.jsonl"
        self.PROCESSED = self.here/"state"/"processed_ids.txt"

    def inbox(self):
        def order_index(p):                         # tolerate a file claimed mid-scan
            try: return json.loads(p.read_text()).get("order_index", 0)
            except (OSError, json.JSONDecodeError): return 0
        return sorted((self.here/"inbox").glob("wo_*.json"), key=order_index)

    def claim(self, wo_path):                       # exclusive inbox -> working
        dst = self.here/"working"/wo_path.name
        # Must FAIL if another worker already claimed this file. os.rename is exclusive on
        # Windows but SILENTLY REPLACES on POSIX, so use os.link (hardlink): it raises
        # FileExistsError if dst already exists on BOTH platforms. Then drop the inbox copy.
        try:
            os.link(wo_path, dst)
        except FileExistsError:
            return None                             # already claimed by another worker
        except FileNotFoundError:
            return None                             # already claimed + moved
        except OSError:
            # this filesystem doesn't support hardlinks -> os.rename (exclusive on Windows;
            # on such POSIX filesystems single-machine runs use one worker, or the Redis lock).
            try: os.rename(wo_path, dst); return dst
            except OSError: return None
        try: os.unlink(wo_path)
        except FileNotFoundError: pass
        return dst

    def requeue(self, working):
        os.replace(working, self.here/"inbox"/working.name)   # atomic, replaces on Windows too

    def processed(self, key):
        return self.PROCESSED.exists() and key in self.PROCESSED.read_text().splitlines()
    def mark_processed(self, key):
        self.PROCESSED.parent.mkdir(parents=True, exist_ok=True)
        with self.PROCESSED.open("a") as f: f.write(key+"\n")

    def evidence(self, wo, phase):                  # immutable, timestamped, hashed
        d = self.rpa/"logs"/wo["work_order_id"]; d.mkdir(parents=True, exist_ok=True)
        f = d/f"{wo['profile_id']}__{wo['workflow_id']}__{phase}.txt"
        try:
            fd = os.open(str(f), os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            os.write(fd, f"[evidence] {phase} {wo['workflow_id']} {wo['profile_id']} {now_iso()}\n".encode()); os.close(fd)
        except FileExistsError: pass
        return {"path": str(f.relative_to(self.root)), "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}

    def verify_approval(self, wo):
        ref = wo.get("approval_ref")
        if not ref: return False, "no approval_ref"
        p = pathlib.Path(ref)
        base = self.rpa/"approvals"/"approved"           # confine to THIS client's store
        try:
            if p.resolve().parent != base.resolve():
                return False, "approval_ref outside approvals store"
        except OSError:
            return False, "approval artifact missing"
        if not p.exists(): return False, "approval artifact missing"
        a = json.loads(p.read_text())
        if a.get("status") != "approved": return False, "artifact not approved"
        if (a["profile_id"], a["workflow_id"], a["period"]) != (wo["profile_id"], wo["workflow_id"], wo["period"]):
            return False, "approval scope mismatch"
        if datetime.datetime.fromisoformat(a["expires_at"]) < datetime.datetime.now(datetime.timezone.utc):
            return False, "approval expired"
        if hashlib.sha256(json.dumps(a["content"], sort_keys=True).encode()).hexdigest() != a["content_hash"]:
            return False, "content hash mismatch (tampered)"
        return True, p
    def consume_approval(self, p):
        dst = self.rpa/"approvals"/"consumed"/p.name; dst.parent.mkdir(parents=True, exist_ok=True); os.replace(p, dst)

    def finish(self, working, status, report):
        dst = self.here/("done" if status == "done" else "failed")/working.name; os.replace(working, dst)
        self.HIST.parent.mkdir(parents=True, exist_ok=True)
        with self.HIST.open("a") as f: f.write(json.dumps({"ts": now_iso(), "status": status, **report})+"\n")
        if status == "failed" and self.notify and report.get("stage") != "approval":
            wid = report.get("work_order_id", "?"); why = report.get("reason", "failed")
            notify.send(f"Failed: {report.get('workflow_id','?')} [{wid}] — {why}", level="error")

    def gate(self, wo, wf, working, rep, profile):
        """Idempotency + policy + approval. Returns (ok, key, approval_path)."""
        pid = wo["profile_id"]; key = f"{pid}|{wo['workflow_id']}|{wo['period']}"
        if self.processed(key):
            print(f"  {wo['work_order_id']}: already done this period — skip")
            self.finish(working, "done", {**rep, "note": "idempotent skip"}); return False, key, None
        ok, why = pol.check(wf, profile, self.policy)
        if not ok:
            print(f"  {wo['work_order_id']}: BLOCKED — {why}")
            self.finish(working, "failed", {**rep, "reason": why, "stage": "policy"}); return False, key, None
        approval_path = None
        needs = wo["customer_facing"] or wf.get("action_class") in self.policy.get("human_gate_action_classes", [])
        if needs:
            if not wo["customer_facing"]:
                print(f"  {wo['work_order_id']}: risk-tier auto-gate ({wf.get('action_class')} is public-posting)")
            ok, res = self.verify_approval(wo)
            if not ok:
                print(f"  {wo['work_order_id']}: HELD — {res}")
                self.finish(working, "failed", {**rep, "reason": res, "stage": "approval"}); return False, key, None
            approval_path = res
        return True, key, approval_path
