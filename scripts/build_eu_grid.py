"""Build the static layers of the Europe grid view from data/eu/ (fetch_eu_energy.py).

Writes frontend/public/data/eu/:
  grid.json       transmission lines >= 220 kV [voltage kV, flat lon/lat path], HVDC links
                  [capacity MW, flat path], simplified for continent zoom, and
                  substations [kV, lon, lat, ISO]
  plants.json     operating plants >= 20 MW [group, MW, lon, lat, ISO, name, year in],
                  plus units and capacity per country and group (units >= 1 MW)
  plants/<ISO>.json  every operating unit >= 1 MW of one country, loaded on focus
  gas.json        gas pipelines, LNG terminals, storages (SciGRID_gas IGGIELGN, 2021)
  world.json      land of all other countries (GeoJSON, coarse), the globe's base
  countries.json  country polygons (ISO code, name, label point), borders, coast

Sources: PyPSA-Eur prebuilt OSM network (Zenodo 18619025, ODbL),
powerplantmatching (PyPSA, MIT), Eurostat GISCO countries 1:20M,
SciGRID_gas IGGIELGN (Zenodo 4767098, CC BY 4.0).

    uv run python scripts/build_eu_grid.py
"""

from __future__ import annotations

import csv
import json
import sys
import zipfile
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
WORLD_TOL = 0.12  # rest of the world: outline only, seen from far away
MIN_PLANT_MW = 20.0
MIN_UNIT_MW = 1.0  # per-country files shown on focus
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


def build_substations() -> list[list]:
    """[kV, lon, lat, ISO] per substation of the PyPSA-Eur network (>= 220 kV)."""
    out = []
    for row in read_csv("buses.csv"):
        if row["under_construction"] == "t" or not row["x"]:
            continue
        kv = int(float(row["voltage"] or 0))
        out.append([kv, round(float(row["x"]), 4), round(float(row["y"]), 4), row["country"]])
    return out


def _certain(item: dict, key: str, ndigits: int = 0) -> float | None:
    """A SciGRID_gas parameter, only when the dataset marks it as not estimated."""
    value = item["param"].get(key)
    if value is None or item["uncertainty"].get(key) not in (0, 0.0):
        return None
    return round(float(value), ndigits)


def build_gas() -> dict:
    """Pipelines, LNG terminals and storages from SciGRID_gas IGGIELGN (2021)."""
    z = zipfile.ZipFile(SRC / "IGGIELGN.zip")

    def features(name: str) -> list[dict]:
        return json.load(z.open(f"data/IGGIELGN_{name}.geojson"))["features"]

    covered = set(COUNTRIES)

    def iso(code: str) -> str:
        return "GR" if code == "EL" else code

    pipes = []
    for f in features("PipeSegments"):
        # inside the mapped countries only; XX marks offshore segments
        codes = {iso(c) for c in f["properties"]["country_code"]}
        if not (codes - {"XX"}) or not codes <= covered | {"XX"}:
            continue
        line = shape(f["geometry"]).simplify(LINE_TOL)
        diameter = f["properties"]["param"].get("diameter_mm") or 0
        for part in lines_of(line):
            if len(part.coords) >= 2:
                pipes.append([round(diameter), flat(part)])

    def sites(name: str, capacity_key: str) -> list[list]:
        out = []
        for f in features(name):
            props = f["properties"]
            if iso(props["country_code"]) not in covered:
                continue
            x, y = f["geometry"]["coordinates"][:2]
            out.append(
                [
                    props["name"],
                    iso(props["country_code"]),
                    round(x, 4),
                    round(y, 4),
                    props["param"].get("start_year"),
                    _certain(props, capacity_key),
                ]
            )
        return out

    return {
        "source": "SciGRID_gas IGGIELGN (2021, Zenodo 4767098), CC BY 4.0; "
        "capacities only where the dataset marks them as not estimated",
        "pipes": pipes,
        # [name, ISO, lon, lat, start year, capacity or null]
        "lng": sites("LNGs", "max_cap_store2pipe_M_m3_per_d"),  # send-out, M m3/day
        "storages": sites("Storages", "max_workingGas_M_m3"),  # working gas, M m3
    }


def build_plants() -> tuple[dict, dict[str, dict]]:
    """Plants for the Europe map (>= 20 MW) and per-country files with every unit >= 1 MW.

    The per-country files are loaded when a country is focused; the German input is
    unit-level (MaStR), so the 1 MW floor keeps it to ~39k rows.
    """
    with (SRC / "powerplants.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    plants = []
    per_country: dict[str, list[list]] = {}
    # per country and group: [units, MW] of the units >= 1 MW shown on focus
    by_country: dict[str, dict[str, list[float]]] = {}
    for r in rows:
        mw = float(r["Capacity"] or 0)
        if mw < MIN_UNIT_MW or not r["lat"] or not r["lon"]:
            continue
        if r["DateOut"] and float(r["DateOut"]) < YEAR:
            continue
        if r["DateIn"] and float(r["DateIn"]) > YEAR:
            continue
        group = PLANT_GROUP.get(r["Fueltype"], "other")
        iso = PPM_ISO.get(r["Country"])
        year = int(float(r["DateIn"])) if r["DateIn"] else None
        lon, lat = round(float(r["lon"]), 4), round(float(r["lat"]), 4)
        if iso:
            cell = by_country.setdefault(iso, {}).setdefault(group, [0, 0.0])
            cell[0] += 1
            cell[1] += mw
            per_country.setdefault(iso, []).append(
                [GROUPS.index(group), round(mw, 1), lon, lat, r["Name"], year]
            )
        if mw >= MIN_PLANT_MW:
            plants.append([GROUPS.index(group), round(mw), lon, lat, iso, r["Name"], year])
    plants.sort(key=lambda p: -p[1])  # big first, so small ones draw on top
    main = {
        "source": "powerplantmatching (PyPSA), operating units >= 20 MW",
        "groups": GROUPS,
        "plants": plants,
        "by_country": {
            iso: {g: [int(n), round(mw)] for g, (n, mw) in sorted(groups.items())}
            for iso, groups in sorted(by_country.items())
        },
    }
    files = {
        iso: {
            "source": "powerplantmatching (PyPSA), operating units >= 1 MW",
            # [group index, MW, lon, lat, name, year in operation]
            "plants": sorted(units, key=lambda p: -p[1]),
        }
        for iso, units in per_country.items()
    }
    return main, files


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


def build_world() -> dict:
    """Land of every other country, coarse, as the globe's base (no data on it)."""
    with (SRC / "countries.geojson").open(encoding="utf-8") as f:
        fc = json.load(f)
    covered = {GISCO_ID.get(c, c) for c in COUNTRIES}
    features = []
    for feat in fc["features"]:
        if feat["properties"]["CNTR_ID"] in covered:
            continue
        geom = shape(feat["geometry"]).simplify(WORLD_TOL)
        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        rings = [
            [[[round(x, 2), round(y, 2)] for x, y in p.exterior.coords]]
            for p in polys
            if p.area >= 0.3 and len(p.exterior.coords) >= 4
        ]
        if rings:
            features.append(
                {
                    "type": "Feature",
                    "properties": {"name": feat["properties"]["NAME_ENGL"]},
                    "geometry": {"type": "MultiPolygon", "coordinates": rings},
                }
            )
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    grid = build_grid()
    grid["substations"] = build_substations()
    write("grid.json", grid)
    print(
        f"  {len(grid['lines']):,} lines, {len(grid['links'])} HVDC links, "
        f"{len(grid['substations']):,} substations"
    )
    plants, per_country = build_plants()
    write("plants.json", plants)
    print(f"  {len(plants['plants']):,} plants >= 20 MW")
    (OUT / "plants").mkdir(exist_ok=True)
    for iso_code, payload in per_country.items():
        (OUT / "plants" / f"{iso_code}.json").write_text(
            json.dumps(payload, separators=(",", ":")), encoding="utf-8"
        )
    units = sum(len(v["plants"]) for v in per_country.values())
    print(f"  plants/<ISO>.json: {units:,} units >= 1 MW in {len(per_country)} countries")
    gas = build_gas()
    write("gas.json", gas)
    print(
        f"  {len(gas['pipes']):,} pipe segments, {len(gas['lng'])} LNG, {len(gas['storages'])} storages"
    )
    countries = build_countries()
    write("countries.json", countries)
    world = build_world()
    write("world.json", world)
    print(f"  {len(countries['countries'])} countries, {len(countries['borders'])} border lines")


if __name__ == "__main__":
    main()
