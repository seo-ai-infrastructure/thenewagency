"""PAA Velocity Trap ΓÇö deterministic, no LLM.

The organic_mobile lane already captures People-Also-Ask elements. This compares the PAA questions
in the latest tracker run against prior runs (the caller passes the runs inside the desired window,
e.g. last 30 days) to catch:
  - NEW questions (a question that wasn't in any prior run) -> emerging intent
  - RISERS (a question that climbed the PAA box, e.g. #4 -> #1) -> intensifying intent
and emits a human-gated PAA-hijack Q&A recommendation (web/wordpress) so you capture the volume
before competitors. Output is a rec_*.json (via aeo_recs.write_recs); the `content` field carries a
Q&A markdown scaffold for the content generator.

A "position" is the question's slot within the PAA accordion (rank_group, falling back to rank_absolute).
"""
import hashlib

PAA_FEATURES = ("people_also_ask", "people_also_ask_element")


def _rid(*parts):
    return "rec_" + hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:10]


def paa_questions(records):
    """Extract PAA questions from a run's records: [{keyword, question, position}] (skips blanks)."""
    out = []
    for r in records:
        if r.get("feature_type") in PAA_FEATURES:
            q = (r.get("title") or "").strip()
            if q:
                out.append({"keyword": r.get("keyword"), "question": q,
                            "position": r.get("rank_group") or r.get("rank_absolute")})
    return out


def detect_velocity(runs, jump_threshold=2):
    """runs: ordered (oldest -> newest) list of (run_id, records). Returns velocity events for the
    LATEST run vs the prior runs (the window). A riser must improve by >= jump_threshold positions."""
    if not runs:
        return []
    _, latest_recs = runs[-1]
    seen, best_prior = set(), {}
    for _, recs in runs[:-1]:
        for q in paa_questions(recs):
            key = (q["keyword"], q["question"].lower())
            seen.add(key)
            if q["position"] is not None:
                best_prior[key] = min(best_prior.get(key, 10 ** 9), q["position"])
    events, emitted = [], set()
    for q in paa_questions(latest_recs):
        key = (q["keyword"], q["question"].lower())
        if key in emitted:
            continue
        if key not in seen:
            emitted.add(key)
            events.append({"keyword": q["keyword"], "question": q["question"], "kind": "new",
                           "from_position": None, "to_position": q["position"]})
        else:
            prev, cur = best_prior.get(key), q["position"]
            if prev is not None and cur is not None and (prev - cur) >= jump_threshold:
                emitted.add(key)
                events.append({"keyword": q["keyword"], "question": q["question"], "kind": "riser",
                               "from_position": prev, "to_position": cur})
    events.sort(key=lambda e: (e["kind"] != "new", e.get("to_position") or 999))
    return events


def velocity_recs(events, client):
    """One PAA-hijack rec per velocity event (web/wordpress), with a Q&A markdown scaffold."""
    out = []
    for e in events:
        qa_md = (f"## {e['question']}\n\n"
                 f"*Lead with the direct answer in 40-60 words, then 1-2 supporting sentences. "
                 f"Mark up as FAQPage schema.*\n")
        label = "new question" if e["kind"] == "new" else f"riser #{e.get('from_position')}->#{e.get('to_position')}"
        out.append({
            "recommendation_id": _rid("paa", client, e["keyword"], e["question"].lower()),
            "client_id": client, "area": "web", "subsystem": "wordpress-publisher",
            "status": "pending_human_review", "kind": "paa_hijack",
            "gap": {"keyword": e["keyword"], "question": e["question"], "velocity": e["kind"],
                    "from_position": e.get("from_position"), "to_position": e.get("to_position")},
            "suggested_action": (f"PAA Velocity ({label}): the question \"{e['question']}\" is surging "
                                 f"for '{e['keyword']}'. Add an optimized Q&A block (FAQPage schema) to "
                                 f"capture this intent before competitors."),
            "content": qa_md,
            "note": "Human reviews + supplies the final answer before any publish work order issues.",
        })
    return out
