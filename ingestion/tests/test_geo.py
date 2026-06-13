"""Geometry helper tests: capacity buffers and wind-turbine clustering."""

from shapely import wkt
from shapely.geometry import Point

from ingestion import geo


def test_square_wkt_is_valid_multipolygon_around_point():
    g = wkt.loads(geo.square_wkt(11.5, 48.1, 300))
    assert g.geom_type == "MultiPolygon"
    cx, cy = g.centroid.x, g.centroid.y
    assert abs(cx - 11.5) < 1e-6
    assert abs(cy - 48.1) < 1e-6


def test_capacity_side_respects_minimum():
    # tiny capacity -> min side; large capacity -> area-based side
    assert geo.capacity_side_m(0.0, 1.4, 200.0) == 200.0
    big = geo.capacity_side_m(50.0, 1.4, 200.0)  # 50 MW * 1.4 ha = 70 ha = 700_000 m2
    assert abs(big - 836.66) < 1.0  # sqrt(700000)


def test_cluster_turbines_groups_near_and_splits_far():
    # two turbines ~300 m apart, one ~5 km away
    coords = [(11.500, 48.100), (11.504, 48.100), (11.600, 48.100)]
    clusters = geo.cluster_turbines(coords, merge_radius_m=400)
    sizes = sorted(len(c) for c in clusters)
    assert sizes == [1, 2]


def test_farm_wkt_contains_member_turbines():
    coords = [(11.500, 48.100), (11.503, 48.101), (11.502, 48.099)]
    g = wkt.loads(geo.farm_wkt(coords, pad_m=250))
    assert g.geom_type == "MultiPolygon"
    for lon, lat in coords:
        assert g.contains(Point(lon, lat))
