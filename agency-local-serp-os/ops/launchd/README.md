# launchd agents (Mac mini, always-on board + morning issuance)

Two jobs:
- **com.agency.serp.board** — keeps the Kanban server running on 127.0.0.1:8787 (RunAtLoad +
  KeepAlive, so it restarts on crash and at login).
- **com.agency.serp.genworkorders** — runs `scripts/issue_all.sh` at 07:00 daily, issuing
  today's work orders for every client that has schedules.

Both go through `run-wrapped.sh`, which loads `secrets.env` (a scheduled job won't see your
shell env otherwise) and fixes PATH for system/Homebrew python.

## Install
    bash ops/launchd/install.sh        # substitutes the repo path, copies to ~/Library/LaunchAgents, loads both

## Manage
    launchctl start com.agency.serp.genworkorders   # run the morning job now (test)
    launchctl list | grep com.agency.serp           # see status / last exit code
    tail -f ops/launchd/logs/board.err.log          # watch the board
    bash ops/launchd/install.sh remove              # unload + delete both

## Notes
- Change the time by editing StartCalendarInterval in the genworkorders template, then re-run install.
- Change the port in the board template (and your bookmark) if 8787 is taken.
- `launchctl load -w` works broadly; on recent macOS the modern form is
  `launchctl bootstrap gui/$(id -u) <plist>` / `bootout`.
- KeepAlive means the board stays up; to stop it, use `install.sh remove` (or `launchctl unload`).
