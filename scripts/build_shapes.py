"""Shapes and names for the agent and regional maps (brief 17, group A).

    python scripts/build_shapes.py nuts|zones|admin1|cities [--lake lake-out] [--upload]

nuts    Eurostat GISCO NUTS 2024, 1:20M, all levels (© EuroGeographics for the administrative
        boundaries) -> lake `shapes/nuts` (nuts_id, level, name, iso2, iso3, geometry).
zones   European bidding zones as outlines built from NUTS regions (the open zone geometries are
        AGPL: electricityMaps, and entsoe-py's copies of it): each zone is the union of the NUTS 3
        regions named in ZONES, ids as in prices.json. Approximate where a zone border cuts a
        region (Nordic and Italian zones follow the operators' published zone membership by
        county/region; see docs/DATA_SOURCES.md). -> lake `shapes/bidding_zones` and
        frontend/public/data/eu/zones.json (simplified, <= 1 MB).
admin1  geoBoundaries CGAZ ADM1 (CC BY 4.0, 360 MB GeoJSON; Actions only) -> lake
        `shapes/admin1` and `shapes/admin1_simplified` (0.01 degrees).
cities  GeoNames cities15000 (CC BY 4.0) -> lake `places/cities`; cities of 100,000 people and
        more -> frontend/public/data/eu/cities.json for the search box.
"""

from __future__ import annotations

import argparse
import csv
import io
import zipfile
from pathlib import Path

import wave5_common as w

NUTS_URL = (
    "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2024_4326.geojson"
)
CGAZ_URL = "https://github.com/wmgeolab/geoBoundaries/raw/main/releaseData/CGAZ/geoBoundariesCGAZ_ADM1.geojson"
CITIES_URL = "https://download.geonames.org/export/dump/cities15000.zip"
TMP = Path("/tmp/wave5")
NUTS_ISO2 = {"EL": "GR", "UK": "GB"}
# NUTS regions outside the zone's synchronous system (overseas, Canaries, Ceuta and Melilla,
# Azores and Madeira, Svalbard and Jan Mayen)
EXCLUDE = ("FRY", "ES70", "ES63", "ES64", "PT20", "PT30", "NO0B")
# zone -> NUTS id prefixes; every other zone of prices.json is its country (NUTS country code)
ZONES: dict[str, tuple[str, ...]] = {
    "DE-LU": ("DE", "LU"),
    "DK1": ("DK03", "DK04", "DK05"),
    "DK2": ("DK01", "DK02"),
    "IT-North": ("ITC", "ITH"),
    "IT-Centre-North": ("ITI1", "ITI2", "ITI3"),
    "IT-Centre-South": ("ITI4", "ITF1", "ITF3"),
    "IT-South": ("ITF2", "ITF4", "ITF5"),
    "IT-Calabria": ("ITF6",),
    "IT-Sicily": ("ITG1",),
    "IT-Sardinia": ("ITG2",),
    "NO1": ("NO020", "NO081", "NO083", "NO084", "NO085", "NO093", "NO094"),
    "NO2": ("NO092", "NO0A1"),
    "NO3": ("NO060", "NO0A3"),
    "NO4": ("NO071", "NO072", "NO073"),
    "NO5": ("NO0A2",),
    "SE1": ("SE332",),
    "SE2": ("SE331", "SE321", "SE322"),
    "SE3": ("SE11", "SE12", "SE211", "SE213", "SE214", "SE231", "SE232", "SE311", "SE312", "SE313"),
    "SE4": ("SE212", "SE221", "SE224"),
}
# zones whose border follows the regions exactly (whole countries, DE-LU, Italy's regions)
EXACT = {"DE-LU", *[z for z in ZONES if z.startswith("IT-")]}


def iso2_of(cntr: str) -> str:
    return NUTS_ISO2.get(cntr, cntr)


def zone_of(nuts_id: str, zones: list[str]) -> str | None:
    """The bidding zone (of `zones`, as in prices.json) a NUTS 3 region belongs to."""
    if nuts_id.startswith(EXCLUDE):
        return None
    for zone, prefixes in ZONES.items():
        if nuts_id.startswith(prefixes) and zone in zones:
            return zone
    country = iso2_of(nuts_id[:2])
    if country in zones and not any(z.startswith(country) and z != country for z in zones):
        return country
    return None


def parse_city(row: list[str]) -> dict:
    """One line of GeoNames cities15000 (tab-separated, 19 columns)."""
    return {
        "geonameid": int(row[0]),
        "name": row[1],
        "ascii_name": row[2],
        "lat": float(row[4]),
        "lon": float(row[5]),
        "feature_code": row[7],
        "iso2": row[8],
        "admin1": row[10],
        "population": int(row[14] or 0),
        "timezone": row[17],
    }


def nuts(args: argparse.Namespace) -> None:
    import duckdb

    src = w.download(NUTS_URL, TMP / "nuts.geojson")
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    lk = w.lake_for(
        "shapes", args.lake, "Eurostat GISCO NUTS 2024 (1:20M)",
        "© EuroGeographics for the administrative boundaries", "scripts/build_shapes.py", "NUTS 2024",
    )  # fmt: skip
    lk.write(
        con,
        "nuts",
        f"""SELECT NUTS_ID AS nuts_id, LEVL_CODE::INTEGER AS level, NAME_LATN AS name,
                   NUTS_NAME AS name_local,
                   CASE CNTR_CODE WHEN 'EL' THEN 'GR' WHEN 'UK' THEN 'GB' ELSE CNTR_CODE END AS iso2,
                   ISO3_CODE AS iso3, geom AS geometry
            FROM ST_Read('{src}')""",
        sort=["level", "nuts_id"],
        geometry="geometry",
    )
    w.lake_done(lk, args.upload)


def zones(args: argparse.Namespace) -> None:
    import json

    from shapely.geometry import shape
    from shapely.ops import unary_union

    src = w.download(NUTS_URL, TMP / "nuts.geojson")
    feats = json.loads(src.read_text(encoding="utf-8"))["features"]
    wanted = sorted(json.loads((w.EU / "prices.json").read_text(encoding="utf-8"))["zones"])
    members: dict[str, list] = {z: [] for z in wanted}
    ids: dict[str, list[str]] = {z: [] for z in wanted}
    for f in feats:
        p = f["properties"]
        if p["LEVL_CODE"] != 3:
            continue
        z = zone_of(p["NUTS_ID"], wanted)
        if z:
            g = shape(f["geometry"])
            members[z].append(g if g.is_valid else g.buffer(0))
            ids[z].append(p["NUTS_ID"])
    missing = [z for z in wanted if not members[z]]
    out, rows = {}, []
    for z in wanted:
        if not members[z]:
            continue
        g = unary_union(members[z])
        simple = g.simplify(0.01, preserve_topology=True)
        out[z] = {
            "nuts3": ids[z],
            "exact": z in EXACT or z not in ZONES,
            "polygons": w.rings(simple),
        }
        rows.append({"zone": z, "nuts3": ",".join(ids[z]), "exact": out[z]["exact"], "wkt": g.wkt})
    w.write_json(
        w.EU / "zones.json",
        {
            "fetched": w.now(),
            "source": "Built from Eurostat GISCO NUTS 2024 regions (© EuroGeographics); approximate outline where a zone border cuts a region",
            "zones": out,
        },
        max_mb=1.0,
    )
    print(f"  {len(out)} zones; none for {missing}", flush=True)
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    tmp = TMP / "zones.json"
    tmp.write_text(json.dumps(rows), encoding="utf-8")
    lk = w.lake_for(
        "shapes", args.lake, "Bidding zones built from Eurostat GISCO NUTS 2024",
        "© EuroGeographics for the administrative boundaries", "scripts/build_shapes.py", "NUTS 2024",
    )  # fmt: skip
    lk.write(
        con,
        "bidding_zones",
        f"""SELECT zone, string_split(nuts3, ',') AS nuts3, exact, left(zone, 2) AS iso2,
                   ST_GeomFromText(wkt) AS geometry FROM read_json('{tmp}', maximum_object_size = 500000000)""",
        sort=["zone"],
        geometry="geometry",
    )
    w.lake_done(lk, args.upload)


def admin1(args: argparse.Namespace) -> None:
    import duckdb

    src = w.download(CGAZ_URL, TMP / "cgaz_adm1.geojson")
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    import lake

    lake.iso_codes(con)
    con.execute(f"CREATE TABLE a AS SELECT * FROM ST_Read('{src}')")
    print(con.execute("DESCRIBE a").fetchall(), flush=True)
    lk = w.lake_for(
        "shapes", args.lake, "geoBoundaries CGAZ ADM1 (wmgeolab)", "CC BY 4.0",
        "scripts/build_shapes.py", "CGAZ",
    )  # fmt: skip
    base = """SELECT a.shapeGroup AS iso3, i.iso2, a.shapeID AS admin1_id, a.shapeName AS name,
                     a.shapeISO AS admin1_iso, {geom} AS geometry
              FROM a LEFT JOIN iso_codes i ON i.iso3 = a.shapeGroup"""
    lk.write(
        con, "admin1", base.format(geom="a.geom"), sort=["iso3", "admin1_id"], geometry="geometry"
    )
    lk.write(
        con,
        "admin1_simplified",
        base.format(geom="ST_SimplifyPreserveTopology(a.geom, 0.01)"),
        sort=["iso3", "admin1_id"],
        geometry="geometry",
    )
    w.lake_done(lk, args.upload)


def cities(args: argparse.Namespace) -> None:
    import duckdb

    src = w.download(CITIES_URL, TMP / "cities15000.zip")
    with zipfile.ZipFile(src) as z:
        text = z.read("cities15000.txt").decode("utf-8")
    rows = [
        parse_city(r) for r in csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE)
    ]
    big = sorted((r for r in rows if r["population"] >= 100_000), key=lambda r: -r["population"])
    w.write_json(
        w.EU / "cities.json",
        {
            "fetched": w.now(),
            "source": "GeoNames cities15000 (CC BY 4.0), cities of 100,000 people and more",
            "cities": [
                [r["name"], r["iso2"], round(r["lon"], 4), round(r["lat"], 4), r["population"]]
                for r in big
            ],
        },
        max_mb=1.0,
    )
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    import json

    tmp = TMP / "cities.json"
    tmp.write_text(json.dumps(rows), encoding="utf-8")
    lk = w.lake_for(
        "places", args.lake, "GeoNames cities15000", "CC BY 4.0", "scripts/build_shapes.py",
        w.now()[:10],
    )  # fmt: skip
    lk.write(
        con,
        "cities",
        f"""SELECT *, ST_Point(lon, lat) AS geometry FROM read_json('{tmp}', maximum_object_size = 500000000)""",
        sort=["iso2", "population DESC"],
        geometry="geometry",
    )
    print(f"  {len(rows):,} cities, {len(big):,} of 100,000 people and more", flush=True)
    w.lake_done(lk, args.upload)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["nuts", "zones", "admin1", "cities"])
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    {"nuts": nuts, "zones": zones, "admin1": admin1, "cities": cities}[args.what](args)


if __name__ == "__main__":
    main()
