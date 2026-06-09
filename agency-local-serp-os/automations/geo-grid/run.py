#!/usr/bin/env python3
"""Programmatic geo-grid emulation (Local Falcon-style, no SaaS).

Runs one DataForSEO local_finder query per point of an NxN grid around the client's business
coordinate, maps the client's local rank onto the grid, and computes a localized Share of Local
Voice. Real PAID pulls: size*size calls for one keyword (5x5 = 25 ~ $0.05-0.08). Writes
clients/<id>/signals/geo_grid.json for the Search Intelligence tab.

  python run.py [--client example-hvac-client] [--keyword "ac servicing near me"] [--size 5] [--step 0.012]
"""
import sys, json, datetime, pathlib, yaml
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]; sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()
from lib import geo_grid
from integrations.dataforseo import client as dfs

ENDPOINT = "https://api.dataforseo.com/v3/serp/google/local_finder/live/advanced"


def _rank_at(items, place_id, domain):
    """First local result that is the client (by GBP place_id or owned domain) -> its rank."""
    pid, dom = (place_id or "").lower(), (domain or "").lower()
    for it in items or []:
        if not isinstance(it, dict):
            continue
        hay = json.dumps(it).lower()
        if (pid and pid in hay) or (dom and dom in hay):
            return it.get("rank_absolute") or it.get("rank_group")
    return None


def main():
    a = sys.argv
    client = a[a.index("--client") + 1] if "--client" in a else "example-hvac-client"
    size = int(a[a.index("--size") + 1]) if "--size" in a else 5
    step = float(a[a.index("--step") + 1]) if "--step" in a else 0.012
    facts = ROOT / "clients" / client / "facts"
    terms = yaml.safe_load((facts / "targeted-search-terms.yaml").read_text())
    kw = a[a.index("--keyword") + 1] if "--keyword" in a else terms["rank_tracking"]["local_finder_terms"][0]["keyword"]
    loc = yaml.safe_load((facts / "locations.yaml").read_text())["locations"][0]
    assets = yaml.safe_load((facts / "owned-assets.yaml").read_text())
    place_id, domain = assets.get("gbp_place_id"), (assets.get("owned") or [None])[0]

    grid = geo_grid.build_grid_from_coordinate(loc["local_finder_coordinate"], size=size, step=step)
    run_id = "geo_" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pts = []
    for p in grid:
        task = {"keyword": kw, "location_code": loc["location_code"], "language_code": "en",
                "device": "mobile", "os": "android", "depth": 20, "location_coordinate": p["coordinate"]}
        try:
            items, _ = dfs.call(ENDPOINT, task, raw_dir=str(HERE / "raw" / run_id), tag=f"{p['row']}_{p['col']}")
            rank = _rank_at(items, place_id, domain)
        except Exception as e:
            print(f"  [skip] ({p['row']},{p['col']}): {type(e).__name__}: {str(e)[:100]}")
            rank = None
        pts.append({"row": p["row"], "col": p["col"], "lat": p["lat"], "lng": p["lng"], "rank_absolute": rank})
        print(f"  ({p['row']},{p['col']}) rank={rank}")

    out = {"client": client, "keyword": kw, "size": size, "step": step,
           "center": loc["local_finder_coordinate"], "location": loc["name"],
           "pulled": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "points": pts, "matrix": geo_grid.matrix(pts, size), "solv": geo_grid.solv(pts)}
    out_p = ROOT / "clients" / client / "signals" / "geo_grid.json"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(out, indent=2))
    s = out["solv"]
    print(f"[geo-grid] {client} “{kw}” {size}x{size}: SoLV {s['solv']} · "
          f"ranked {s['points_ranked']}/{s['points_total']} · top3 {s['top3_points']} · avg {s['avg_rank']} "
          f"-> clients/{client}/signals/geo_grid.json")


if __name__ == "__main__":
    main()
