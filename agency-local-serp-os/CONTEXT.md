# CONTEXT

Every automation — including the DuoPlus RPA orchestrator — reads entity/NAP facts and
approved templates from `clients/<id>/facts/` (e.g. business_entity.md). Anything posted
on a phone is built upstream from facts/ for NAP consistency; the RPA layer only executes
pre-approved artifacts and never generates content on-device.

Layers: lib/ + integrations/ = shared code (libraries). clients/<id>/ = per-client data
(facts/, rpa/ config). automations/<name>/ = runners with the inbox/working/done/failed
skeleton. Coordination (locks, rate limit) is file-based by default, Redis when REDIS_HOST
is set — see docs/SETUP-REDIS.md and docs/CONFIG-GUIDE.md.
