"""SERP feature taxonomy + lane-aware slot classifier with 5-class ownership
and AI citation capture. Shared across all clients.

Lanes (api_source) disambiguate AI surfaces: the AI Overview element appears in
BOTH the organic lane (AIO) and the ai_mode lane (AI Mode), so we relabel by lane,
not by item type (FIX #3)."""

# DataForSEO item type -> reported surface (organic/local_finder lanes)
FEATURE_MAP = {
    "local_pack": "local_pack",
    "local_finder": "local_finder",
    "featured_snippet": "featured_snippet",
    "answer_box": "featured_snippet",
    "organic": "organic",
    "organic_video": "organic_video",
    "video": "organic_video",
    "images": "images",
    "people_also_ask": "people_also_ask",
    "people_also_ask_element": "people_also_ask_element",
    "discussions_and_forums": "discussions_and_forums",
    "discussions_and_forums_element": "discussions_and_forums_element",
    "social_platform_result": "social_platform_result",
    "carousel": "carousel",
    "twitter": "social_platform_result",
    "ai_overview": "ai_overview",
}

_AGG = None
def _aggregators():
    """Agency-wide aggregator/directory domains from shared_schemas/aggregators.yaml (loaded once)."""
    global _AGG
    if _AGG is None:
        try:
            import pathlib, yaml
            p = pathlib.Path(__file__).resolve().parents[1] / "shared_schemas" / "aggregators.yaml"
            _AGG = [d.lower() for d in (yaml.safe_load(p.read_text()) or {}).get("aggregators", [])]
        except Exception:
            _AGG = []
    return _AGG


def _refs(item):
    out = []
    for ref in (item.get("references") or []):
        if isinstance(ref, dict):                       # live data: references may be strings
            d = ref.get("domain") or ref.get("url") or ""
        else:
            d = str(ref or "")
        if d: out.append(d.lower())
    return out

def _haystack(item):
    parts = [item.get("url") or "", item.get("domain") or ""]
    for el in (item.get("items") or []):                # live data: sub-items may be plain strings
        if isinstance(el, dict):
            parts += [el.get("url") or "", el.get("domain") or ""]
        elif isinstance(el, str):
            parts.append(el)
    parts += _refs(item)
    return " ".join(parts).lower()

def _classify_ownership(hay, assets, competitors, place_id, surface, aggregators):
    """First match wins, in priority order. Client asset tiers beat the aggregator list (so the
    client's OWN listing inside Yelp stays owned/controlled), which beats true competitors."""
    if place_id and surface in ("local_pack","local_finder") and place_id.lower() in hay:
        return "controlled"
    for tier in ("owned","controlled","influenced"):
        for tok in assets.get(tier, []):
            if tok and tok.lower() in hay:
                return tier
    for a in aggregators:
        if a and a in hay:
            return "aggregator"
    for c in competitors:
        if c and c.lower() in hay:
            return "competitor"
    return "unknown"

def classify(items, lane, assets, competitors, place_id=None, aggregators=None):
    """lane: 'local_finder' | 'organic_mobile' | 'ai_mode'.
    assets: {owned:[...], controlled:[...], influenced:[...]}.
    aggregators: directory domains (yelp/angi/...) -> ownership_class 'aggregator'; defaults to the
    agency-wide shared_schemas/aggregators.yaml list.
    Returns list of slot dicts (run-level fields added by the tracker)."""
    owned_all = [t.lower() for tier in ("owned","controlled") for t in assets.get(tier, [])]
    # citation honors ALL client tiers incl. influenced: a cited influenced asset is AI presence
    cited_tokens = owned_all + [t.lower() for t in assets.get("influenced", [])]
    comp = [c.lower() for c in competitors]
    agg = [a.lower() for a in (aggregators if aggregators is not None else _aggregators())]
    slots = []
    for it in items or []:
        itype = it.get("type")
        if not itype:
            continue                          # untyped item — we can't name the feature
        # GOAL (SERP saturation): track ALL features. Known item types normalize to a canonical
        # surface; every other DataForSEO item type passes through under its own name rather than
        # being silently dropped, so the saturation count sees the whole SERP.
        surface = FEATURE_MAP.get(itype, itype)
        # relabel AI surface by LANE, not by item type (FIX #3)
        if surface == "ai_overview":
            surface = "ai_mode_response" if lane == "ai_mode" else "ai_overview"
        hay = _haystack(it)
        # reddit/forum organic -> its own surface
        if surface == "organic" and "reddit." in hay:
            surface = "discussions_and_forums_element"
        oc = _classify_ownership(hay, assets, comp, place_id, surface, agg)
        refs = _refs(it)
        client_cited = bool(refs) and any(any(t in r for t in cited_tokens) for r in refs)
        cited_comp = [r for r in refs if any(c in r for c in comp)]
        # AI surfaces aren't "owned" by appearing — score them on CITATION instead.
        if surface in ("ai_overview", "ai_mode_response"):
            if client_cited:           oc = "influenced"
            elif cited_comp:           oc = "competitor"
            else:                      oc = "unknown"
        slot = {
            "feature_type": surface,
            "rank_absolute": it.get("rank_absolute"),
            "rank_group": it.get("rank_group"),
            "title": it.get("title"), "url": it.get("url"), "domain": it.get("domain"),
            "ownership_class": oc,
            "client_mentioned": any(t in hay for t in owned_all),
            "client_cited": client_cited,
            "cited_sources": refs,
            "cited_competitors": cited_comp,
        }
        slots.append(slot)
    return slots
