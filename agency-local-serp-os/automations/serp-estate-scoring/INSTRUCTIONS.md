# serp-estate-scoring
Reads the latest tracker history and produces THREE separate lane scores
(local_finder / organic_mobile / ai_mode) — never a naive blend. Within a lane,
estate_share = ownership-weighted share of SERP slots, weighted by
the keyword's lead_value. Output: history/<run_id>.jsonl with lane scores + per-query
detail (including competitor_share and ai_available).
