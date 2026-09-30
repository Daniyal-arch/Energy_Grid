"""Build the static layers of the Europe grid view from data/eu/ (fetch_eu_energy.py).

Writes frontend/public/data/eu/:
  grid.json       transmission lines >= 220 kV [voltage kV, flat lon/lat path] and
                  HVDC links [capacity MW, flat path], simplified for continent zoom
  plants.json     operating plants >= 20 MW [group, MW, lon, lat, ISO, name, year in],
                  plus capacity per country and group
  countries.json  country polygons (ISO code, name, label point), borders, coast

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
# powerplantmatching country names -> ISO 3166 alpha-2
PPM_ISO = {
    "Albania": "AL",
    "Austria": "AT",
    "Belgium": "BE",
    "Bosnia and Herzegovina": "BA",
    "Bulgaria": "BG",
    "Croatia": "HR",
    "Czechia": "CZ",
    "Denmark": "DK",
    "Estonia": "EE",
    "Finland": "FI",
    "France": "FR",
    "Germany": "DE",
    "Greece": "GR",
    "Hungary": "HU",
    "Ireland": "IE",
    "Italy": "IT",
    "Kosovo": "XK",
    "Latvia": "LV",
    "Lithuania": "LT",
    "Luxembourg": "LU",
    "Moldova": "MD",
    "Montenegro": "ME",
    "Netherlands": "NL",
    "North Macedonia": "MK",
    "Norway": "NO",
    "Poland": "PL",
    "Portugal": "PT",
    "Romania": "RO",
    "Serbia": "RS",
    "Slovakia": "SK",
    "Slovenia": "SI",
    "Spain": "ES",
    "Sweden": "SE",
    "Switzerland": "CH",
    "Ukraine": "UA",
    "United Kingdom": "GB",
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
    # per country and group: [units, MW] of the same filtered set that is drawn
    by_country: dict[str, dict[str, list[float]]] = {}
    for r in rows:
        mw = float(r["Capacity"] or 0)
        if mw < MIN_PLANT_MW or not r["lat"] or not r["lon"]:
            continue
        if r["DateOut"] and float(r["DateOut"]) < YEAR:
            continue
        if r["DateIn"] and float(r["DateIn"]) > YEAR:
            continue
        group = PLANT_GROUP.get(r["Fueltype"], "other")
        iso = PPM_ISO.get(r["Country"])
        if iso:
            cell = by_country.setdefault(iso, {}).setdefault(group, [0, 0.0])
            cell[0] += 1
            cell[1] += mw
        year = int(float(r["DateIn"])) if r["DateIn"] else None
        plants.append(
            [
                GROUPS.index(group),
                round(mw),
                round(float(r["lon"]), 4),
                round(float(r["lat"]), 4),
                iso,
                r["Name"],
                year,
            ]
        )
    plants.sort(key=lambda p: -p[1])  # big first, so small ones draw on top
    return {
        "source": "powerplantmatching (PyPSA), operating units >= 20 MW",
        "groups": GROUPS,
        "plants": plants,
        "by_country": {
            iso: {g: [int(n), round(mw)] for g, (n, mw) in sorted(groups.items())}
            for iso, groups in sorted(by_country.items())
        },
    }


def build_countries() -> dict:
    with (SRC / "countries.geojson").open(encoding="utf-8") as f:
        fc = json.load(f)
    wanted = {GISCO_ID.get(c, c): c for c in COUNTRIES}
    countries = []
    shapes = []
    for feat in fc["features"]:
        iso = wanted.get(feat["properties"]["CNTR_ID"])
        if not iso:
            continue
        geom = shape(feat["geometry"]).simplify(LAND_TOL)
        shapes.append(geom)
        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        # drop tiny islands and overseas territories (French Guiana, Reunion, Canaries...)
        polys = [
            p
            for p in polys
            if p.area >= 0.01 and -25 <= p.centroid.x <= 45 and 34 <= p.centroid.y <= 72
        ]
        biggest = max(polys, key=lambda p: p.area)
        label = biggest.representative_point()
        countries.append(
            {
                "iso": iso,
                "name": feat["properties"]["NAME_ENGL"],
                "label": [round(label.x, 2), round(label.y, 2)],
                "polygons": [
                    [flat(p.exterior, 3)] + [flat(r, 3) for r in p.interiors] for p in polys
                ],
            }
        )
    # borders = country outlines minus the coast (outline of the union)
    coast = unary_union(shapes).boundary
    borders = []
    for s in shapes:
        inner = s.boundary.difference(coast.buffer(0.02))
        borders += [flat(ls, 3) for ls in lines_of(inner) if ls.length > 0.05]
    coastline = [flat(ls, 3) for ls in lines_of(coast.simplify(LAND_TOL)) if ls.length > 0.05]
    return {
        "source": "Eurostat GISCO countries 1:20M (2024)",
        "countries": countries,
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
    print(f"  {len(countries['countries'])} countries, {len(countries['borders'])} border lines")


if __name__ == "__main__":
    main()
