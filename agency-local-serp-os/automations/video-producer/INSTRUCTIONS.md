# video-producer (Tier-3 asset generation — drafts only, never publishes)

Takes a brief, then: (1) drafts an image prompt + a motion prompt from client facts via the
LLM gate, (2) generates a still with Nano Banana, (3) animates it to video with Veo
(image-to-video). The image + video land as a PENDING draft in the client's approvals/pending/
with the asset file paths recorded. A human reviews the actual files, then approve_draft.py
emits the hashed approval; only then may a publisher use the asset. The producer never posts.

  python run.py --client example-hvac-client --location "locations/REPLACE" \
      --brief "15s vertical reel: emergency AC repair in Fort Lauderdale, friendly tech at a door" \
      [--still-only] [--dry-run]

Live calls need GOOGLE_API_KEY (or GEMINI_API_KEY) and SPEND real money (Nano Banana ~$0.05-0.24/
image, Veo ~$0.15-0.40/sec). --dry-run (or no key) writes placeholder files for free. Assets are
written under clients/<id>/rpa/assets/<draft_id>/.
