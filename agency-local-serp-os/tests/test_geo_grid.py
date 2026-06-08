"""Unit tests for programmatic geo-grid emulation (lib/geo_grid) — zero-cost local map-pack
dominance: build an NxN coordinate grid around the business, map local_finder rank_absolute onto
it, compute a localized Share of Local Voice. Deterministic; the DataForSEO calls live in a runner."""
from lib import geo_grid


def test_build_grid_dimensions_and_center():
    pts = geo_grid.build_grid(26.12, -80.14, size=3, step=0.01)
    assert len(pts) == 9
    center = [p for p in pts if p["row"] == 1 and p["col"] == 1][0]
    assert center["lat"] == 26.12 and center["lng"] == -80.14
    assert center["coordinate"].startswith("26.12,-80.14,")


def test_build_grid_offsets_north_top_west_left():
    pts = {(p["row"], p["col"]): p for p in geo_grid.build_grid(26.0, -80.0, size=3, step=0.01)}
    assert pts[(0, 1)]["lat"] > pts[(2, 1)]["lat"]      # row 0 is north (higher lat)
    assert pts[(1, 0)]["lng"] < pts[(1, 2)]["lng"]      # col 0 is west (lower lng)


def test_build_grid_from_coordinate_string():
    pts = geo_grid.build_grid_from_coordinate("26.12,-80.14,14", size=5, step=0.02)
    assert len(pts) == 25 and pts[0]["coordinate"].endswith(",14")   # zoom preserved


def test_solv_position_weighted():
    pts = [{"row": 0, "col": 0, "rank_absolute": 1},     # weight 1.0
           {"row": 0, "col": 1, "rank_absolute": 4},     # weight 0.35
           {"row": 1, "col": 0, "rank_absolute": None},  # absent -> 0
           {"row": 1, "col": 1, "rank_absolute": 2}]     # weight 0.6
    s = geo_grid.solv(pts)
    assert s["points_total"] == 4 and s["points_ranked"] == 3
    assert s["top3_points"] == 2                         # ranks 1 and 2
    assert s["solv"] == round((1.0 + 0.35 + 0.0 + 0.6) / 4, 4)
    assert s["avg_rank"] == round((1 + 4 + 2) / 3, 2)


def test_matrix_lays_ranks_on_grid():
    pts = [{"row": 0, "col": 0, "rank_absolute": 1}, {"row": 1, "col": 1, "rank_absolute": 5}]
    m = geo_grid.matrix(pts, size=2)
    assert m == [[1, None], [None, 5]]
