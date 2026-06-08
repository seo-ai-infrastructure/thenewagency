#!/usr/bin/env python3
"""Three-lane mobile SERP feature tracker.  python run.py [--dry-run]"""
import sys, json, datetime, pathlib, yaml

def root(start):
    for d in [start, *start.parents]:
        if (d/"lib"/"serp_features.py").exists(): return d
    raise RuntimeError("repo root not found")

HERE = pathlib.Path(__file__).resolve().parent
ROOT = root(HERE); sys.path.insert(0, str(ROOT))
from lib.serp_features import classify
from lib import schema, log
from integrations.dataforseo import client as dfs   # noqa
LOG = log.get_logger("tracker")

_EP_DOC = yaml.safe_load((ROOT/"integrations"/"dataforseo"/"endpoints.yaml").read_text())
schema.validate(_EP_DOC, schema.ENDPOINTS)     # fail loud if a config key was renamed (FIX #7)
ENDPOINTS = _EP_DOC["apis"]
CFG   = yaml.safe_load((HERE/"config.template.yaml").read_text())
FACTS = ROOT/"clients"/CFG["client_id"]/"facts"
TERMS = yaml.safe_load((FACTS/"targeted-search-terms.yaml").read_text())
ASSETS = yaml.safe_load((FACTS/"owned-assets.yaml").read_text())
COMPS  = yaml.safe_load((FACTS/"competition.yaml").read_text())["competitors"]
LOCS   = yaml.safe_load((FACTS/"locations.yaml").read_text())

FIXTURE = {"local_finder":"dataforseo_local_finder_sample.json",
           "organic_mobile":"dataforseo_organic_house_ac_sample.json",
           "ai_mode":"dataforseo_ai_mode_sample.json"}

def terms_for(keyword_source):
    node = TERMS
    for k in keyword_source.split("."): node = node[k]
    return node

_AI_ABSENCE = {"feature_type": "ai_mode_response", "ownership_class": "unknown",
               "client_mentioned": False, "client_cited": False, "rank_absolute": None,
               "rank_group": None, "title": None, "url": None, "domain": None,
               "cited_sources": [], "cited_competitors": []}


def reclassify(run_id):
    """Re-run the classifier over an existing run's CACHED raw payloads — no API spend. Rewrites
    history/<run_id>.jsonl with the current classifier + owned-assets, so config/classifier fixes
    are reflected on the dashboard without re-billing DataForSEO. Raw payloads echo our `tag`
    (client|run|lane|term_id|loc_id|os) and `data.keyword`, making the mapping exact."""
    raw_dir = HERE / "raw" / run_id
    if not raw_dir.exists():
        sys.exit(f"no cached raw payloads for {run_id}")
    place_id = ASSETS.get("gbp_place_id")
    lane_api = {api["parse_as"]: name for name, api in ENDPOINTS.items()}
    lead_by_id = {}
    for src in (TERMS.get("rank_tracking") or {}).values():
        for t in (src or []):
            if isinstance(t, dict) and t.get("id"):
                lead_by_id[t["id"]] = t.get("lead_value", "unknown")
    loc_name = {l["id"]: l["name"] for l in LOCS["locations"]}
    out = HERE / "history" / f"{run_id}.jsonl"
    n = 0
    with out.open("w") as fh:
        for f in sorted(raw_dir.glob("*.json")):
            payload = json.loads(f.read_text(encoding="utf-8"))
            data = ((payload.get("tasks") or [{}])[0]).get("data") or {}
            parts = (data.get("tag") or "").split("|")
            if len(parts) != 6:
                continue
            _, _, lane, term_id, loc_id, os_type = parts
            items = dfs.extract_items(payload)
            ai_available = not (lane == "ai_mode" and not items)
            slots = classify(items, lane, ASSETS, COMPS, place_id) or ([_AI_ABSENCE] if lane == "ai_mode" else [])
            for s in slots:
                rec = {"schema_version": "3", "run_id": run_id, "client_id": CFG["client_id"],
                       "api_source": lane_api.get(lane, lane), "query_class": lane,
                       "keyword": data.get("keyword"), "keyword_id": term_id,
                       "lead_value": lead_by_id.get(term_id, "unknown"),
                       "location_name": loc_name.get(loc_id, loc_id), "device": CFG["device"],
                       "os": os_type, "ai_surface_available": ai_available, **s}
                schema.validate(rec, schema.SNAPSHOT)
                fh.write(json.dumps(rec) + "\n"); n += 1
    LOG.info(f"reclassified {run_id}: {n} records -> {out.name}", extra={"run_id": run_id, "n_records": n})
    print(f"reclassified {run_id}: {n} records -> history/{out.name}")


def main():
    if "--reclassify" in sys.argv:
        i = sys.argv.index("--reclassify")
        arg = sys.argv[i + 1] if i + 1 < len(sys.argv) else "latest"
        runs = sorted(p.name for p in (HERE / "raw").glob("mobile_serp_*") if p.is_dir())
        targets = runs if arg == "all" else (runs[-1:] if arg == "latest" else [arg])
        for t in targets:
            reclassify(t)
        return
    dry = "--dry-run" in sys.argv
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    run_id = "mobile_serp_" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = HERE/"history"/f"{run_id}.jsonl"; out.parent.mkdir(exist_ok=True)
    place_id = ASSETS.get("gbp_place_id")
    n = 0; costs = []
    with out.open("w") as fh:
        for api_name, api in ENDPOINTS.items():
            lane = api["parse_as"]                 # local_finder | organic_mobile | ai_mode
            for term in terms_for(api["keyword_source"]):
                for loc in LOCS["locations"]:
                    for os_type in LOCS["mobile_os"]:
                        if dry:
                            payload = json.loads((HERE/"fixtures"/FIXTURE[lane]).read_text())
                            items, meta = dfs.extract_items(payload), dfs.extract_meta(payload)
                        else:
                            task = {"keyword": term["keyword"], "location_code": loc["location_code"],
                                    "language_code":"en","device":CFG["device"],"os":os_type,
                                    **api.get("params",{}),
                                    "location_coordinate": loc.get(f"{lane}_coordinate"),
                                    "tag": f"{CFG['client_id']}|{run_id}|{lane}|{term['id']}|{loc['id']}|{os_type}"}
                            items, meta = dfs.call(api["endpoint"], task,
                                             raw_dir=str(HERE/"raw"/run_id),
                                             tag=f"{lane}_{term['id']}_{loc['id']}_{os_type}")
                        costs.append({"run_id":run_id,"api_source":api_name,"query_class":lane,
                                      "keyword":term["keyword"],"location_name":loc["name"],"os":os_type,
                                      "cost":meta.get("cost"),"task_cost":meta.get("task_cost"),
                                      "tasks_error":meta.get("tasks_error")})
                        ai_available = not (lane == "ai_mode" and not items)
                        slots = classify(items, lane, ASSETS, COMPS, place_id)
                        if not slots and lane == "ai_mode":         # record AI Mode absence (FIX #2)
                            slots = [{"feature_type":"ai_mode_response","ownership_class":"unknown",
                                      "client_mentioned":False,"client_cited":False,
                                      "rank_absolute":None,
                                      "rank_group":None,"title":None,"url":None,"domain":None,
                                      "cited_sources":[],"cited_competitors":[]}]
                        for s in slots:
                            rec = {"schema_version":"3","run_id":run_id,"client_id":CFG["client_id"],
                                   "api_source":api_name,"query_class":lane,
                                   "keyword":term["keyword"],"keyword_id":term["id"],
                                   "lead_value":term.get("lead_value","unknown"),
                                   "location_name":loc["name"],"device":CFG["device"],"os":os_type,
                                   "ai_surface_available":ai_available, **s}
                            schema.validate(rec, schema.SNAPSHOT)   # enforce v3 at write time
                            fh.write(json.dumps(rec)+"\n"); n += 1
    cdir = HERE/"costs"; cdir.mkdir(exist_ok=True)        # meter the bill (FIX #8 — AI Mode ~2x)
    with (cdir/f"{run_id}.jsonl").open("w") as cf:
        for c in costs: cf.write(json.dumps(c)+"\n")
    spent = sum(c["task_cost"] or 0 for c in costs)
    (HERE/"state").mkdir(exist_ok=True)
    (HERE/"state"/"last_run.json").write_text(json.dumps({       # machine-readable (#17)
        "run_id": run_id, "started_at": started,
        "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "n_records": n, "n_calls": len(costs), "cost": spent, "dry": dry}, indent=2))
    LOG.info(f"{'DRY ' if dry else ''}{run_id}: {n} records, {len(costs)} calls, ${spent:.4f} -> {out.name}",
             extra={"run_id": run_id, "n_records": n, "n_calls": len(costs), "cost": spent, "dry": dry})

if __name__ == "__main__":
    main()
