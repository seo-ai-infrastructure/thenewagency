# zernio-publisher (API publishing — GBP + social). SEPARATE from DuoPlus RPA.

This subsystem posts through the Zernio API. It has NO phones, NO device locks, NO RPA.
It shares only the neutral safety library in lib/ (policy, approval gate, idempotency,
evidence, rate limiter) with the DuoPlus orchestrator — nothing else.

Processes only work orders whose workflow execution_method == google_business_api.
Dispatch by action_class: gbp_post_publish -> create_local_post (text + optional image +
location); gbp_photo_upload -> create_media; gbp_review_reply -> reply_to_review. Social
platforms use the same client (create_post / cross_post).

  python run.py [--dry-run] [--date YYYY-MM-DD] [--client <id>]

Work orders are placed here by scripts/gen_workorders.py (the shared scheduler).
