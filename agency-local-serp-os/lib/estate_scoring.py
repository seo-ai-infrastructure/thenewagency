"""SERP estate scoring. Three separate lane scores (never naively blended).
Within a lane, estate_share = ownership-weighted share of SERP slots the client holds,
weighted at the lane level by each keyword's lead_value.

Weights are env-overridable per-client (#14) so a PM can A/B them without a code edit:
  ESTATE_W_OWNED / _CONTROLLED / _INFLUENCED / _COMPETITOR / _UNKNOWN   (ownership class)
  ESTATE_LEAD_HIGH / _MEDIUM_HIGH / _MEDIUM / _LOW / _UNKNOWN           (lead value)
  ESTATE_MIN_SAMPLES   (below this, a lane is flagged low_confidence, #15)
This is shared (lib/), so changing the defaults below affects every client; prefer the env vars."""
import os
from collections import defaultdict


def _weights(defaults, prefix):
    return {k: float(os.environ.get(f"{prefix}{k.upper()}", v)) for k, v in defaults.items()}


OWNERSHIP_WEIGHT = _weights({"owned": 1.0, "controlled": 0.85, "influenced": 0.45,
                             "aggregator": 0.0, "competitor": 0.0, "unknown": 0.0}, "ESTATE_W_")
LEAD_WEIGHT = _weights({"high": 1.0, "medium_high": 0.7, "medium": 0.5, "low": 0.3,
                        "unknown": 0.5}, "ESTATE_LEAD_")
MIN_CONFIDENT_SAMPLES = int(os.environ.get("ESTATE_MIN_SAMPLES", "5"))


def estate_share(records):
    """For one (query, location, os): ownership-weighted slots / total slots."""
    n = len(records)
    if n == 0:
        return 0.0
    owned = sum(OWNERSHIP_WEIGHT.get(r["ownership_class"], 0.0) for r in records)
    return round(owned / n, 4)


def score_lane(records):
    """records all share one query_class. Returns lane score + per-query detail + a sample count
    (low_confidence when below MIN_CONFIDENT_SAMPLES so a 1-record lane isn't read like a 40-record one)."""
    groups = defaultdict(list)
    for r in records:
        groups[(r["keyword"], r["location_name"], r["os"])].append(r)
    detail, num, den = [], 0.0, 0.0
    for (kw, loc, os_), recs in groups.items():
        share = estate_share(recs)
        # lead_value is a property of the keyword, and keyword is in the group key, so it's the
        # same for every record in `recs` — recs[0] is safe (test pins this invariant). (#13)
        lw = LEAD_WEIGHT.get((recs[0].get("lead_value") or "unknown"), 0.5)
        comp = sum(1 for r in recs if r["ownership_class"] == "competitor")
        detail.append({"keyword": kw, "location": loc, "os": os_,
                       "estate_share": share, "lead_value": recs[0].get("lead_value"),
                       "competitor_slots": comp, "total_slots": len(recs),
                       "ai_available": any(r.get("ai_surface_available", True) for r in recs)})
        num += share * lw; den += lw
    return {"lane_score": round(num/den, 4) if den else 0.0,
            "samples": len(records), "low_confidence": len(records) < MIN_CONFIDENT_SAMPLES,
            "queries": detail}


def score_all(records):
    """Group by query_class -> one score per lane. No cross-lane blend."""
    lanes = defaultdict(list)
    for r in records:
        lanes[r["query_class"]].append(r)
    return {lane: score_lane(recs) for lane, recs in lanes.items()}


# ---- position-weighted Share of Voice (#SoV) ----
# PositionWeight scales inversely with absolute rank (pos 1 = 1.0, pos 5 = 0.3). A separate,
# named metric — does NOT replace estate_share (which is ownership-share, pinned by tests).
_PRESENT = ("owned", "controlled", "influenced")
POSITION_WEIGHT = {1: 1.0, 2: 0.6, 3: 0.45, 4: 0.35, 5: 0.3, 6: 0.25, 7: 0.2, 8: 0.16, 9: 0.13, 10: 0.1}


def position_weight(rank):
    if rank is None:
        return 0.0
    if rank in POSITION_WEIGHT:
        return POSITION_WEIGHT[rank]
    return 0.05 if rank > 10 else 0.0


def _sov_lane(records):
    """SoV = Σ(PositionWeight × LeadValue) over client-held slots / same over ALL ranked slots.
    Also splits the rest into competitor vs aggregator share so you can see WHO you lose to."""
    num = den = comp = agg = 0.0
    for r in records:
        rank = r.get("rank_absolute")
        if rank is None:                               # AI surfaces etc. have no slot rank
            continue
        w = position_weight(rank) * LEAD_WEIGHT.get(r.get("lead_value") or "unknown", 0.5)
        den += w
        oc = r.get("ownership_class")
        if oc in _PRESENT:
            num += w
        elif oc == "competitor":
            comp += w
        elif oc == "aggregator":
            agg += w
    return {"sov": round(num / den, 4) if den else 0.0,
            "competitor_share": round(comp / den, 4) if den else 0.0,
            "aggregator_share": round(agg / den, 4) if den else 0.0,
            "ranked_slots": sum(1 for r in records if r.get("rank_absolute") is not None)}


def sov_score(records):
    """One position-weighted SoV per lane. No cross-lane blend (same invariant as score_all)."""
    lanes = defaultdict(list)
    for r in records:
        lanes[r["query_class"]].append(r)
    return {lane: _sov_lane(recs) for lane, recs in lanes.items()}
