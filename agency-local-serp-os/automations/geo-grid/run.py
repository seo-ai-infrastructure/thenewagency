#!/usr/bin/env python3
"""Programmatic geo-grid emulation (Local Falcon-style, no SaaS).

Runs one DataForSEO local_finder query per point of an NxN grid around the client's business
coordinate, for one or more keywords, maps the client's local rank onto each grid, and computes a
localized Share of Local Voice per keyword. Real PAID pulls: size*size calls per keyword
(5x5 = 25 ~ $0.05-0.08). Results MERGE into clients/<id>/signals/geo_grid.json keyed by keyword,
so the Search Intelligence map can filter per keyword via a dropdown.

  python run.py [--client ...] [--keyword "ac servicing near me"]   # one keyword (default: first)
  python run.py [--client ...] --all                                 # every local_finder keyword
"""
import sys, json, re, datetime, pathlib, yaml
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]; sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()
from lib import geo_grid
from integrations.dataforseo import client as dfs

ENDPOINT = "https://api.dataforseo.com/v3/serp/google/local_finder/live/advanced"


def _rank_at(items, place_id, domain):
    pid, dom = (place_id or "").lower(), (domain or "").lower()
    for it in items or []:
        if not isinstance(it, dict):
            continue
        hay = json.dumps(it).lower()
        if (pid and pid in hay) or (dom and dom in hay):
            return it.get("rank_absolute") or it.get("rank_group")
    return None


def _grid_for(kw, loc, place_id, domain, size, step, run_id):
    slug = re.sub(r"[^a-z0-9]+", "-", kw.lower()).strip("-")
    pts = []
    for p in geo_grid.build_grid_from_coordinate(loc["local_finder_coordinate"], size=size, step=step):
        task = {"keyword": kw, "location_code": loc["location_code"], "language_code": "en",
                "device": "mobile", "os": "android", "depth": 20, "location_coordinate": p["coordinate"]}
        try:
            items, _ = dfs.call(ENDPOINT, task, raw_dir=str(HERE / "raw" / run_id), tag=f"{slug}_{p['row']}_{p['col']}")
            rank = _rank_at(items, place_id, domain)
        except Exception as e:
            print(f"  [skip] {slug} ({p['row']},{p['col']}): {type(e).__name__}: {str(e)[:90]}")
            rank = None
        pts.append({"row": p["row"], "col": p["col"], "lat": p["lat"], "lng": p["lng"], "rank_absolute": rank})
        print(f"  {slug} ({p['row']},{p['col']}) rank={rank}")
    return {"keyword": kw, "size": size, "step": step, "points": pts,
            "matrix": geo_grid.matrix(pts, size), "solv": geo_grid.solv(pts)}


def _load_existing_grids(out_p):
    """Existing keyword->grid map, migrating the older single-keyword file shape if present."""
    if not out_p.exists():
        return {}
    doc = json.loads(out_p.read_text())
    if doc.get("grids"):
        return doc["grids"]
    if doc.get("keyword"):
        return {doc["keyword"]: {k: doc.get(k) for k in ("keyword", "size", "step", "points", "matrix", "solv")}}
    return {}


def main():
    a = sys.argv
    client = a[a.index("--client") + 1] if "--client" in a else "example-hvac-client"
    size = int(a[a.index("--size") + 1]) if "--size" in a else 5
    step = float(a[a.index("--step") + 1]) if "--step" in a else 0.012
    facts = ROOT / "clients" / client / "facts"
    terms = yaml.safe_load((facts / "targeted-search-terms.yaml").read_text())
    all_kws = [t["keyword"] for t in terms["rank_tracking"]["local_finder_terms"]]
    if "--all" in a:
        kws = all_kws
    elif "--keyword" in a:
        kws = [a[a.index("--keyword") + 1]]
    else:
        kws = [all_kws[0]]
    loc = yaml.safe_load((facts / "locations.yaml").read_text())["locations"][0]
    assets = yaml.safe_load((facts / "owned-assets.yaml").read_text())
    place_id, domain = assets.get("gbp_place_id"), (assets.get("owned") or [None])[0]

    out_p = ROOT / "clients" / client / "signals" / "geo_grid.json"
    grids = _load_existing_grids(out_p)
    run_id = "geo_" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for kw in kws:
        grids[kw] = _grid_for(kw, loc, place_id, domain, size, step, run_id)
        print(f"  -> {kw}: SoLV {grids[kw]['solv']['solv']}")

    out = {"client": client, "location": loc["name"], "center": loc["local_finder_coordinate"],
           "pulled": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "keywords": sorted(grids), "grids": grids}
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(out, indent=2))
    print(f"[geo-grid] {client}: {len(kws)} keyword(s) this run, {len(grids)} total "
          f"-> clients/{client}/signals/geo_grid.json")


if __name__ == "__main__":
    main()
