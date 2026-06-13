"""Probe: how many of our solar sites actually have an OSM ground-mounted-solar polygon?

Answers "does OSM have all the polygons?" with a real match rate against our sites,
broken down by registry status (operating vs in-planning) to show the coverage bias.

Run: uv run python scripts/probe_osm.py
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict

import httpx

from app.db import get_db

OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="DE"][admin_level=2]->.de;
(
  way["power"="plant"]["plant:source"="solar"](area.de);
  relation["power"="plant"]["plant:source"="solar"](area.de);
  way["landuse"="solar"](area.de);
  relation["landuse"="solar"](area.de);
);
out center;
"""
MATCH_M = 1000  # an OSM polygon within this distance counts as the same site


def _haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6_371_000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = math.radians(b[0] - a[0])
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def main() -> None:
    print("querying Overpass for German ground-mounted solar polygons…")
    r = httpx.post(
        OVERPASS,
        data={"data": QUERY},
        timeout=240,
        headers={"User-Agent": "gridwatch/0.1 (research; construction monitoring)"},
    )
    r.raise_for_status()
    elements = r.json()["elements"]
    osm_pts = [
        (e.get("center", e).get("lat"), e.get("center", e).get("lon"))
        for e in elements
        if (e.get("center") or e).get("lat") is not None
    ]
    print(f"OSM solar polygons found: {len(osm_pts):,}")

    # bucket OSM points into ~1 km cells for fast lookup
    grid: dict[tuple[int, int], list[tuple[float, float]]] = defaultdict(list)
    for lat, lon in osm_pts:
        grid[(round(lat, 2), round(lon, 2))].append((lat, lon))

    def has_match(lat: float, lon: float) -> bool:
        for dlat in (-0.01, 0, 0.01):
            for dlon in (-0.01, 0, 0.01):
                for p in grid.get((round(lat + dlat, 2), round(lon + dlon, 2)), []):
                    if _haversine((lat, lon), p) <= MATCH_M:
                        return True
        return False

    db = get_db()
    rows, page = [], 0
    while True:
        b = (
            db.table("sites_with_centroid")
            .select("mastr_status, lat, lon")
            .eq("technology", "solar")
            .range(page * 1000, page * 1000 + 999)
            .execute()
            .data
            or []
        )
        rows.extend(b)
        if len(b) < 1000:
            break
        page += 1

    total = Counter()
    matched = Counter()
    for s in rows:
        if s["lat"] is None:
            continue
        status = s["mastr_status"] or "unknown"
        total[status] += 1
        total["ALL"] += 1
        if has_match(s["lat"], s["lon"]):
            matched[status] += 1
            matched["ALL"] += 1

    print(f"\nour solar sites: {total['ALL']:,}")
    print(f"{'status':22} {'sites':>7} {'with OSM polygon':>18} {'%':>6}")
    for status in ["ALL", "In Betrieb", "In Planung"]:
        t = total.get(status, 0)
        m = matched.get(status, 0)
        pct = 100 * m / t if t else 0
        print(f"{status:22} {t:>7} {m:>18} {pct:>5.0f}%")


if __name__ == "__main__":
    main()
