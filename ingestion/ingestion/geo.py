"""Geometry helpers for AOI derivation: capacity-based square buffers and wind clustering.

Phase 1 AOI method is a capacity-based buffer around the MaStR point (OSM polygon
matching is a Phase 2 refinement). Wind turbines are clustered into farm footprints.
All output is WGS84 (EPSG:4326) MultiPolygon WKT for the PostGIS `sites.geom` column.
"""

from __future__ import annotations

import math

from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

M_PER_DEG_LAT = 111_320.0


def _m_per_deg_lon(lat: float) -> float:
    return M_PER_DEG_LAT * math.cos(math.radians(lat))


def square_wkt(lon: float, lat: float, side_m: float) -> str:
    """A square of side `side_m` metres centred on (lon, lat), as MultiPolygon WKT."""
    half = side_m / 2
    dlat = half / M_PER_DEG_LAT
    dlon = half / _m_per_deg_lon(lat)
    poly = box(lon - dlon, lat - dlat, lon + dlon, lat + dlat)
    return MultiPolygon([poly]).wkt


def capacity_side_m(capacity_mw: float, ha_per_mw: float, min_side_m: float) -> float:
    """Side length of a square whose area matches `capacity_mw * ha_per_mw` hectares."""
    area_m2 = max(capacity_mw, 0.0) * ha_per_mw * 10_000
    return max(min_side_m, math.sqrt(area_m2))


def cluster_turbines(
    coords: list[tuple[float, float]],
    merge_radius_m: float = 400.0,
) -> list[list[int]]:
    """Cluster turbine points into farms.

    Buffers each point by `merge_radius_m` and unions; turbines whose buffers touch
    (i.e. within ~2*radius of a chain) land in the same farm. Returns, for each farm,
    the list of input indices belonging to it.
    """
    if not coords:
        return []
    lat0 = sum(c[1] for c in coords) / len(coords)
    mlon = _m_per_deg_lon(lat0)

    def to_xy(lon: float, lat: float) -> tuple[float, float]:
        return lon * mlon, lat * M_PER_DEG_LAT

    pts = [Point(*to_xy(lon, lat)) for lon, lat in coords]
    merged = unary_union([p.buffer(merge_radius_m) for p in pts])
    farms = list(merged.geoms) if isinstance(merged, MultiPolygon) else [merged]

    clusters: list[list[int]] = [[] for _ in farms]
    for idx, p in enumerate(pts):
        for fi, farm in enumerate(farms):
            if farm.contains(p):
                clusters[fi].append(idx)
                break
    return [c for c in clusters if c]


def farm_wkt(coords: list[tuple[float, float]], pad_m: float = 250.0) -> str:
    """Footprint polygon for a set of turbine points: convex hull padded by `pad_m`."""
    lat0 = sum(c[1] for c in coords) / len(coords)
    mlon = _m_per_deg_lon(lat0)
    pts = [Point(lon * mlon, lat * M_PER_DEG_LAT) for lon, lat in coords]
    hull = unary_union(pts).convex_hull.buffer(pad_m)

    # back to lon/lat
    def inv(x: float, y: float) -> tuple[float, float]:
        return x / mlon, y / M_PER_DEG_LAT

    if isinstance(hull, Polygon):
        ring = [inv(x, y) for x, y in hull.exterior.coords]
        return MultiPolygon([Polygon(ring)]).wkt
    # degenerate (single point) -> small square
    lon, lat = coords[0]
    return square_wkt(lon, lat, 2 * pad_m)
