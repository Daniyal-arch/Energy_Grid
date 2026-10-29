"""Places from the app's own outlines and gazetteer: countries (Europe's and the world's), US
states, bidding zones, GeoNames cities, and coordinates. Point-in-outline tests use the same
flat-ring rule as the frontend (lib/site.ts inFlatPolygons).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

EARTH_KM = 6371.0088
COORD = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*°?\s*([NSns])?\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*°?\s*([EWew])?\s*$"
)


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between two lon/lat points (haversine), as lib/site.ts km()."""
    rad = math.pi / 180
    dlat = (b[1] - a[1]) * rad
    dlon = (b[0] - a[0]) * rad
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(a[1] * rad) * math.cos(b[1] * rad) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_KM * math.asin(min(1.0, math.sqrt(h)))


def in_flat_ring(x: float, y: float, ring: list[float]) -> bool:
    inside = False
    n = len(ring) // 2
    j = n - 1
    for i in range(n):
        xi, yi, xj, yj = ring[2 * i], ring[2 * i + 1], ring[2 * j], ring[2 * j + 1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def in_flat_polygons(p: tuple[float, float], polygons: list[list[list[float]]]) -> bool:
    return any(
        poly
        and in_flat_ring(p[0], p[1], poly[0])
        and not any(in_flat_ring(p[0], p[1], h) for h in poly[1:])
        for poly in polygons
    )


def geojson_to_flat(geom: dict[str, Any]) -> list[list[list[float]]]:
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return [[[v for pt in ring for v in pt[:2]] for ring in poly] for poly in polys]


def bbox_of(polygons: list[list[list[float]]]) -> list[float]:
    xs = [v for poly in polygons for v in poly[0][0::2]] if polygons else [0.0]
    ys = [v for poly in polygons for v in poly[0][1::2]] if polygons else [0.0]
    return [round(min(xs), 4), round(min(ys), 4), round(max(xs), 4), round(max(ys), 4)]


@dataclass
class Place:
    kind: str
    name: str
    codes: dict[str, str]
    centre: list[float]
    bbox: list[float] | None
    source: str
    polygons: list[list[list[float]]] = field(default_factory=list, repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "codes": self.codes,
            "centre": self.centre,
            "bbox": self.bbox,
            "source": self.source,
        }


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.casefold().replace("-", " ")).strip()


class Gazetteer:
    def __init__(self, public_dir: Path) -> None:
        self.public = public_dir

    def _load(self, rel: str) -> Any:
        p = self.public / rel
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    @cached_property
    def europe(self) -> list[Place]:
        f = self._load("eu/countries.json") or {"countries": [], "source": ""}
        out = []
        for c in f["countries"]:
            bb = bbox_of(c["polygons"])
            label = c.get("label") or [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2]
            out.append(
                Place(
                    "country", c["name"], {"iso2": c["iso"]}, label, bb, f["source"], c["polygons"]
                )
            )
        return out

    @cached_property
    def world(self) -> list[Place]:
        f = self._load("eu/world.json") or {"features": []}
        out = []
        for ft in f["features"]:
            polys = geojson_to_flat(ft["geometry"])
            bb = bbox_of(polys)
            out.append(
                Place(
                    "country",
                    ft["properties"]["name"],
                    {"iso3": ft["properties"]["iso3"]},
                    [round((bb[0] + bb[2]) / 2, 4), round((bb[1] + bb[3]) / 2, 4)],
                    bb,
                    "world outlines (frontend/public/data/eu/world.json)",
                    polys,
                )
            )
        return out

    @cached_property
    def us_states(self) -> list[Place]:
        f = self._load("us/states.json") or {"states": [], "source": ""}
        return [
            Place(
                "us_state",
                s["name"],
                {"state": s["code"]},
                s["label"],
                s["bbox"],
                f["source"],
                s["polygons"],
            )
            for s in f["states"]
        ]

    @cached_property
    def zones(self) -> list[Place]:
        f = self._load("eu/prices.json") or {"zones": {}}
        by_iso = {p.codes["iso2"]: p for p in self.europe}
        out = []
        for z, v in f["zones"].items():
            c = by_iso.get(v["country"])
            out.append(
                Place(
                    "bidding_zone",
                    z,
                    {"zone": z, "iso2": v["country"]},
                    c.centre if c else [0, 0],
                    c.bbox if c else None,
                    "ENTSO-E bidding zones (prices.json); zone outlines are in the lake (shapes)",
                )
            )
        return out

    @cached_property
    def cities(self) -> list[Place]:
        f = self._load("eu/cities.json") or {"cities": [], "source": ""}
        return [
            Place(
                "city",
                c[0],
                {"iso2": c[1]},
                [c[2], c[3]],
                None,
                f"{f['source']}; population {c[4]}",
            )
            for c in f["cities"]
        ]

    def find(self, text: str, limit: int = 5) -> list[Place]:
        m = COORD.match(text)
        if m:
            a, ns, b, ew = m.groups()
            lat, lon = float(a), float(b)
            if (ns or "").upper() == "S":
                lat = -abs(lat)
            if (ew or "").upper() == "W":
                lon = -abs(lon)
            if not ns and not ew and abs(lat) > 90:  # "lon, lat" given
                lat, lon = lon, lat
            loc = self.locate(lon, lat)
            name = loc["name"] or "open sea"
            return [Place("point", name, loc["codes"], [lon, lat], None, "coordinates as given")]
        q = _norm(text)
        if not q:
            return []
        ranked: list[tuple[int, int, Place]] = []
        groups = [self.europe, self.us_states, self.zones, self.world, self.cities]
        for gi, group in enumerate(groups):
            for p in group:
                name = _norm(p.name)
                codes = {c.lower() for c in p.codes.values()}
                if q == name:
                    r = 0
                elif q in codes and p.kind != "city":
                    r = 1
                elif name.startswith(q):
                    r = 2
                elif len(q) > 3 and q in name:
                    r = 3
                else:
                    continue
                ranked.append((r, gi, p))
        ranked.sort(key=lambda t: (t[0], t[1]))
        seen: set[tuple[str, str]] = set()
        out = []
        for _, _, p in ranked:
            key = (p.kind, p.name)
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
            if len(out) >= limit:
                break
        return out

    def locate(self, lon: float, lat: float) -> dict[str, Any]:
        """The country (Europe's outlines first, then the world's) and the US state of a point."""
        pt = (lon, lat)
        eu = next((p for p in self.europe if in_flat_polygons(pt, p.polygons)), None)
        w = None if eu else next((p for p in self.world if in_flat_polygons(pt, p.polygons)), None)
        st = next((p for p in self.us_states if in_flat_polygons(pt, p.polygons)), None)
        codes: dict[str, str] = {}
        if eu:
            codes["iso2"] = eu.codes["iso2"]
        if w:
            codes["iso3"] = w.codes["iso3"]
        if st:
            codes["state"] = st.codes["state"]
            codes["iso3"] = "USA"
        name = f"{st.name}, United States" if st else (eu.name if eu else (w.name if w else None))
        return {"name": name, "codes": codes, "europe": bool(eu)}
