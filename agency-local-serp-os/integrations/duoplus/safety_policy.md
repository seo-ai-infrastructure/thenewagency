# DuoPlus RPA safety policy (enforced in code by policy.py)
RPA is ONLY for authorized, client-owned, policy-compliant actions: mobile QA,
posting pre-approved client-owned content where no API exists, uploading approved media
to client-owned profiles, login-state checks, screenshot evidence, internal/client-owned
forms, first-party operational data.
BLOCKED (fail-closed): fake reviews, review gating, engagement manipulation, unsolicited
bulk messaging, fake account activity, captcha/verification bypass, ban evasion, scraping
private data behind login, any action on accounts the client does not own.
Customer-facing actions ALWAYS require a hashed, scoped, single-use, non-expired approval
artifact and a human sign-off. A global kill switch (policy.enabled=false) halts everything.
