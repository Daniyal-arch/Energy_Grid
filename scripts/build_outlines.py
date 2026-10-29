"""Outlines at every level for the agent's areas (docs/tasks/27, B1) -> lake `outlines/*`.

    python scripts/build_outlines.py divisions|adm2|us|uk|fr|nl|ucdb|grid|national|names|all
        [--lake lake-out] [--upload]

Every set has the same columns, so resolve_area and the shape sets read them alike
(backend/data/areas.py): `id` (the source's code), `name`, `level` (the atlas's level name),
`subtype` (the source's own), `iso3`, `parent_name`, `population` (as published, else NULL),
`geometry` (EPSG:4326) and the GeoParquet `bbox`, rows in Hilbert order.

divisions  Overture Maps divisions (division_area joined to division for population and the
           parent's name), the newest release on its public S3 bucket, every subtype below the
           country, worldwide; ODbL (OSM), CC BY 4.0 (geoBoundaries, Esri Community Maps). 4.6 GB
           read by range, only the needed columns. Partition iso3.
adm2       geoBoundaries CGAZ ADM2 (CC BY 4.0), 550 MB GeoJSON.
us         US Census cartographic boundary files 2024, 1:500k: places, county subdivisions,
           tracts (public domain; 23 + 40 + 58 MB zips).
uk         ONS Open Geography (OGL v3): ITL 1-3 (January 2025), local authority districts
           (December 2024), MSOA and LSOA (December 2021, England and Wales), generalised (BGC);
           Scottish data zones 2022 (Scottish Government, OGL v3) and Northern Ireland super data
           zones 2021 (NISRA, OGL v3).
fr         IGN / INSEE Contours IRIS 2025 (Licence Ouverte 2.0), GeoParquet 133 MB; communes are
           the union of their IRIS (IRIS partition every commune: computed, exact).
nl         CBS Wijk- en buurtkaart 2024 via PDOK's OGC API (CC BY 4.0): gemeenten, wijken,
           buurten.
ucdb       GHS Urban Centre Database R2024 V1.1 (CC BY 4.0), 308 MB zip: city outlines worldwide
           with their 2025 population.
grid       Eurostat Census 2021 population grid, 1 km (GEOSTAT), 590 MB zip: the cells with their
           census population (EU and EFTA).
national   the national census small areas the research found open
           (docs/research/small-area-energy.md): one table `small_areas`.
names      the search index over every set (no geometry): `outlines/names`.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import duckdb
import httpx
import wave5_common as w

TMP = Path("/tmp/wave8/outlines")
SCRIPT = "scripts/build_outlines.py"
OVERTURE = "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com"
# Overture subtype -> the atlas's level
SUBTYPE_LEVEL = {
    "dependency": "region",
    "macroregion": "region",
    "region": "region",
    "macrocounty": "county",
    "county": "county",
    "localadmin": "locality",
    "locality": "locality",
    "borough": "locality",
    "macrohood": "neighbourhood",
    "neighborhood": "neighbourhood",
    "microhood": "neighbourhood",
}
ONS = "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services"
UK_LAYERS = {
    # level: (service, code field, name field)
    "itl1": ("ITL1_JAN_2025_UK_BGC", "ITL125CD", "ITL125NM"),
    "itl2": ("ITL2_JAN_2025_UK_BGC", "ITL225CD", "ITL225NM"),
    "itl3": ("ITL3_JAN_2025_UK_BGC_V2:1", "ITL325CD", "ITL325NM"),
    "lad": ("Local_Authority_Districts_December_2024_Boundaries_UK_BGC", "LAD24CD", "LAD24NM"),
    "msoa": ("Middle_layer_Super_Output_Areas_December_2021_Boundaries_EW_BGC_V3", "MSOA21CD", "MSOA21NM"),
    "lsoa": ("Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BGC_V5", "LSOA21CD", "LSOA21NM"),
}  # fmt: skip
SCOT_DZ = "https://maps.gov.scot/ATOM/shapefiles/SG_DataZoneBdry_2022.zip"
NI_SDZ = "https://www.nisra.gov.uk/files/nisra/publications/geography-sdz2021-esri-shapefile.zip"
IRIS = "https://data.geopf.fr/telechargement/download/CONTOURS-IRIS/CONTOURS-IRIS_3-0__GEOPARQUET_WGS84G_FRA_2025-01-01/contours_iris.parquet"
PDOK = "https://api.pdok.nl/cbs/wijken-en-buurten-2024/ogc/v1/collections"
UCDB = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_UCDB_GLOBE_R2024A/GHS_UCDB_GLOBE_R2024A/V1-1/GHS_UCDB_GLOBE_R2024A_V1_1.zip"
GEOSTAT = "https://gisco-services.ec.europa.eu/census/2021/Eurostat_Census-GRID_2021_V2.2.zip"
CGAZ2 = "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/CGAZ/geoBoundariesCGAZ_ADM2.geojson"
TIGER = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_{}_500k.zip"
STATES = {
    "01": "Alabama", "02": "Alaska", "04": "Arizona", "05": "Arkansas", "06": "California",
    "08": "Colorado", "09": "Connecticut", "10": "Delaware", "11": "District of Columbia",
    "12": "Florida", "13": "Georgia", "15": "Hawaii", "16": "Idaho", "17": "Illinois",
    "18": "Indiana", "19": "Iowa", "20": "Kansas", "21": "Kentucky", "22": "Louisiana",
    "23": "Maine", "24": "Maryland", "25": "Massachusetts", "26": "Michigan", "27": "Minnesota",
    "28": "Mississippi", "29": "Missouri", "30": "Montana", "31": "Nebraska", "32": "Nevada",
    "33": "New Hampshire", "34": "New Jersey", "35": "New Mexico", "36": "New York",
    "37": "North Carolina", "38": "North Dakota", "39": "Ohio", "40": "Oklahoma", "41": "Oregon",
    "42": "Pennsylvania", "44": "Rhode Island", "45": "South Carolina", "46": "South Dakota",
    "47": "Tennessee", "48": "Texas", "49": "Utah", "50": "Vermont", "51": "Virginia",
    "53": "Washington", "54": "West Virginia", "55": "Wisconsin", "56": "Wyoming",
    "60": "American Samoa", "66": "Guam", "69": "Northern Mariana Islands", "72": "Puerto Rico",
    "78": "U.S. Virgin Islands",
}  # fmt: skip
COLUMNS = "id, name, level, subtype, iso3, parent_name, population, geometry"


def con_spatial() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs")
    con.execute("SET geometry_always_xy = true")
    import lake as lakemod

    lakemod.iso_codes(con)
    return con


def lake(args: argparse.Namespace, source: str, licence: str, version: str = ""):  # noqa: ANN201
    return w.lake_for("outlines", args.lake, source, licence, SCRIPT, version)


def write(lk, con: duckdb.DuckDBPyConnection, table: str, query: str, **kw: object) -> None:  # noqa: ANN001
    import lake as lakemod

    t0 = time.time()
    lk.write(
        con,
        table,
        f"SELECT {COLUMNS} FROM (SELECT * EXCLUDE (geometry), ST_GeomFromWKB(ST_AsWKB(geometry)) AS geometry "
        f"FROM ({query})) WHERE geometry IS NOT NULL AND NOT ST_IsEmpty(geometry)",
        sort=["iso3", lakemod.hilbert("geometry")],
        geometry="geometry",
        **kw,
    )
    print(f"  outlines/{table}: written in {time.time() - t0:.0f} s", flush=True)


def newest_overture() -> str:
    xml = httpx.get(
        OVERTURE, params={"list-type": "2", "prefix": "release/", "delimiter": "/"}, timeout=60
    ).text
    return sorted(re.findall(r"<Prefix>release/([^<]+)/</Prefix>", xml))[-1]


# ---------------------------------------------------------------------- sets


def divisions(args: argparse.Namespace) -> None:
    rel = newest_overture()
    con = con_spatial()
    con.execute("SET s3_region = 'us-west-2'")
    base = f"s3://overturemaps-us-west-2/release/{rel}/theme=divisions"
    t0 = time.time()
    con.execute(
        f"""CREATE TABLE d AS SELECT id, names.primary AS name, subtype, country, population,
                   parent_division_id
            FROM read_parquet('{base}/type=division/*', hive_partitioning = false)"""
    )
    print(
        f"  divisions: {con.execute('SELECT count(*) FROM d').fetchone()[0]:,} in {time.time() - t0:.0f} s",
        flush=True,
    )
    levels = ", ".join(f"('{k}', '{v}')" for k, v in SUBTYPE_LEVEL.items())
    con.execute(f"CREATE TABLE lv(subtype VARCHAR, level VARCHAR); INSERT INTO lv VALUES {levels}")
    t0 = time.time()
    con.execute(
        f"""CREATE TABLE a AS SELECT a.division_id, a.subtype, a.country, a.geometry
            FROM read_parquet('{base}/type=division_area/*', hive_partitioning = false) a
            WHERE a.subtype IN (SELECT subtype FROM lv) AND a.class = 'land'"""
    )
    n = con.execute("SELECT count(*) FROM a").fetchone()[0]
    print(
        f"  division areas (land, below the country): {n:,} in {time.time() - t0:.0f} s", flush=True
    )
    lk = lake(
        args,
        f"Overture Maps divisions, release {rel}",
        "ODbL 1.0 (OSM); CC BY 4.0 (geoBoundaries, Esri Community Maps)",
        rel,
    )
    q = """SELECT d.id, d.name, lv.level, a.subtype, i.iso3, p.name AS parent_name,
                  d.population::DOUBLE AS population, a.geometry
           FROM a JOIN d ON d.id = a.division_id JOIN lv ON lv.subtype = a.subtype
           LEFT JOIN d p ON p.id = d.parent_division_id
           LEFT JOIN iso_codes i ON i.iso2 = a.country"""
    for (iso3,) in con.execute(
        "SELECT DISTINCT i.iso3 FROM a LEFT JOIN iso_codes i ON i.iso2 = a.country ORDER BY 1"
    ).fetchall():
        part = "XXX" if iso3 is None else iso3
        cond = "i.iso3 IS NULL" if iso3 is None else f"i.iso3 = '{iso3}'"
        write(lk, con, "divisions", f"{q} WHERE {cond}", partition={"iso3": part})
    w.lake_done(lk, args.upload)


def adm2(args: argparse.Namespace) -> None:
    src = w.download(CGAZ2, TMP / "cgaz_adm2.geojson")
    con = con_spatial()
    lk = lake(args, "geoBoundaries CGAZ ADM2", "CC BY 4.0")
    write(
        lk, con, "adm2",
        f"""SELECT shapeID AS id, shapeName AS name, 'admin2' AS level, 'ADM2' AS subtype,
                   shapeGroup AS iso3, NULL::VARCHAR AS parent_name, NULL::DOUBLE AS population, geom AS geometry
            FROM ST_Read('{src}')""",
    )  # fmt: skip
    w.lake_done(lk, args.upload)


def us(args: argparse.Namespace) -> None:
    con = con_spatial()
    states = ", ".join(f"('{k}', '{v.replace(chr(39), chr(39) * 2)}')" for k, v in STATES.items())
    con.execute(f"CREATE TABLE st(fp VARCHAR, name VARCHAR); INSERT INTO st VALUES {states}")
    lk = lake(
        args, "US Census Bureau cartographic boundary files 2024 (1:500,000)", "public domain"
    )
    for kind, table, level, name in (
        ("place", "us_places", "us_place", "NAMELSAD"),
        ("cousub", "us_cousub", "us_cousub", "NAMELSAD"),
        ("tract", "us_tracts", "us_tract", "NAMELSAD"),
    ):
        z = w.download(TIGER.format(kind), TMP / f"cb_2024_us_{kind}_500k.zip")
        shp = next(w.unzip(z).glob("*.shp"))
        write(
            lk, con, table,
            f"""SELECT t.GEOID AS id, t.{name} AS name, '{level}' AS level, t.LSAD AS subtype,
                       'USA' AS iso3, st.name AS parent_name, NULL::DOUBLE AS population, t.geom AS geometry
                FROM ST_Read('{shp}') t LEFT JOIN st ON st.fp = t.STATEFP""",
        )  # fmt: skip
    w.lake_done(lk, args.upload)


def arcgis_geojson(service: str, out: Path) -> Path:
    """Every feature of an ONS ArcGIS layer as one GeoJSON file (paged, 2,000 per request)."""
    if out.exists():
        return out
    feats, offset = [], 0
    name, _, layer = service.partition(":")
    while True:
        url = (
            f"{ONS}/{name}/FeatureServer/{layer or 0}/query?where=1%3D1&outFields=*&outSR=4326&f=geojson"
            f"&resultOffset={offset}&resultRecordCount=2000"
        )
        page = w.get_json(url, timeout=300)
        got = page.get("features", [])  # type: ignore[union-attr]
        feats += got
        if len(got) < 2000:
            break
        offset += len(got)
    out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    print(f"  {service}: {len(feats):,} features", flush=True)
    return out


def uk(args: argparse.Namespace) -> None:
    con = con_spatial()
    lk = lake(args, "ONS Open Geography; Scottish Government; NISRA", "OGL v3")
    parts = []
    for level, (service, cd, nm) in UK_LAYERS.items():
        try:
            f = arcgis_geojson(service, TMP / f"{service.split(':')[0]}.geojson")
        except SystemExit as e:  # one layer that fails is named; the others build
            print(f"  {level} ({service}): not built ({e})", flush=True)
            continue
        parts.append(
            f"""SELECT {cd} AS id, {nm} AS name, '{level}' AS level, '{service}' AS subtype, 'GBR' AS iso3,
                       NULL::VARCHAR AS parent_name, NULL::DOUBLE AS population, geom AS geometry FROM ST_Read('{f}')"""
        )  # fmt: skip
    for url, level, cd, nm, label in (
        (SCOT_DZ, "data_zone", "dzcode", "dzname", "Scottish data zones 2022"),
        (NI_SDZ, "super_data_zone", "SDZ2021_cd", "SDZ2021_nm", "NI super data zones 2021"),
    ):
        try:
            shp = next(w.unzip(w.download(url, TMP / Path(url).name)).rglob("*.shp"))
            cols = {
                c[0].lower(): c[0]
                for c in con.execute(f"DESCRIBE SELECT * FROM ST_Read('{shp}')").fetchall()
            }
            parts.append(
                f"""SELECT "{cols[cd.lower()]}" AS id, "{cols[nm.lower()]}" AS name, '{level}' AS level, '{label}' AS subtype,
                           'GBR' AS iso3, NULL::VARCHAR AS parent_name, NULL::DOUBLE AS population,
                           ST_Transform(geom, 'EPSG:27700', 'EPSG:4326') AS geometry FROM ST_Read('{shp}')"""
            )  # fmt: skip
        except (SystemExit, KeyError, StopIteration, duckdb.Error) as e:
            print(f"  {label}: not built ({e})", flush=True)
    write(lk, con, "uk_ons", " UNION ALL ".join(parts))
    w.lake_done(lk, args.upload)


def fr(args: argparse.Namespace) -> None:
    src = w.download(IRIS, TMP / "contours_iris_2025.parquet")
    con = con_spatial()
    cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{src}')").fetchall()]
    print(f"  IRIS columns: {cols}", flush=True)
    code = next(c for c in cols if c.lower() in ("code_iris", "iris_code", "code_iris_2025"))
    name = next(c for c in cols if c.lower() in ("nom_iris", "iris_name"))
    com = next(c for c in cols if c.lower() in ("code_insee", "insee_com", "code_commune"))
    cname = next(c for c in cols if c.lower() in ("nom_commune", "nom_com"))
    geom = next(c for c in cols if c.lower() in ("geometry", "geom", "the_geom", "geometrie"))
    # GeoParquet with native (GeoArrow) multipolygons: rebuilt as GEOMETRY through GeoJSON
    native = "list_transform(p, r -> list_transform(r, q -> [q.x, q.y]))"
    con.execute(
        f"CREATE TABLE iris AS SELECT * EXCLUDE ({geom}), ST_GeomFromGeoJSON(json_object('type', "
        f"'MultiPolygon', 'coordinates', list_transform({geom}, p -> {native}))) AS {geom} "
        f"FROM read_parquet('{src}')"
    )
    lk = lake(args, "IGN / INSEE Contours IRIS 2025", "Licence Ouverte 2.0")
    write(
        lk, con, "fr_iris",
        f"""SELECT {code} AS id, {name} AS name, 'iris' AS level, 'IRIS' AS subtype, 'FRA' AS iso3,
                   {cname} AS parent_name, NULL::DOUBLE AS population, {geom} AS geometry FROM iris
            UNION ALL
            SELECT {com} AS id, any_value({cname}) AS name, 'fr_commune' AS level,
                   'commune (union of its IRIS, computed)' AS subtype, 'FRA', NULL, NULL,
                   ST_Union_Agg({geom}) FROM iris GROUP BY {com}""",
    )  # fmt: skip
    w.lake_done(lk, args.upload)


def ogc_items(collection: str, out: Path) -> Path:
    if out.exists():
        return out
    feats = []
    url: str | None = f"{PDOK}/{collection}/items?f=json&limit=1000"
    while url:
        page = w.get_json(url, timeout=300)
        feats += page.get("features", [])  # type: ignore[union-attr]
        url = next((ln["href"] for ln in page.get("links", []) if ln.get("rel") == "next"), None)  # type: ignore[union-attr]
    out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    print(f"  CBS {collection}: {len(feats):,}", flush=True)
    return out


def nl(args: argparse.Namespace) -> None:
    con = con_spatial()
    lk = lake(args, "CBS Wijk- en buurtkaart 2024 (PDOK)", "CC BY 4.0", "2024")
    parts = []
    for coll, level, cd, nm, parent in (
        ("gemeenten", "nl_gemeente", "gemeentecode", "gemeentenaam", "NULL"),
        ("wijken", "nl_wijk", "wijkcode", "wijknaam", "gemeentenaam"),
        ("buurten", "nl_buurt", "buurtcode", "buurtnaam", "gemeentenaam"),
    ):
        f = ogc_items(coll, TMP / f"cbs_{coll}.geojson")
        pop = "aantal_inwoners"
        parts.append(
            f"""SELECT {cd} AS id, {nm} AS name, '{level}' AS level, '{coll}' AS subtype, 'NLD' AS iso3,
                       {parent} AS parent_name, TRY_CAST({pop} AS DOUBLE) AS population, geom AS geometry
                FROM ST_Read('{f}') WHERE water IS NULL OR water = 'NEE'"""
        )  # fmt: skip
    write(lk, con, "nl_cbs", " UNION ALL ".join(parts))
    w.lake_done(lk, args.upload)


def ucdb(args: argparse.Namespace) -> None:
    folder = w.unzip(w.download(UCDB, TMP / "ucdb.zip"))
    gpkg = next(folder.rglob("*.gpkg"))
    con = con_spatial()
    layers = [
        r[0]
        for r in con.execute(
            f"SELECT l.name FROM (SELECT unnest(layers) AS l FROM ST_Read_Meta('{gpkg}'))"
        ).fetchall()
    ]  # noqa: E501
    print(f"  UCDB layers: {layers[:12]}", flush=True)
    layer = next(x for x in layers if "general" in x.lower() or "GHS_UCDB_THEME_GENERAL" in x)
    cols = [
        c[0]
        for c in con.execute(
            f"DESCRIBE SELECT * FROM ST_Read('{gpkg}', layer = '{layer}')"
        ).fetchall()
    ]
    # the columns' names start with a byte-order mark in R2024A
    pick = lambda *names: '"' + next(c for c in cols if c.lstrip("\ufeff") in names) + '"'  # noqa: E731
    cid, cname = pick("ID_UC_G0"), pick("GC_UCN_MAI_2025", "GC_UCN_MAI_2020")
    ciso, cpop = (
        pick("GC_CNT_GAD_2025", "GC_CNT_GAD_2020"),
        pick("GC_POP_TOT_2025", "GC_POP_TOT_2020"),
    )
    lk = lake(args, "GHS Urban Centre Database R2024A V1.1", "CC BY 4.0", "R2024A V1.1")
    write(
        lk, con, "urban_centres",
        f"""SELECT replace(CAST({cid} AS VARCHAR), chr(65279), '') AS id, replace({cname}, chr(65279), '') AS name, 'urban_centre' AS level, 'urban centre' AS subtype,
                   i.iso3, NULL::VARCHAR AS parent_name, {cpop}::DOUBLE AS population,
                   ST_Transform(geom, 'ESRI:54009', 'EPSG:4326') AS geometry
            FROM ST_Read('{gpkg}', layer = '{layer}') LEFT JOIN iso_codes i ON lower(i.name) = lower(replace({ciso}, chr(65279), ''))""",
    )  # fmt: skip
    w.lake_done(lk, args.upload)


def grid(args: argparse.Namespace) -> None:
    folder = w.unzip(w.download(GEOSTAT, TMP / "geostat_2021.zip"))
    gpkg = next(iter(folder.rglob("*.gpkg")), None)
    con = con_spatial()
    src = f"ST_Read('{gpkg}')" if gpkg else f"read_csv('{next(folder.rglob('*.csv'))}')"
    cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()]
    print(f"  GEOSTAT columns: {cols}", flush=True)
    gid = next(c for c in cols if c.upper() in ("GRD_ID", "GRD_NEWID"))
    pop = next(c for c in cols if c.upper() in ("T", "OBS_VALUE_T", "TOT_P"))
    ctry = next((c for c in cols if c.upper() in ("CNTR_ID", "COUNTRY")), None)
    # GRD_ID "CRS3035RES1000mN2684000E4334000": the cell's south-west corner in EPSG:3035
    lk = lake(
        args,
        "Eurostat Census 2021 population grid (GEOSTAT), 1 km",
        "Eurostat reuse policy (CC BY 4.0)",
        "V2.2",
    )
    write(
        lk, con, "geostat_grid",
        f"""WITH g AS (SELECT {gid} AS id, {pop}::DOUBLE AS population, {ctry or 'NULL'} AS ctry,
                       CAST(regexp_extract({gid}, 'N([0-9]+)', 1) AS DOUBLE) AS n,
                       CAST(regexp_extract({gid}, 'E([0-9]+)', 1) AS DOUBLE) AS e FROM {src})
            SELECT id, id AS name, 'grid_1km' AS level, 'GEOSTAT 1 km cell' AS subtype, i.iso3,
                   NULL::VARCHAR AS parent_name, population,
                   ST_Transform(ST_MakeEnvelope(e, n, e + 1000, n + 1000), 'EPSG:3035', 'EPSG:4326') AS geometry
            FROM g LEFT JOIN iso_codes i ON i.iso2 = g.ctry WHERE population > 0""",
    )  # fmt: skip
    w.lake_done(lk, args.upload)


# national census small areas found open (docs/research/small-area-energy.md): one row per set
NATIONAL: list[dict[str, str]] = [
    {
        "iso3": "BEL", "level": "be_sector", "label": "Statbel statistical sectors 2024",
        "url": "https://statbel.fgov.be/sites/default/files/files/opendata/Statistische%20sectoren/sh_statbel_statistical_sectors_31370_20240101.geojson.zip",
        "id": "cd_sector", "name": "tx_sector_descr_nl", "crs": "EPSG:31370", "licence": "Licence Ouverte (Statbel open data)",
    },
    {
        "iso3": "IRL", "level": "ie_small_area", "label": "CSO / Tailte Éireann Small Areas 2022 (generalised 20 m)",
        "url": "https://data-osi.opendata.arcgis.com/api/download/v1/items/9472cff586d74f2ba3c240d4344c5720/geojson?layers=0",
        "id": "SA_GEOGID_2022", "name": "ED_ENGLISH", "crs": "EPSG:4326", "licence": "CC BY 4.0",
    },
    {
        "iso3": "SWE", "level": "se_deso", "label": "SCB DeSO 2025 (demographic statistical areas)",
        "url": "https://geodata.scb.se/geoserver/stat/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=stat:DeSO_2025&outputFormat=application/json&srsName=EPSG:4326",
        "id": "desokod", "name": "desokod", "crs": "EPSG:4326", "licence": "CC0 (SCB open geodata)",
    },
]  # fmt: skip


def national(args: argparse.Namespace) -> None:
    con = con_spatial()
    lk = lake(
        args,
        "national census small areas (see each row's subtype)",
        "per set: docs/research/small-area-energy.md",
    )
    parts = []
    for s in NATIONAL:
        try:
            dest = TMP / f"{s['level']}{'.zip' if s['url'].endswith('.zip') else '.geojson'}"
            f = w.download(s["url"], dest)
            if f.suffix == ".zip":
                f = next(
                    p
                    for p in w.unzip(f).rglob("*")
                    if p.suffix.lower() in (".geojson", ".json", ".shp", ".gpkg")
                )
            cols = {
                c[0].lower(): c[0]
                for c in con.execute(f"DESCRIBE SELECT * FROM ST_Read('{f}')").fetchall()
            }
            geom = (
                "ST_GeomFromWKB(ST_AsWKB(geom))"
                if s["crs"] == "EPSG:4326"
                else f"ST_GeomFromWKB(ST_AsWKB(ST_Transform(geom, '{s['crs']}', 'EPSG:4326')))"
            )
            parts.append(
                f"""SELECT CAST("{cols[s['id'].lower()]}" AS VARCHAR) AS id, CAST("{cols[s['name'].lower()]}" AS VARCHAR) AS name,
                           '{s['level']}' AS level, '{s['label']} ({s['licence']})' AS subtype, '{s['iso3']}' AS iso3,
                           NULL::VARCHAR AS parent_name, NULL::DOUBLE AS population, {geom} AS geometry
                    FROM ST_Read('{f}')"""
            )  # fmt: skip
            print(f"  {s['label']}: read", flush=True)
        except (SystemExit, KeyError, StopIteration, duckdb.Error) as e:
            print(f"  {s['label']}: not built ({type(e).__name__}: {str(e)[:200]})", flush=True)
    if parts:
        write(lk, con, "small_areas", " UNION ALL ".join(parts))
        w.lake_done(lk, args.upload)


def names(args: argparse.Namespace) -> None:
    """The search index: every outline's name, level, country, parent, population and box."""
    con = con_spatial()
    root = Path(args.lake) / "outlines"
    parts = []
    for t in sorted(
        p for p in root.iterdir() if p.is_dir() and p.name != "names" and any(p.rglob("*.parquet"))
    ):
        parts.append(
            f"""SELECT '{t.name}' AS "set", id, name, level, subtype, iso3, parent_name, population,
                       bbox.xmin AS xmin, bbox.ymin AS ymin, bbox.xmax AS xmax, bbox.ymax AS ymax
                FROM read_parquet('{t}/**/*.parquet', hive_partitioning = false)"""
        )
    lk = lake(args, "search index over the outline sets", "as each set")
    lk.write(con, "names", " UNION ALL ".join(parts), sort=["name"], bloom=["name"])
    w.lake_done(lk, args.upload)


SETS = {
    "divisions": divisions, "adm2": adm2, "us": us, "uk": uk, "fr": fr, "nl": nl,
    "ucdb": ucdb, "grid": grid, "national": national, "names": names,
}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=[*SETS, "all"])
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    TMP.mkdir(parents=True, exist_ok=True)
    for name in SETS if args.what == "all" else [args.what]:
        print(f"== {name}", flush=True)
        SETS[name](args)


if __name__ == "__main__":
    main()
