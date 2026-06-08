"""Nextdoor community-recommendation mining — deterministic, no LLM.

Community threads are pure word-of-mouth. This measures Share of Recommendation (who neighbors
praise vs criticize, sentence-level so one block can credit one company and fault another) and the
attributes buyers explicitly demand (honest/affordable/family-owned/licensed/"fix first"). Both feed
human-gated positioning recs (web/wordpress). Public posts only; no personal targeting.
"""
import re
import hashlib

POSITIVE = ["highly recommend", "recommend", "honest", "reliable", "dependable", "affordable",
            "reasonable", "family owned", "family-owned", "great job", "great", "the best",
            "best in town", "fair price", "fair", "trustworthy", "trust worthy", "excellent",
            "very happy", "happy", "professional", "amazing", "saved me", "stand behind", "upfront",
            "love them", "good company", "very good"]
NEGATIVE = ["sucks", "ripped me off", "rip off", "ripped off", "high cost", "high costs", "high price",
            "high repair", "awful", "stay away", "steer clear", "red flag", "don't stand behind",
            "dont stand behind", "doesn't stand behind", "overpriced", "pushy", "price gouging",
            "gouging", "scheme", "not disclosed", "undisclosed", "poorly", "screwed up", "screw",
            "disappointed", "blamed", "scam", "expensive", "charge to tell", "problems", "shocked"]
DESIRED = ["honest", "reasonable", "affordable", "family owned", "family-owned", "licensed",
           "insured", "trustworthy", "reliable", "fair", "reputable", "dependable", "professional",
           "fix first", "upfront"]


def _rid(*parts):
    return "rec_" + hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:10]


def _sentences(text):
    return [s.strip() for s in re.split(r"[.!?\n]+", text or "") if s.strip()]


def _blocks(text):
    return [b.strip() for b in re.split(r"\n\s*\n", text or "") if b.strip()]


def classify_sentiment(sentence):
    t = (sentence or "").lower()
    p = sum(t.count(w) for w in POSITIVE)
    n = sum(t.count(w) for w in NEGATIVE)
    return "positive" if p > n else "negative" if n > p else "neutral"


def analyze(text, companies):
    """Share of Recommendation + demanded attributes for a known company list. A block (one post)
    that names a single company is scored whole (praise often sits in a different sentence than the
    name); a block naming several is scored per-company from the sentences that mention each."""
    comps = [(c, c.lower()) for c in companies]
    sor = {c: {"positive": 0, "negative": 0, "neutral": 0, "total": 0} for c in companies}
    mentions = []

    def _credit(company, sentiment, snippet):
        sor[company][sentiment] += 1
        sor[company]["total"] += 1
        mentions.append({"company": company, "sentiment": sentiment, "snippet": snippet[:200]})

    for block in _blocks(text):
        bl = block.lower()
        present = [(c, cl) for c, cl in comps if cl in bl]
        if not present:
            continue
        if len(present) == 1:
            c, _ = present[0]
            _credit(c, classify_sentiment(block), block)
        else:
            for c, cl in present:
                hits = [s for s in _sentences(block) if cl in s.lower()]
                joined = " ".join(hits) or block
                _credit(c, classify_sentiment(joined), joined)
    tl = (text or "").lower()
    desired = {a: tl.count(a) for a in DESIRED if tl.count(a) > 0}
    sor = {c: v for c, v in sor.items() if v["total"] > 0}
    return {"share_of_recommendation": sor, "desired_attributes": desired,
            "mentions": mentions, "n_mentions": len(mentions)}


def nextdoor_recs(analysis, client, min_attr=2, min_neg=1):
    """Positioning recs from demanded attributes + competitor-signal recs from negative word-of-mouth."""
    out = []
    for attr, cnt in sorted(analysis["desired_attributes"].items(), key=lambda x: -x[1]):
        if cnt < min_attr:
            continue
        out.append({
            "recommendation_id": _rid("ndattr", client, attr),
            "client_id": client, "area": "web", "subsystem": "wordpress-publisher",
            "status": "pending_human_review", "kind": "nextdoor_positioning",
            "gap": {"attribute": attr, "mentions": cnt},
            "suggested_action": (f"Nextdoor neighbors repeatedly demand '{attr}' ({cnt}x) when choosing "
                                 f"an AC company. Make '{attr}' an explicit headline signal on the site, "
                                 f"GBP, and business_entity.md so the client matches community + AI intent."),
            "note": "Human reviews + approves positioning copy before any publish work order issues.",
        })
    for c, v in analysis["share_of_recommendation"].items():
        if v["negative"] >= min_neg and v["negative"] >= v["positive"]:
            out.append({
                "recommendation_id": _rid("ndcomp", client, c),
                "client_id": client, "area": "web", "subsystem": "wordpress-publisher",
                "status": "pending_human_review", "kind": "nextdoor_competitor_signal",
                "gap": {"competitor": c, "negative": v["negative"], "positive": v["positive"]},
                "suggested_action": (f"'{c}' draws negative community word-of-mouth ({v['negative']} "
                                     f"negative mentions). Position the client as the trustworthy "
                                     f"alternative and target their switchers."),
                "note": "Human reviews before any publish work order issues.",
            })
    return out
