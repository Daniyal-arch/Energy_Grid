"""Build the static layers of the Europe grid view from data/eu/ (fetch_eu_energy.py).

Writes frontend/public/data/eu/:
  grid.json       transmission lines >= 220 kV [voltage kV, flat lon/lat path] and
                  HVDC links [capacity MW, flat path], simplified for continent zoom
  plants.json     operating plants >= 20 MW [group, capacity MW, lon, lat]
  countries.json  land polygons and border lines of the covered countries

Sources: PyPSA-Eur prebuilt OSM network (Zenodo 18619025, ODbL),
powerplantmatching (PyPSA, MIT), Eurostat GISCO countries 1:20M.

    uv run python scripts/build_eu_grid.py
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

from shapely import wkt
from shapely.geometry import LineString, MultiLineString, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "eu"
OUT = ROOT / "frontend" / "public" / "data" / "eu"

LINE_TOL = 0.002  # degrees, ~150-200 m; 1 px is ~3 km at continent zoom
LAND_TOL = 0.01
MIN_PLANT_MW = 20.0
YEAR = date.today().year

# covered area: the PyPSA-Eur network countries (ISO 3166 alpha-2, GISCO uses EL/UK)
COUNTRIES = [
    "AL",
    "AT",
    "BA",
    "BE",
    "BG",
    "CH",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GB",
    "GR",
    "HR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "ME",
    "MD",
    "MK",
    "NL",
    "NO",
    "PL",
    "PT",
    "RO",
    "RS",
    "SE",
    "SI",
    "SK",
    "UA",
    "XK",
]
GISCO_ID = {"GR": "EL", "GB": "UK"}

PLANT_GROUP = {
    "Nuclear": "nuclear",
    "Hard Coal": "coal",
    "Lignite": "coal",
    "Natural Gas": "gas",
    "Oil": "gas",
    "Hydro": "hydro",
    "Wind": "wind",
    "Solar": "solar",
    "Biogas": "bio",
    "Solid Biomass": "bio",
    "Waste": "bio",
    "Geothermal": "other",
    "Other": "other",
    "Battery": "storage",
    "Hydrogen Storage": "storage",
    "Heat Storage": "storage",
    "Mechanical Storage": "storage",
}
GROUPS = ["nuclear", "coal", "gas", "hydro", "wind", "solar", "bio", "storage", "other"]


def flat(geom: LineString, ndigits: int = 4) -> list[float]:
    out: list[float] = []
    for x, y in geom.coords:
        out += [round(x, ndigits), round(y, ndigits)]
    return out


def lines_of(geom) -> list[LineString]:
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    return []


def read_csv(name: str) -> list[dict[str, str]]:
    csv.field_size_limit(sys.maxsize if sys.maxsize < 2**31 else 2**31 - 1)
    with (SRC / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, quotechar="'"))


def build_grid() -> dict:
    lines = []
    for row in read_csv("lines.csv"):
        kv = int(float(row["voltage"]))
        for part in lines_of(wkt.loads(row["geometry"])):
            simple = part.simplify(LINE_TOL, preserve_topology=False)
            if len(simple.coords) >= 2:
                lines.append([kv, flat(simple)])
    links = []
    for row in read_csv("links.csv"):
        for part in lines_of(wkt.loads(row["geometry"])):
            simple = part.simplify(LINE_TOL, preserve_topology=False)
            if len(simple.coords) >= 2:
                links.append([round(float(row["p_nom"] or 0)), flat(simple)])
    return {
        "source": "PyPSA-Eur prebuilt network from OpenStreetMap (Zenodo 18619025), ODbL",
        "lines": lines,
        "links": links,
    }


def build_plants() -> dict:
    with (SRC / "powerplants.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    plants = []
    for r in rows:
        mw = float(r["Capacity"] or 0)
        if mw < MIN_PLANT_MW or not r["lat"] or not r["lon"]:
            continue
        if r["DateOut"] and float(r["DateOut"]) < YEAR:
            continue
        if r["DateIn"] and float(r["DateIn"]) > YEAR:
            continue
        group = PLANT_GROUP.get(r["Fueltype"], "other")
        plants.append(
            [GROUPS.index(group), round(mw), round(float(r["lon"]), 4), round(float(r["lat"]), 4)]
        )
    plants.sort(key=lambda p: -p[1])  # big first, so small ones draw on top
    return {
        "source": "powerplantmatching (PyPSA), operating units >= 20 MW",
        "groups": GROUPS,
        "plants": plants,
    }


def build_countries() -> dict:
    with (SRC / "countries.geojson").open(encoding="utf-8") as f:
        fc = json.load(f)
    wanted = {GISCO_ID.get(c, c): c for c in COUNTRIES}
    land = []
    shapes = []
    for feat in fc["features"]:
        iso = wanted.get(feat["properties"]["CNTR_ID"])
        if not iso:
            continue
        geom = shape(feat["geometry"]).simplify(LAND_TOL)
        shapes.append(geom)
        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        for poly in polys:
            if poly.area < 0.01:  # tiny islands
                continue
            land.append([flat(poly.exterior, 3)] + [flat(r, 3) for r in poly.interiors])
    # borders = country outlines minus the coast (outline of the union)
    coast = unary_union(shapes).boundary
    borders = []
    for s in shapes:
        inner = s.boundary.difference(coast.buffer(0.02))
        borders += [flat(ls, 3) for ls in lines_of(inner) if ls.length > 0.05]
    coastline = [flat(ls, 3) for ls in lines_of(coast.simplify(LAND_TOL)) if ls.length > 0.05]
    return {
        "source": "Eurostat GISCO countries 1:20M (2024)",
        "land": land,
        "borders": borders,
        "coast": coastline,
    }


def write(name: str, payload: dict) -> None:
    path = OUT / name
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"{name}: {path.stat().st_size / 1e6:.1f} MB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    grid = build_grid()
    write("grid.json", grid)
    print(f"  {len(grid['lines']):,} lines, {len(grid['links'])} HVDC links")
    plants = build_plants()
    write("plants.json", plants)
    print(f"  {len(plants['plants']):,} plants")
    countries = build_countries()
    write("countries.json", countries)
    print(f"  {len(countries['land'])} land polygons, {len(countries['borders'])} border lines")


if __name__ == "__main__":
    main()
