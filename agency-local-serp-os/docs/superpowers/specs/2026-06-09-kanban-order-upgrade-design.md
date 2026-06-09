# Kanban Board & Manual Order Creation Upgrade — Design

**Date:** 2026-06-09
**Status:** Approved (design); implementation plan to follow
**Area:** `apps/kanban-board/`

## Goal

Make the live Kanban board best-in-class without breaking the core invariant: **the board is a
projection of the filesystem (the SSOT), and approvals are cryptographically gated.** Add
drag-and-drop, a rich order-editor modal, and a second swimlane board for "Fractional Employees"
(CloakBrowser / social personas). Keep it clean (Jira-style) — explicitly *not* a heavy
Businessmap/Gantt clone.

## Context (current system)

- `apps/kanban-board/server.py` — stdlib-only, localhost-only HTTP server. Scans real work-order
  folders (`automations/<dir>/{inbox,working,done,failed}`) and approval stores
  (`clients/*/{rpa,browser,web}/approvals/{pending,approved}`) via `lib/board_scan.py`.
- Columns (`board_scan.COLS`): NEEDS APPROVAL → QUEUED → IN PROGRESS → DONE → FAILED/HELD.
- "Move" today (`/api/move` → `move_wo`) is **bounded recovery only**, logged as `manual_override`.
- Order creation: 2-tab modal — "Create content" (`/api/create_content`, runs a creator → draft)
  and "Queue work order" (`/api/create` → typed WO into a runner inbox).
- Front-end: `static/app.js` (board render + modal + view-switch), `static/index.html`,
  `static/styles.css`. Cards act via `prompt()`/`alert()`. No drag-drop.
- Subsystems: DuoPlus (RPA/mobile), Zernio (GBP), CloakBrowser (browser identities),
  WordPress, Edge, Podcast.
- Vendored client libs already served from `static/vendor/` (leaflet, apexcharts) via fixed,
  no-traversal paths.

## Approved decisions

1. **Drag behavior:** *Safe moves + reorder.* Drag `wo` cards between
   QUEUED/IN PROGRESS/DONE/FAILED = today's bounded recovery move (logged `manual_override`).
   Reorder within QUEUED persists `order_index`. Approval/approved cards are **not** draggable;
   Approve/Reject stay explicit actions. The signed-approval gate is never bypassed by a drag.
2. **Fractional Employees board:** *One swimlane (row) per identity/persona.* Roster from
   `clients/*/browser/profiles.yaml`; browser/cloakbrowser work bucketed by `profile_id`.
3. **Order-editor modal:** *Full editor, attachments via links.* Editable WO JSON (inbox only),
   run history, logs, and attachments as `{label, url}` references. No upload store.

## Approach & tech

- **Sortable.js**, vendored into `static/vendor/sortable/Sortable.min.js`, served like existing
  vendor assets (fixed path, no traversal). Chosen over native HTML5 DnD for touch support,
  drop-placeholders, and cross-list drag with far less code. No build step.
- **Light refactor:** split `static/app.js` into:
  - `app.js` — view-switch shell + bootstrap only.
  - `board.js` — main board render + drag wiring.
  - `order-modal.js` — the rich order-editor modal (open/render/save/approve/reject/attach).
  - `fractional.js` — swimlane board render + drag wiring.
  - Shared helpers (`apiCall`, `esc`, `cardHTML`) move to `board-common.js`.
  Loaded as plain `<script>` tags in order (no bundler), matching current setup.

## Components & data flow

### Drag-and-drop (main board)
- Each column `.cards` is a Sortable list (`group:"board"`).
- Card DOM carries `data-kind`, `data-automation`, `data-filename`, `data-col`.
- `onEnd`:
  - `wo` card moved to a different column → `POST /api/move` with column→folder map
    (`queued→inbox, progress→working, done→done, held→failed`). Reuses existing `move_wo`.
  - `wo` cards reordered within QUEUED (same column) → `POST /api/reorder` with the ordered list
    of inbox filenames for that automation; server rewrites `order_index` 0..N on those files.
  - Other in-column reorders → visual only (no write).
- `draggable:false` on `draft`, `recommendation`, and `approved` cards.
- Optimistic move with rollback on POST failure; the 3s poll reconciles ground truth.

### Order-editor modal
- Click a card (anywhere on its surface) opens a slide-over modal.
- `GET /api/wo?automation=<dir>&filename=<wo>.json` → `{wo, history, logs, attachments}`.
  Path-safe: `filename` must equal its basename and end `.json`; `automation` must be a known
  `INBOX_DIR` value (mirrors `move_wo` guards). Searches `inbox/working/done/failed` for the file.
  - `history`: lines from `automations/<dir>/history/runs.jsonl` filtered to this `work_order_id`.
  - `logs`: the runner report/log text for this WO if present (best-effort; empty if none).
  - `attachments`: `wo.get("attachments", [])`.
- Sections:
  - **Overview** — full WO JSON. Editable only when the card is in `inbox`; Save →
    `POST /api/wo/save {automation, filename, wo}`. Server: JSON parse, re-validate required fields
    (`execution_method`, `client_id`, `workflow_id`, `work_order_id`), reject any `work_order_id`
    or derived path containing separators, atomic write (`.tmp` + replace). Non-inbox = read-only.
  - **History** — vertical timeline from the `history` payload.
  - **Logs** — monospace, scrollable; from the `logs` payload.
  - **Attachments** — list of `{label, url}`; "Add link" → `POST /api/wo/attach
    {automation, filename, label, url}` appends to `wo["attachments"]` (atomic write). Links open
    in a new tab; no upload.
  - **Draft cards** — instead of `prompt()`, an inline Approve pane (edit textarea → `/api/approve`)
    and Reject pane (reason → `/api/reject`).

### Fractional Employees board
- New top-nav tab "Fractional Employees" (`view-fractional`), peer to "Kanban Board".
- `GET /api/fractional?client=<id?>` →
  `{generated, identities:[{profile_id, client, label, columns:{queued,progress,done,held:[cards]}}]}`.
  - Roster: every persona in `clients/*/browser/profiles.yaml`.
  - Cards: browser/cloakbrowser WOs (and browser-area drafts) grouped by `profile_id`.
  - Personas with no current work still render (empty lanes) so the roster is visible.
- Layout: columns across the top; one row per persona with an initials chip + name header and the
  persona's cards per column. Same drag rules as the main board.
- v1 scope: `browser/profiles.yaml` only. RPA phone-profiles are a documented follow-on.

### Card upgrade (Jira-style)
- Keep system tag + client + existing accent colors.
- Add: persona/profile chip (generated initials), age pill, `·man` manual marker, whole-card click
  to open the modal.
- No avatars-from-disk in v1.

## New / changed HTTP endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/wo` | WO detail: `{wo, history, logs, attachments}` (path-safe) |
| POST | `/api/wo/save` | Overwrite an **inbox** WO JSON (validated, atomic, traversal-proof) |
| POST | `/api/wo/attach` | Append `{label,url}` to `wo["attachments"]` (atomic) |
| POST | `/api/reorder` | Rewrite `order_index` on an automation's inbox WOs |
| GET  | `/api/fractional` | Swimlane data grouped by browser persona |
| GET  | `/vendor/sortable/Sortable.min.js` | Serve vendored Sortable.js (fixed path) |

Reused unchanged: `/api/move`, `/api/approve`, `/api/reject`, `/api/create`, `/api/create_content`,
`/api/state`, `/api/catalog`, `/api/tasks`.

## Security

- Every new endpoint inherits `_guard` (localhost-only) and, for POSTs, `_csrf_ok`.
- File-touching endpoints reuse `move_wo`'s guards: `automation ∈ INBOX_DIR.values()`,
  `filename == basename(filename)` and endswith `.json`, no path separators.
- `/api/wo/save` additionally re-validates the WO body and refuses a `work_order_id` that would
  change the on-disk path or contains separators. Edits are only accepted for files currently in
  `inbox` (gated/in-flight WOs are read-only).
- Reorder only writes the integer `order_index` field; it never relocates files.

## Testing

- `tests/test_board_server.py` (extend): `/api/reorder` writes sequential `order_index`;
  `/api/wo` assembles detail + rejects traversal/unknown automation; `/api/wo/save` validates and
  rejects path-changing edits; `/api/wo/attach` appends; `/api/fractional` grouping shape.
- `tests/test_board_scan.py` (extend if scan helpers are added for fractional grouping).
- Front-end: manual verification via the running server (drag move, reorder, modal save, approve
  inline, swimlane render). No JS test harness exists; not adding one in v1.

## Out of scope (v1)

Timeline/Gantt, file uploads, WIP limits, cross-board card moves, multi-board stacking, avatars
from disk, RPA personas on the Fractional board.
