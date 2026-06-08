# The board (two flavors)

1) **Static snapshot** — `python scripts/board.py` writes `board/index.html`. Zero services;
   re-run (or cron/launchd) to refresh. Good for a quick glance / mobile.
2) **Live server** — `python apps/kanban-board/server.py` (localhost:8787). Polls every 3s and
   adds gated Approve/Reject, typed work-order creation, and bounded recovery moves.

Both read the same files via `lib/board_scan.py`; the approval gate is `lib/approvals.py`,
shared with `scripts/approve_draft.py`. Nothing the board does bypasses the gate: Approve
produces a hashed/scoped/expiring artifact, created work orders are the typed kind the runners
execute, and manual moves are logged as overrides. The filesystem stays the source of truth.

Localhost only by design. For shared/agency use, front it with VPN/SSO + HTTPS + per-user
audit logging (the server has no auth of its own).
