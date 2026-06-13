"""OSM AOI-matching tests (pure geometry; no HTTP/zip)."""

from ingestion.sources.osm import OSMSource
from shapely import STRtree
from shapely.geometry import Point, box


def test_match_returns_containing_polygon():
    polys = [box(0, 0, 1, 1), box(5, 5, 6, 6)]
    tree = STRtree(polys)
    match = OSMSource._match(tree, polys, Point(0.5, 0.5))
    assert match is not None and match.equals(polys[0])


def test_match_accepts_nearby_polygon_within_threshold():
    polys = [box(0, 0, 1, 1)]
    tree = STRtree(polys)
    # ~0.005 deg outside the edge (< NEAR_DEG 0.009) -> still matched
    assert OSMSource._match(tree, polys, Point(1.005, 0.5)) is not None


def test_match_none_when_far():
    polys = [box(0, 0, 1, 1)]
    tree = STRtree(polys)
    assert OSMSource._match(tree, polys, Point(50, 50)) is None
