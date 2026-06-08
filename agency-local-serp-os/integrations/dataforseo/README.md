# DataForSEO integration (shared)
Three lanes (local_finder / organic / ai_mode), declared in endpoints.yaml.
client.py does Live or Standard calls and archives raw responses to the tracker's raw/.
AI Mode: English-only, returns empty where AI Mode isn't available to users — handled
as absence, not error. Cost: AI Mode ~2x organic; paid params each multiply cost — see
the cadence/method fields in endpoints.yaml.
