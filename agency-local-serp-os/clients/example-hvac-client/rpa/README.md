# clients/<id>/rpa — configuration (DATA, not an automation)

The orchestrator READS this folder; it deliberately has no run.py / inbox of its own.
Files: phones.yaml, profiles.yaml, workflows.yaml, schedules.yaml, policy.yaml,
approvals/ (pending|approved|rejected|consumed), logs/. The actual runner with the
inbox/working/done/failed skeleton is automations/duoplus-rpa-orchestrator/.
See docs/CONFIG-GUIDE.md for the fill-in-the-blanks setup.
