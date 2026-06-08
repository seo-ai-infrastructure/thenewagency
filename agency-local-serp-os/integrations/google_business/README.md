# integrations/google_business (shared) — GBP via Zernio

Google Business Profile posting/reviews/photos through Zernio's API
(https://docs.zernio.com/platforms/google-business). API-first, no phone needed —
this is why GBP workflows run with execution_method: google_business_api, not duoplus_rpa.

- Auth: Bearer token in env ZERNIO_API_KEY. Zernio owns the Google business.manage OAuth
  (done once when you connect the GBP account in Zernio); we reference the connected
  accountId (+ optional locationId).
- client.py: create_local_post, reply_to_review, create_media, get_locations (fake-able,
  rate-limited via the shared limiter).
- Per-client account/location ids live in clients/<id>/rpa/google_business.yaml.
- Limits: 1500 chars, 1 image (JPEG/PNG, <=5MB, >=400x300), no video, no Q&A.
- The orchestrator's gates (policy, human approval, idempotency, evidence, history) wrap
  these API calls exactly as they wrap DuoPlus RPA — only the execution method differs.
