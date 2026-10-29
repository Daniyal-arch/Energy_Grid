"""Asset layers of data wave 8 (docs/tasks/27, B4) -> lake tables and small app files.

    python scripts/build_assets_w8.py eea|ownership|dams|co2stop|hotmaps|fires|tri|ukpi|all
        [--lake lake-out] [--upload]

eea        EEA Industrial Reporting v15 (2007-2023; E-PRTR, LCP, EU Registry; CC BY 4.0): the
           user-friendly CSVs (air and water releases per facility, LCP fuel input and emissions,
           IED installations) -> lake `industrial/*`; facilities with their newest reported
           releases -> frontend/public/data/eu/w8/industrial.json; refineries (E-PRTR activity
           1(a)) are the EU "oil and gas facilities" family.
ownership  GEM Global Energy Ownership Tracker (CC BY 4.0) from the private bucket (the GEM
           workflow downloads it through GEM's form) -> lake `gem_ownership/*` (licensed: the
           SQL guard returns aggregates only, as for every GEM table).
dams       Global Dam Watch v1.0 (CC BY 4.0, figshare 25988293, 70 MB) -> lake `dams/*` and
           frontend/public/data/eu/w8/dams.json (barriers with a reservoir or a height).
co2stop    CO2StoP (JRC, SETIS; "reuse authorised, provided the source is acknowledged"), the
           open-formats zip -> lake `co2stop/*`, w8/co2storage.json (storage units, vintage shown).
hotmaps    Hotmaps (CC BY 4.0): heat demand density 100 m (EU28) -> COG lake/rasters/
           hotmaps_heat_density_100m.tif (area_stats measure `heat_demand`); industrial sites with
           excess heat -> lake `hotmaps/industrial_sites`, w8/excess_heat.json.
fires      NIFC WFIGS current interagency perimeters (US, public domain) and, with FIRMS_MAP_KEY,
           NASA FIRMS VIIRS detections of the last 24 h over the EU-27, the UK and the US ->
           w8/fires.json; transmission lines within 4.8 km (WECC's 3 miles) of a detection are
           counted (computed) in the agent's tables, not here.
tri        EPA Toxics Release Inventory, newest basic data file (public domain) -> lake `tri/*`.
ukpi       Environment Agency Pollution Inventory (England, OGL v3) -> lake `uk_pi/*`.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import duckdb
import httpx
import wave5_common as w

TMP = Path("/tmp/wave8/assets")
SCRIPT = "scripts/build_assets_w8.py"
APP = w.EU / "w8"
EEA = "https://sdi.eea.europa.eu/datashare/public.php/webdav/User-friendly-CSV/{}.csv"
EEA_TOKEN = "gN8jayNx7igxeMf"  # the public share of record 3461f4ab (v15), not a secret
GDW = "https://ndownloader.figshare.com/files/47913754"
CO2STOP = "https://setis.ec.europa.eu/document/download/786a884f-0b33-4789-b744-28004b16bd1a_en?filename=co2jrc_openformats.zip"
HOTMAPS_TIF = "https://gitlab.com/hotmaps/heat/heat_tot_curr_density/-/raw/master/data/heat_tot_curr_density.tif"
HOTMAPS_SITES = "https://gitlab.com/hotmaps/industrial_sites/industrial_sites_Industrial_Database/-/raw/master/data/Industrial_Database.csv"
NIFC = "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0/query"
BOXES = "-32,27,45,72;-180,17,-64,72"


def con_spatial() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    con.execute("SET geometry_always_xy = true")
    return con


def first_col(con: duckdb.DuckDBPyConnection, table: str = "t") -> str:
    return '"' + con.execute(f"DESCRIBE {table}").fetchone()[0] + '"'


def app_file(name: str, payload: dict, max_mb: float = 5.0) -> None:
    w.write_json(APP / f"{name}.json", {"fetched": w.now(), **payload}, max_mb=max_mb)


# ---------------------------------------------------------------------- EEA Industrial Reporting


def eea(args: argparse.Namespace) -> None:
    con = con_spatial()
    files = {
        "air_releases": "F1_4_Air_Releases_Facilities",
        "water_releases": "F2_4_Water_Releases_Facilities",
        "lcp": "F5_2_LCP_Energy_Emissions",
        "installations": "F6_1_IED_Installations",
    }
    lk = w.lake_for(
        "industrial",
        args.lake,
        "EEA Industrial Reporting database v15 (2007-2023), user-friendly CSV",
        "CC BY 4.0 (EEA)",
        SCRIPT,
        "v15 2025-12-15",
    )
    for table, name in files.items():
        f = w.download(EEA.format(name), TMP / f"{name}.csv", auth=(EEA_TOKEN, ""), timeout=1800)
        con.execute(
            f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv('{f}', header = true, all_varchar = false, sample_size = -1)"
        )
        n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {n:,} rows", flush=True)
        lk.write(con, table, f"SELECT * FROM {table}", sort=["reportingYear"], bloom=[])
    # facilities: the newest reported year's releases to air (kg), with position and activity
    rows = con.execute(
        """WITH last AS (SELECT FacilityInspireId, max(reportingYear) AS y FROM air_releases GROUP BY 1)
           SELECT a.Longitude, a.Latitude, any_value(a.facilityName), any_value(a.countryName),
                  any_value(a.EPRTRAnnexIMainActivity), any_value(a.EPRTR_SectorName), a.reportingYear,
                  sum(CASE WHEN a.Pollutant LIKE 'Carbon dioxide (CO2)%' THEN a.Releases END) AS co2_kg,
                  count(*) AS pollutants
           FROM air_releases a JOIN last l ON l.FacilityInspireId = a.FacilityInspireId AND l.y = a.reportingYear
           WHERE a.Longitude IS NOT NULL AND a.Latitude IS NOT NULL
           GROUP BY a.FacilityInspireId, a.Longitude, a.Latitude, a.reportingYear"""
    ).fetchall()
    points = [
        [
            round(lon, 5),
            round(lat, 5),
            name,
            country,
            act,
            sector,
            y,
            round(co2) if co2 else None,
            n,
        ]
        for lon, lat, name, country, act, sector, y, co2, n in rows
    ]
    refineries = sum(1 for p in points if str(p[4]).startswith("1(a)"))
    app_file(
        "industrial",
        {
            "source": "EEA Industrial Reporting database v15 (E-PRTR, 2007-2023), CC BY 4.0",
            "fields": [
                "lon",
                "lat",
                "name",
                "country",
                "eprtr_activity",
                "sector",
                "year",
                "co2_kg",
                "pollutants_reported",
            ],
            "how": "every facility reporting releases to air, its newest reporting year; co2_kg as reported (kg)",
            "points": points,
        },
        max_mb=8,
    )
    print(
        f"  facilities on the map: {len(points):,} ({refineries} refineries, activity 1(a))",
        flush=True,
    )
    w.lake_done(lk, args.upload)


# ---------------------------------------------------------------------- GEM ownership


def ownership(args: argparse.Namespace) -> None:
    import lake as lakemod

    dest = TMP / "energy-ownership-tracker.xlsx"
    if not dest.exists() and not lakemod.wrangler(
        "r2",
        "object",
        "get",
        "infraatlas-raw/gem/energy-ownership/energy-ownership-tracker.xlsx",
        "--file",
        str(dest),
        "--remote",
    ):
        raise SystemExit("GEM ownership file not in the private bucket (run the GEM workflow)")
    import openpyxl

    wb = openpyxl.load_workbook(dest, read_only=True, data_only=True)
    con = duckdb.connect()
    lk = w.lake_for(
        "gem_ownership",
        args.lake,
        "GEM Global Energy Ownership Tracker",
        "CC BY 4.0 (Global Energy Monitor)",
        SCRIPT,
    )
    for ws in wb.worksheets:
        it = ws.iter_rows(values_only=True)
        header = next(it, None)
        if not header or sum(1 for h in header if h) < 3:
            continue
        cols = [str(h or f"col{i}").strip() for i, h in enumerate(header)]
        path = TMP / f"own_{ws.title}.csv"
        import csv

        with path.open("w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f)
            wr.writerow(cols)
            n = 0
            for r in it:
                wr.writerow(["" if v is None else v for v in r])
                n += 1
        table = "".join(ch if ch.isalnum() else "_" for ch in ws.title.lower()).strip("_")
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_csv('{path}', header = true, all_varchar = true)"
        )
        lk.write(con, table, "SELECT * FROM t", sort=[f'"{cols[0]}"'])
        print(f"  ownership sheet {ws.title}: {n:,} rows -> gem_ownership/{table}", flush=True)
    w.lake_done(lk, args.upload)


# ---------------------------------------------------------------------- dams, CO2 storage


def dams(args: argparse.Namespace) -> None:
    folder = w.unzip(w.download(GDW, TMP / "GDW_v1_0_shp.zip"))
    con = con_spatial()
    lk = w.lake_for(
        "dams", args.lake, "Global Dam Watch v1.0 (figshare 25988293)", "CC BY 4.0", SCRIPT, "v1.0"
    )
    for shp in sorted(folder.rglob("*.shp")):
        table = (
            "barriers"
            if "barrier" in shp.name.lower()
            else "reservoirs"
            if "res" in shp.name.lower()
            else shp.stem.lower()
        )
        con.execute(
            f"CREATE OR REPLACE TABLE {table} AS SELECT * EXCLUDE (geom), ST_GeomFromWKB(ST_AsWKB(geom)) AS geometry FROM ST_Read('{shp}')"
        )
        n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {n:,} rows ({shp.name})", flush=True)
        lk.write(
            con, table, f"SELECT * FROM {table}", sort=[lakemod_hilbert()], geometry="geometry"
        )
        if table == "barriers":
            cols = [c[0] for c in con.execute(f"DESCRIBE {table}").fetchall()]
            pick = lambda *xs: next((c for c in cols if c.upper() in xs), None)  # noqa: E731
            name, height, cap, year, use = (
                pick("DAM_NAME", "NAME"),
                pick("DAM_HGT_M", "HEIGHT"),
                pick("CAP_MCM", "CAPACITY"),
                pick("YEAR_DAM", "YEAR"),
                pick("MAIN_USE", "USE"),
            )
            rows = con.execute(
                f"""SELECT round(ST_X(ST_Centroid(geometry)), 4), round(ST_Y(ST_Centroid(geometry)), 4),
                           {name or "NULL"}, {height or "NULL"}, {cap or "NULL"}, {year or "NULL"}, {use or "NULL"}
                    FROM {table}"""
            ).fetchall()
            app_file(
                "dams",
                {
                    "source": "Global Dam Watch v1.0 (CC BY 4.0)",
                    "fields": [
                        "lon",
                        "lat",
                        "name",
                        "height_m",
                        "capacity_mcm",
                        "year",
                        "main_use",
                    ],
                    "how": "every barrier as published (no filter)",
                    "points": [list(r) for r in rows],
                },
                max_mb=8,
            )
    w.lake_done(lk, args.upload)


def lakemod_hilbert() -> str:
    import lake as lakemod

    return lakemod.hilbert("geometry")


def co2stop(args: argparse.Namespace) -> None:
    folder = w.unzip(w.download(CO2STOP, TMP / "co2jrc_openformats.zip"))
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    print(f"  CO2StoP files: {[p.name for p in files][:30]}", flush=True)
    con = con_spatial()
    lk = w.lake_for(
        "co2stop",
        args.lake,
        "CO2StoP, European CO2 storage database (JRC, SETIS), open formats",
        "reuse authorised, provided the source is acknowledged (JRC)",
        SCRIPT,
        "2013 (open formats 2020)",
    )
    # the database's own tables; its user list and test exports are left out (personal data)
    skip = ("user_details", "test_exporteddata", "uuid_audit")
    for csvf in [p for p in files if p.suffix.lower() == ".csv" and p.stem.lower() not in skip]:
        table = "".join(ch if ch.isalnum() else "_" for ch in csvf.stem.lower()).strip("_")
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_csv('{csvf}', header = true, all_varchar = true, ignore_errors = true)"
        )
        lk.write(con, table, "SELECT * FROM t", sort=[first_col(con)])
        print(
            f"  {table}: {con.execute('SELECT count(*) FROM t').fetchone()[0]:,} rows", flush=True
        )
    pts = []
    for kml in [p for p in files if p.suffix.lower() == ".kml"]:
        try:
            rows = con.execute(
                f"SELECT * EXCLUDE (geom), ST_X(ST_Centroid(geom)), ST_Y(ST_Centroid(geom)) FROM ST_Read('{kml}')"
            ).fetchall()
        except duckdb.Error as e:
            print(f"  {kml.name}: {e}", flush=True)
            continue
        for r in rows:
            pts.append([round(r[-2], 4), round(r[-1], 4), str(r[0])[:80], kml.stem])
    app_file(
        "co2storage",
        {
            "source": "CO2StoP (JRC, SETIS), assessments of about 2013; reuse authorised with acknowledgement",
            "fields": ["lon", "lat", "name", "kind"],
            "how": "storage units and traps as published (KML centroids, computed for the map); the vintage is the 2013 assessment",
            "points": pts,
        },
    )
    w.lake_done(lk, args.upload)


# ---------------------------------------------------------------------- Hotmaps


def hotmaps(args: argparse.Namespace) -> None:
    import subprocess

    tif = w.download(HOTMAPS_TIF, TMP / "heat_tot_curr_density.tif", timeout=3600)
    cog = TMP / "hotmaps_heat_density_100m.tif"
    subprocess.run(
        [
            "gdal_translate",
            "-of",
            "COG",
            "-co",
            "COMPRESS=ZSTD",
            "-co",
            "BIGTIFF=YES",
            "-co",
            "NUM_THREADS=ALL_CPUS",
            str(tif),
            str(cog),
        ],
        check=True,
    )
    print(f"  heat density COG: {cog.stat().st_size / 1e6:,.0f} MB", flush=True)
    if args.upload:
        subprocess.run(
            [
                "aws",
                "s3",
                "cp",
                "--only-show-errors",
                "--endpoint-url",
                f"https://{w.env('CLOUDFLARE_ACCOUNT_ID')}.r2.cloudflarestorage.com",
                str(cog),
                f"s3://infraatlas-raw/lake/rasters/{cog.name}",
            ],
            check=True,
        )
    sites = w.download(HOTMAPS_SITES, TMP / "Industrial_Database.csv")
    con = con_spatial()
    con.execute(
        f"CREATE TABLE s AS SELECT * FROM read_csv('{sites}', header = true, all_varchar = true, ignore_errors = true)"
    )
    cols = [c[0] for c in con.execute("DESCRIBE s").fetchall()]
    print(f"  Hotmaps industrial sites columns: {cols}", flush=True)
    lk = w.lake_for(
        "hotmaps",
        args.lake,
        "Hotmaps industrial sites (Industrial Database)",
        "CC BY 4.0 (Hotmaps project)",
        SCRIPT,
    )
    lk.write(con, "industrial_sites", "SELECT * FROM s", sort=[first_col(con, "s")])
    geom = next((c for c in cols if c.lower() in ("geom", "geometry", "wkt")), None)
    exc = [c for c in cols if "excess" in c.lower()]
    if geom:
        rows = con.execute(
            f"""SELECT ST_X(g), ST_Y(g), {", ".join(f'"{c}"' for c in (["SiteName"] if "SiteName" in cols else cols[:1]))}, {", ".join(f'TRY_CAST("{c}" AS DOUBLE)' for c in exc[:3]) or "NULL"}
                FROM (SELECT *, TRY(ST_GeomFromText(regexp_replace("{geom}", '^SRID=\\d+;', ''))) AS g FROM s) WHERE g IS NOT NULL"""
        ).fetchall()
        app_file(
            "excess_heat",
            {
                "source": "Hotmaps Industrial Database (CC BY 4.0)",
                "fields": ["lon", "lat", "name", *[c for c in exc[:3]]],
                "how": "industrial sites with their excess heat as published (GWh a year by temperature level)",
                "points": [[round(r[0], 4), round(r[1], 4), *r[2:]] for r in rows],
            },
        )
    w.lake_done(lk, args.upload)


# ---------------------------------------------------------------------- fires


def fires(args: argparse.Namespace) -> None:
    from shapely.geometry import shape

    out: dict = {"source": [], "perimeters": [], "detections": [], "skipped": []}
    r = httpx.get(
        NIFC,
        params={
            "where": "1=1",
            "outFields": "poly_IncidentName,attr_IncidentSize,poly_GISAcres,attr_FireDiscoveryDateTime",
            "outSR": "4326",
            "f": "geojson",
        },
        timeout=300,
    )
    r.raise_for_status()
    for f in r.json().get("features", []):
        p = f["properties"]
        out["perimeters"].append(
            {
                "name": p.get("poly_IncidentName"),
                "acres": p.get("poly_GISAcres"),
                "discovered": p.get("attr_FireDiscoveryDateTime"),
                "rings": w.rings(shape(f["geometry"]).simplify(0.001), 4)
                if f.get("geometry")
                else [],
            }
        )
    out["source"].append("NIFC WFIGS current interagency fire perimeters (public domain)")
    key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if key:
        for box in BOXES.split(";"):
            rr = httpx.get(
                f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{box}/1",
                timeout=300,
            )
            lines = rr.text.splitlines()
            head = lines[0].split(",") if lines else []
            for ln in lines[1:]:
                v = dict(zip(head, ln.split(","), strict=False))
                out["detections"].append(
                    [
                        float(v["longitude"]),
                        float(v["latitude"]),
                        v.get("acq_date"),
                        v.get("acq_time"),
                        v.get("frp"),
                        v.get("confidence"),
                    ]
                )
        out["source"].append("NASA FIRMS VIIRS S-NPP NRT, last 24 h (NASA open data)")
    else:
        out["skipped"].append(
            "NASA FIRMS: FIRMS_MAP_KEY is not set (free key: https://firms.modaps.eosdis.nasa.gov/api/map_key/)"
        )
        print("  FIRMS skipped: FIRMS_MAP_KEY is not set", flush=True)
    out["source"] = "; ".join(out["source"])
    app_file("fires", out)
    print(
        f"  fires: {len(out['perimeters'])} perimeters, {len(out['detections'])} detections",
        flush=True,
    )


# ---------------------------------------------------------------------- EPA TRI, EA Pollution Inventory


def tri(args: argparse.Namespace) -> None:
    con = duckdb.connect()
    lk = w.lake_for(
        "tri",
        args.lake,
        "EPA Toxics Release Inventory, basic data files",
        "public domain (US EPA)",
        SCRIPT,
    )
    for year in range(time.gmtime().tm_year - 1, time.gmtime().tm_year - 4, -1):
        url = f"https://data.epa.gov/efservice/downloads/tri/mv_tri_basic_download/{year}_US/csv"
        try:
            f = w.download(url, TMP / f"tri_{year}.csv", timeout=1800, tries=2)
        except SystemExit as e:
            print(f"  TRI {year}: {e}", flush=True)
            continue
        con.execute(
            f"CREATE OR REPLACE TABLE t AS SELECT * FROM read_csv('{f}', header = true, all_varchar = true, ignore_errors = true)"
        )
        lk.write(
            con, "releases", "SELECT * FROM t", sort=[first_col(con)], partition={"year": str(year)}
        )
        print(
            f"  TRI {year}: {con.execute('SELECT count(*) FROM t').fetchone()[0]:,} rows",
            flush=True,
        )
        break
    w.lake_done(lk, args.upload)


def ukpi(args: argparse.Namespace) -> None:
    """The newest Pollution Inventory year: substances released per permitted site (England)."""
    import csv
    import zipfile

    import openpyxl

    meta = w.get_json(
        "https://ckan.publishing.service.gov.uk/api/action/package_show?id=cfd94301-a2f2-48a2-9915-e477ca6d8b7e"
    )
    res = [r for r in meta["result"]["resources"] if str(r.get("format", "")).lower() == "zip"]  # type: ignore[index]
    newest = max(res, key=lambda r: r.get("name", "")[:4])
    year = int(newest["name"][:4])
    print(f"  EA Pollution Inventory: {newest['name']} ({len(res)} years listed)", flush=True)
    z = w.download(newest["url"].replace(" ", "%20"), TMP / "ukpi.zip")
    out = TMP / "ukpi_substances.csv"
    with zipfile.ZipFile(z) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".xlsx"))
        (TMP / "ukpi.xlsx").write_bytes(zf.read(name))
    wb = openpyxl.load_workbook(TMP / "ukpi.xlsx", read_only=True, data_only=True)
    ws = next(s for s in wb.worksheets if "substances" in s.title.lower())
    n = 0
    with out.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        header = None
        for r in ws.iter_rows(values_only=True):
            if header is None:
                if r and r[0] and "PERMIT ID" in str(r[0]).upper():
                    header = [" ".join(str(c).split()).lower() for c in r if c is not None]
                    wr.writerow(header)
                continue
            if r and r[0]:
                wr.writerow(list(r[: len(header)]))
                n += 1
    print(f"  substances sheet: {n:,} rows", flush=True)
    con = con_spatial()
    con.execute(
        f"""CREATE TABLE t AS SELECT {year} AS year, *,
                ST_Transform(ST_Point(TRY_CAST(easting AS DOUBLE), TRY_CAST(northing AS DOUBLE)),
                             'EPSG:27700', 'EPSG:4326') AS geometry
            FROM read_csv('{out}', header = true, all_varchar = true)"""
    )
    lk = w.lake_for(
        "uk_pi",
        args.lake,
        "Environment Agency Pollution Inventory (England)",
        "Environment Agency conditional licence (commercial use allowed; attribution "
        "'Contains Environment Agency information © Environment Agency and/or database right')",
        SCRIPT,
    )
    lk.write(con, "releases", "SELECT * FROM t", sort=['"authorisation id / permit id"'])
    w.lake_done(lk, args.upload)


STEPS = {
    "eea": eea,
    "ownership": ownership,
    "dams": dams,
    "co2stop": co2stop,
    "hotmaps": hotmaps,
    "fires": fires,
    "tri": tri,
    "ukpi": ukpi,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=[*STEPS, "all"])
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    TMP.mkdir(parents=True, exist_ok=True)
    status = {}
    for name in STEPS if args.what == "all" else [args.what]:
        print(f"== {name}", flush=True)
        t0 = time.time()
        try:
            STEPS[name](args)
            status[name] = f"built in {time.time() - t0:.0f} s"
        except (SystemExit, Exception) as e:  # one failing step is named; the others build
            status[name] = f"failed: {type(e).__name__}: {str(e)[:300]}"
            print(f"  {name}: {status[name]}", flush=True)
    print(json.dumps(status, indent=1), flush=True)
    (TMP / "status.json").write_text(json.dumps(status, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
