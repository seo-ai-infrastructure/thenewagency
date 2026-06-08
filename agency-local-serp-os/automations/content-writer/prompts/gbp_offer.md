You are creating a Google Business Profile OFFER post for a local business.

BUSINESS FACTS (ground truth — never invent beyond these):
$facts

OFFER BRIEF (the human includes the discount + terms here): $brief

Return ONLY valid JSON (no prose, no code fences) in exactly this shape:
{
  "text": "<GBP offer post copy, 150-500 chars, warm + local, NO fabricated phone/price/awards>",
  "offer": {
    "couponCode": "<code ONLY if the brief gives one, else omit this key>",
    "redeemOnlineUrl": "<url ONLY if the brief gives one, else omit>",
    "termsConditions": "<short terms taken from the brief>"
  }
}

Rules:
- Use ONLY what the brief states; OMIT any key you don't have. NEVER invent a coupon code,
  discount %, or terms. If the brief has no offer details, return just {"text": "..."}.
- Return ONLY the JSON object.
