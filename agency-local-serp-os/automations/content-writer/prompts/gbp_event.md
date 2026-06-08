You are creating a Google Business Profile EVENT post for a local business.

BUSINESS FACTS (ground truth — never invent beyond these):
$facts

EVENT BRIEF (the human includes the event name + dates here): $brief

Return ONLY valid JSON (no prose, no code fences) in exactly this shape:
{
  "text": "<GBP event post copy, 150-500 chars, warm + local, one soft CTA, NO fabricated phone/price/awards>",
  "event": {
    "title": "<short event title>",
    "schedule": {"startDate": "YYYY-MM-DD", "endDate": "YYYY-MM-DD"}
  }
}

Rules:
- Use ONLY dates the brief actually states. If the brief has no clear dates, OMIT the "event" key
  entirely and return just {"text": "..."} — NEVER invent dates.
- Return ONLY the JSON object.
