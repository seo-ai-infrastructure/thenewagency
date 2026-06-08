# Kanban board (live, localhost)

A projection of the filesystem (the SSOT). Scans the real work-order folders and every
client's approval store (rpa AND browser), and exposes gated actions wired to the real
machinery — not a parallel abstraction.

## Run
    python apps/kanban-board/server.py --host 127.0.0.1 --port 8787
    open http://127.0.0.1:8787      # browser polls /api/state every 3s

Stdlib only (http.server + pyyaml, already used by the runners). Localhost-bound, with a
Host-header guard (rejects non-localhost) because it can write files.

## Columns
NEEDS APPROVAL (pending drafts) · QUEUED (inbox WOs + approved artifacts) · IN PROGRESS
(working) · DONE · FAILED/HELD (reason from history).

## Actions (all on the REAL pipeline)
- **Approve / Reject** → lib.approvals (same hashed + scoped + expiring + single-use artifact
  the runners' verify_approval requires). The Approve button is the same gate as the CLI.
- **Add Work Order** → a TYPED work order (execution_method/workflow_id/profile|location/
  period/approval_ref) written atomically into the owning subsystem's inbox, so DuoPlus /
  Zernio / CloakBrowser actually pick it up. Workflow list + targets come from each client's
  real workflows.yaml / profiles.yaml / google_business.yaml.
- **Move** → bounded recovery only (inbox/working/done/failed), logged to history as
  "manual_override". Normal movement is still done by the runners as a result of execution.

## API
GET /api/state · GET /api/catalog · POST /api/approve · /api/reject · /api/create · /api/move
