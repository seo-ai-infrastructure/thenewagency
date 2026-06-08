"""Programmatic geo-grid emulation — build your own local map-pack rank grid instead of paying a
geo-grid SaaS. Generate an NxN coordinate grid offset from the client's central business
coordinate (DataForSEO local_finder accepts an explicit location_coordinate "lat,lng,zoom"), run
one local_finder query per grid point in a runner, then map rank_absolute onto the grid and compute
a localized Share of Local Voice. Pure/deterministic here; the paid DataForSEO calls live in the
runner. Position weighting reuses lib.estate_scoring.position_weight (pos 1 = 1.0, decays with rank).
"""
from lib.estate_scoring import position_weight


def build_grid(center_lat, center_lng, size=3, step=0.01, zoom=14):
    """NxN grid centered on (center_lat, center_lng), offset by `step` degrees. row 0 = north
    (highest lat), col 0 = west (lowest lng). Each point carries a DataForSEO `coordinate` string."""
    half = (size - 1) / 2.0
    pts = []
    for r in range(size):
        for c in range(size):
            lat = round(center_lat + (half - r) * step, 6)   # north at the top row
            lng = round(center_lng + (c - half) * step, 6)
            pts.append({"row": r, "col": c, "lat": lat, "lng": lng,
                        "coordinate": f"{lat},{lng},{zoom}"})
    return pts


def build_grid_from_coordinate(coordinate, size=3, step=0.01):
    """Build a grid from a 'lat,lng[,zoom]' string (e.g. a locations.yaml *_coordinate)."""
    parts = str(coordinate).split(",")
    lat, lng = float(parts[0]), float(parts[1])
    zoom = int(float(parts[2])) if len(parts) > 2 and parts[2].strip() else 14
    return build_grid(lat, lng, size=size, step=step, zoom=zoom)


def solv(points):
    """Share of Local Voice over the grid. `points`: [{row,col,rank_absolute(None if absent)}].
    solv = position-weighted average across ALL grid points (absent points contribute 0)."""
    n = len(points) or 1
    weighted = sum(position_weight(p.get("rank_absolute")) for p in points)
    ranked = [p for p in points if p.get("rank_absolute") is not None]
    top3 = sum(1 for p in ranked if p["rank_absolute"] <= 3)
    avg = round(sum(p["rank_absolute"] for p in ranked) / len(ranked), 2) if ranked else None
    return {"solv": round(weighted / n, 4), "points_total": len(points),
            "points_ranked": len(ranked), "top3_points": top3, "avg_rank": avg}


def matrix(points, size):
    """2D grid (size x size) of rank_absolute (None where the client doesn't appear)."""
    m = [[None] * size for _ in range(size)]
    for p in points:
        if 0 <= p["row"] < size and 0 <= p["col"] < size:
            m[p["row"]][p["col"]] = p.get("rank_absolute")
    return m
