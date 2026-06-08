# agency-local-serp-os — three-lane mobile SERP estate tracker

Tracks how much of the buyer's MOBILE SERP a client owns/controls/influences across
three DataForSEO lanes, normalized into one schema and scored by ownership-weighted slot share.

## Lanes (integrations/dataforseo/endpoints.yaml)
- Local Finder  /v3/serp/google/local_finder/live/advanced   (map-pack)
- Organic mobile /v3/serp/google/organic/live/advanced        (full feature stack + AIO)
- AI Mode       /v3/serp/google/ai_mode/live/advanced         (English-only, ~2x cost, monthly)

## What was fixed/upgraded vs the prior spec
2. AI Mode absence handled (English-only / location-limited) — recorded, not errored.
3. AI Overview vs AI Mode disambiguated by LANE (both arrive as an ai_overview item).
4. Coordinate format standardized (lat,lng,zoom) across lanes.
5. competition.yaml (structured) drives the 5-class ownership classifier.
6. AI citations captured: cited_sources + cited_competitors (who's winning the AI surface).
7. Cost controls: per-lane cadence + Standard (queued) method in endpoints.yaml;
   AI Mode monthly; minimal paid params to control cost. Raw responses archived to raw/ so you never re-pay to re-parse.
8. Schedule-collector idempotency via state/last_run.txt (not inbox/work-order).
9. Scoring: THREE separate lane scores (never blended), estate_share = ownership-weighted
   share of SERP slots, weighted by ownership class AND keyword lead_value.
10. AI surfaces scored by CITATION (influenced), not block ownership — being cited
    among several sources is not owning the slot.

## Run
```bash
pip install -r requirements.txt
python run_all_dry.py            # tracker (fixtures) -> estate scoring, end to end
# live: set DATAFORSEO_LOGIN/PASSWORD in env, fill clients/<id>/facts, drop --dry-run
```

## Layout
```
lib/           serp_features.py (classifier), estate_scoring.py    (shared, imported)
integrations/dataforseo/  endpoints.yaml (lanes+cadence+cost), client.py (raw archive)
shared_schemas/serp_feature_snapshot.schema.json                  (v3, validated)
automations/local-mobile-serp-feature-tracker/  run.py, fixtures/, history/, raw/, state/
automations/serp-estate-scoring/                 run.py, history/
clients/<id>/facts/  targeted-search-terms.yaml (3-lane), owned-assets.yaml (tiers),
                     competition.yaml, locations.yaml
```

## Known tuning points (deliberately left to you)
- Ownership matching is substring-based on your asset tokens — tighten YouTube/Reddit
  tokens to exact channel/author URLs to avoid lookalike false positives.
- Estate weights (ownership class, lead_value) live in lib/estate_scoring.py — tune.
- gbp.py/gsc.py-style live calls need your keys; dry-run uses fixtures and calls no API.
