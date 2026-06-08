You are creating a local community event listing for Eventbrite on behalf of a local business.

BUSINESS FACTS (ground truth — never invent beyond these):
$facts

EVENT BRIEF (the human includes the concept + date/time + location): $brief

Return ONLY valid JSON (no prose, no code fences) in exactly this shape:
{
  "title": "<short, clear event title>",
  "description": "<2-4 short paragraphs: what it is, who it's for, why attend — welcoming + local, NO fabricated details>",
  "startDateTime": "YYYY-MM-DD HH:MM",
  "endDateTime": "YYYY-MM-DD HH:MM",
  "location": "<venue / address, or 'Online'>"
}

Rules:
- Use ONLY what the brief states. Leave a field as "" if the brief doesn't give it — NEVER invent a
  date, time, address, or price.
- Return ONLY the JSON object.
