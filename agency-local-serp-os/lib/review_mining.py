"""Competitor review mining — deterministic, no LLM, public reviews only.

Parses an Outscraper Google-reviews export (a flat list of review rows), isolates negative
(1-3 star) reviews, and extracts recurring complaint THEMES via a curated lexicon. A competitor's
dominant weakness becomes a counter-positioning recommendation for the client (e.g. competitor X
is hammered for 'hidden fees' -> draft a 'transparent pricing, $0 hidden fees' hook). Output is a
human-gated rec_*.json (web/wordpress), like the other rec pipelines.

Scope: customer-review sentiment -> the client's OWN positioning copy. No employee/personal data,
no individual targeting, no automated outreach.
"""
import hashlib
import datetime

# complaint theme -> (substring patterns, counter-positioning hook for the CLIENT's own copy).
# Patterns are matched only against ALREADY-NEGATIVE (1-3 star) reviews, so broad terms are safe;
# tuned against real HVAC review language (service-call fees, defective installs, misdiagnosis...).
THEMES = {
    "hidden_fees": (["hidden fee", "service call", "more than quoted", "than quoted", "surprise charge",
                     "extra charge", "upcharge", "price went up", "added charge", "nickel and dime",
                     "fee to look", "fee to inspect", "additional $", "just to look", "diagnostic fee",
                     "service fee", "trip charge", "$100 service", "an $89 fee", "additional $150"],
                    "Transparent, upfront pricing — no hidden fees or surprise service-call charges."),
    "overpriced": (["overpriced", "over priced", "too expensive", "rip off", "ripoff", "price gou",
                    "gouging", "way too much", "highway robbery", "ridiculous", "greedy", "high end",
                    "expensive", "outrageous", "charged me", "cost a fortune", "which is ridiculous"],
                   "Fair, competitive pricing with free written estimates."),
    "no_show_late": (["no show", "no-show", "didn't show", "did not show", "never showed", "never came",
                      "waited all day", "missed appointment", "showed up late", "hours late",
                      "left me hanging", "didn't show up", "did not show up", "delay again",
                      "excuses delay", "reschedul", "a month later", "month later", "left hanging"],
                     "On-time service — appointment windows we actually keep."),
    "poor_workmanship": (["still broken", "didn't fix", "did not fix", "not fixed", "made it worse",
                          "had to call again", "came back out", "came back", "shoddy", "poor work",
                          "keeps breaking", "defective", "broke down", "broken down", "failed the install",
                          "failed the installation", "no air again", "no working ac", "without ac",
                          "without a/c", "no a/c", "incompetent", "numerous times", "something different",
                          "leaking", "still no ac", "broke again", "6 times", "broken down 6"],
                         "Workmanship guarantee — we fix it right the first time."),
    "unresponsive": (["never called back", "no call back", "no callback", "wouldn't answer", "no response",
                      "couldn't reach", "ignored my", "ghosted", "never returned", "no communication",
                      "no one even calls", "no one calls", "disinterested", "hard to reach",
                      "didn't call back", "unresponsive", "no one called", "hard to trust"],
                     "Responsive service — we answer and call back, every time."),
    "rude_unprofessional": (["rude", "unprofessional", "disrespect", "bad attitude", "argued with",
                             "yelled", "condescending", "annoyed", "short with", "their attitude"],
                            "Courteous, professional, respectful technicians."),
    "upsell_pressure": (["upsell", "up-sell", "pushy", "high pressure", "pressured me", "tried to sell",
                         "unnecessary repair", "didn't need", "did not need", "needs to be replaced",
                         "need to be replaced", "needed a new", "new system", "new compressor",
                         "purpose for these", "recommend", "wanted to replace", "sell you", "needs replaced"],
                        "Honest recommendations — no pressure, no unnecessary upsells or replacements."),
    "misdiagnosis": (["second opinion", "did nothing", "nothing wrong", "couldn't find anything",
                      "compressor was shot", "another company", "another ac company", "misdiagnos",
                      "wrong diagnosis", "just cleaned the drain", "but did nothing", "no refrigerant"],
                     "Accurate diagnostics you can trust — honest assessments, no phantom problems."),
    "warranty_issues": (["won't honor", "wouldn't honor", "void the warranty", "denied my claim",
                         "warranty was", "no warranty", "service contract", "had a service contract"],
                        "Honored warranties and service agreements we stand behind."),
}


def _rid(*parts):
    return "rec_" + hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:10]


def _slug(name):
    return "".join(c if c.isalnum() else "-" for c in (name or "").lower()).strip("-") or "competitor"


def _num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def normalize_outscraper(rows):
    """Flat Outscraper rows -> [{business, place_id, rating, text, date}] (skips empty text)."""
    out = []
    for r in rows:
        text = (r.get("review_text") or "").strip()
        if not text:
            continue
        out.append({"business": r.get("name"), "place_id": r.get("place_id") or r.get("google_id"),
                    "rating": _num(r.get("review_rating") if r.get("review_rating") is not None else r.get("rating")),
                    "text": text, "date": r.get("review_datetime_utc") or r.get("review_date")})
    return out


def negative_reviews(reviews, max_stars=3):
    return [r for r in reviews if r.get("rating") is not None and r["rating"] <= max_stars]


def extract_themes(text):
    """Complaint themes present in one review text (deterministic substring match)."""
    t = (text or "").lower()
    return [theme for theme, (pats, _) in THEMES.items() if any(p in t for p in pats)]


def competitor_pain_report(reviews, max_stars=3):
    """Per business: negative count, theme counts, sample quote per theme, avg rating of negatives."""
    rep = {}
    for r in negative_reviews(reviews, max_stars):
        b = r["business"]
        entry = rep.setdefault(b, {"business": b, "slug": _slug(b), "n_negative": 0,
                                   "themes": {}, "samples": {}, "_ratings": []})
        entry["n_negative"] += 1
        entry["_ratings"].append(r["rating"])
        for theme in extract_themes(r["text"]):
            entry["themes"][theme] = entry["themes"].get(theme, 0) + 1
            entry["samples"].setdefault(theme, [])
            if len(entry["samples"][theme]) < 3:
                entry["samples"][theme].append(r["text"][:240])
    for entry in rep.values():
        ratings = entry.pop("_ratings")
        entry["avg_rating"] = round(sum(ratings) / len(ratings), 2) if ratings else None
        entry["top_themes"] = sorted(entry["themes"], key=lambda k: -entry["themes"][k])
    return rep


def positioning_recs(report, client, min_mentions=2):
    """Each dominant competitor weakness -> a counter-positioning rec for the client (web/wordpress)."""
    out = []
    for business, entry in report.items():
        for theme in entry["top_themes"]:
            if entry["themes"][theme] < min_mentions:
                continue
            hook = THEMES[theme][1]
            out.append({
                "recommendation_id": _rid("review", client, entry["slug"], theme),
                "client_id": client, "area": "web", "subsystem": "wordpress-publisher",
                "status": "pending_human_review", "kind": "review_counter_positioning",
                "gap": {"competitor": business, "theme": theme,
                        "mentions": entry["themes"][theme], "counter_hook": hook,
                        "evidence": entry["samples"].get(theme, [])},
                "suggested_action": (
                    f"Review Counter-Positioning: '{business}' is repeatedly criticized for "
                    f"{theme.replace('_', ' ')} ({entry['themes'][theme]} negative reviews). Surface the "
                    f"counter-signal on the client's pages + FAQs: \"{hook}\" (also add to business_entity.md "
                    f"so AI engines match safety/intent queries to the client)."),
                "note": "Human reviews + approves the positioning copy before any publish work order issues.",
            })
    return out


def archive_raw(root, client, report, rows):
    """Persist the raw reviews per competitor to clients/<client>/raw/reviews/<slug>_customer.json."""
    import json, pathlib
    base = pathlib.Path(root) / "clients" / client / "raw" / "reviews"
    base.mkdir(parents=True, exist_ok=True)
    by_biz = {}
    for r in rows:
        by_biz.setdefault(r.get("name"), []).append(r)
    written = []
    for business, biz_rows in by_biz.items():
        out = base / f"{_slug(business)}_customer.json"
        out.write_text(json.dumps({"business": business, "captured_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(), "reviews": biz_rows}, indent=2), encoding="utf-8")
        written.append(out)
    return written
