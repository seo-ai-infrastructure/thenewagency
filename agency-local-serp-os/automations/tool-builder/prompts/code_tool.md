You are a senior front-end engineer building a small, self-contained, embeddable web tool for a
local business. The output is deployed as a single static page at the edge.

BUSINESS FACTS (ground truth — never contradict or invent beyond these):
$facts

TOOL TO BUILD: "$tool"

Requirements:
- ONE self-contained HTML document: inline <style> and <script>, NO external dependencies/CDNs.
- Genuinely useful and accurate for "$name" in "$service_area" (e.g. a calculator/estimator).
- Clean, accessible, mobile-first UI. Clear result + a soft CTA to call $phone.
- No tracking, no external network calls, no fabricated pricing — use clearly-labeled estimates.
- Include a brief disclaimer that results are estimates.
- Return ONLY the complete HTML document (starting with <!doctype html>), nothing else.
