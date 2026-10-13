"""The lake for the datasets the map already uses (docs/DATA_LAKE.md sections 6 and 7): full
detail as Parquet under lake/<dataset>/, written with scripts/lake.py, uploaded by workflows.

    python scripts/build_lake_datasets.py DATASET [--year Y | --recent N] --lake lake-out [--upload]

Datasets (the existing fetcher each reuses):
  entsog     ENTSOG physical flows per gas day, point, direction, operator (fetch_entsog.py);
             --year backfill, --recent rewrites the current year; `points` dimension
  eia930     EIA-930 hourly: demand (region-data), generation_by_fuel, interchange; `bas`
             (fetch_us.py, EIA_API_KEY); --year backfill (2015-07 onward), --recent
  eia860m    EIA-860M generators, every sheet, per monthly snapshot (fetch_us_grid.py)
  lbnl       LBNL Queued Up requests per yearly release (fetch_us_grid.py)
  irena      IRENASTAT capacity and generation, every country, technology, year (fetch_irena.py)
  jrc        JRC-PPDB-OPEN units (build_eu_units.py), powerplantmatching plants (fetch_eu_energy.py)
  gem        GEM trackers, one table per tracker, partition `release` (private licence;
             the files fetch_gem.py --pull-r2 copies to data/world/gem)
  osm        OpenStreetMap-derived snapshots: Europe's grid (PyPSA-Eur lines, buses, links),
             undersea cables, data centres (fetch_cables.py, fetch_world.py output files)
  euets      EU ETS: installations (snapshot), verified_emissions, eea_link (fetch_eu_ets.py)
  connect    NESO TEC register, Dutch capacity map, REE nodes, as snapshots (fetch_connect_here.py):
             lake/neso_tec/projects, lake/nl_capacity/areas, lake/ree_nodes/nodes

Every table carries the standard keys iso2, iso3, admin1 (where the source has them).
Values as published: columns keep the source's names (lower-cased, spaces to `_`) and the
types DuckDB reads from them; nothing is computed except the keys.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import httpx
import lake

ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "Europe-InfraAtlas/0.3 (data lake)"}


def snake(name: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", str(name).strip()).strip("_").lower()
    return s or "col"


def load_rows(con: duckdb.DuckDBPyConnection, name: str, rows: list[dict], tmp: Path) -> list[str]:
    """Rows (dicts, as published) into table `name` via CSV: DuckDB reads the types."""
    tmp.mkdir(parents=True, exist_ok=True)
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    names, seen = [], set()
    for c in cols:
        n = snake(c)
        while n in seen:
            n += "_"
        seen.add(n)
        names.append(n)
    path = tmp / f"{name}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(names)
        for r in rows:
            w.writerow(["" if r.get(c) is None else r.get(c) for c in cols])
    con.execute(
        f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_csv('{path}', header = true, "
        "sample_size = -1, max_line_size = 200000000, quote = '\"', escape = '\"')"
    )
    return names


def lake_for(
    dataset: str, root: Path, source: str, licence: str, script: str, version: str = ""
) -> lake.Lake:
    return lake.Lake(
        dataset, root, source=source, licence=licence, script=script, source_version=version
    )


def finish(lk: lake.Lake, upload: bool, merge: bool = False) -> dict:
    """Write the catalogue (merged into the uploaded one when `merge`) and upload."""
    if merge or upload:
        try:
            lk.pull_catalog()
        except SystemExit as e:
            print(f"  catalogue not pulled: {e}")
    path = lk.finish()
    if upload:
        lk.upload()
    cat = json.loads(path.read_text(encoding="utf-8"))
    for name, t in sorted(cat["tables"].items()):
        print(f"  {lk.dataset}/{name}: {t['rows']:,} rows, {t['bytes']:,} bytes")
    return cat


def old_files(lk: lake.Lake, table: str, partition: str, tmp: Path) -> list[Path]:
    """The uploaded files of one partition (to rewrite it with new days)."""
    path = lk.dir / "_catalog.json"
    if not path.exists():
        return []
    cat = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for f in cat.get("tables", {}).get(table, {}).get("files", []):
        if f"/{partition}/" in f"/{f}":
            local = tmp / "old" / lk.dataset / f
            local.parent.mkdir(parents=True, exist_ok=True)
            key = f"{lake.BUCKET}/{lake.PREFIX}/{lk.dataset}/{f}"
            if not lake.wrangler("r2", "object", "get", key, "--file", str(local), "--remote"):
                raise SystemExit(f"could not read {key}")
            out.append(local)
    return out


def iso_join(con: duckdb.DuckDBPyConnection) -> None:
    lake.iso_codes(con)


# ---------------------------------------------------------------- ENTSOG


def entsog(args: argparse.Namespace) -> None:
    import fetch_entsog as fe

    con = duckdb.connect(str(args.tmp / "entsog.duckdb"))
    iso_join(con)
    lk = lake_for(
        "entsog",
        args.lake,
        f"ENTSOG Transparency Platform ({fe.API})",
        "ENTSOG Transparency Platform terms of use",
        "scripts/build_lake_datasets.py",
    )
    today = date.today()
    if args.year:
        start, end = date(args.year, 1, 1), min(date(args.year, 12, 31), today - timedelta(days=1))
    else:
        end = today - timedelta(days=1)
        start = max(date(end.year, 1, 1), end - timedelta(days=args.recent or 7))
    rows: list[dict] = []
    with httpx.Client(timeout=600, headers=UA) as client:
        m = start
        while m <= end:
            last = min(
                end, (m.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            )
            got = fe.get(
                client,
                "operationaldatas",
                indicator="Physical Flow",
                periodType="day",
                timezone="CET",
                **{"from": m.isoformat(), "to": last.isoformat()},
            )["operationaldatas"]
            rows += got
            print(f"  {m}..{last}: {len(got):,} rows", flush=True)
            m = last + timedelta(days=1)
        points = fe.get(client, "connectionpoints")["connectionpoints"]
        opd = fe.get(client, "operatorpointdirections")["operatorpointdirections"]
    load_rows(con, "raw", rows, args.tmp)
    cols = {r[0] for r in con.execute("DESCRIBE raw").fetchall()}
    day = "periodfrom" if "periodfrom" in cols else "period_from"
    new = f"""SELECT CAST(substr(CAST({day} AS VARCHAR), 1, 10) AS DATE) AS gas_day, r.*,
                      upper(left(CAST(r.tsoeiccode AS VARCHAR), 2)) AS eic_prefix
               FROM raw r"""
    con.execute(f"CREATE TABLE new_flows AS {new}")
    year = start.year
    query = "SELECT * FROM new_flows"
    if not args.year:
        lk.pull_catalog()
        old = old_files(lk, "flows", f"year={year}", args.tmp)
        if old:
            files = ", ".join(f"'{p}'" for p in old)
            query = (
                f"SELECT * EXCLUDE (iso2, iso3, admin1) FROM read_parquet([{files}]) WHERE gas_day < DATE '{start}' "
                "UNION ALL BY NAME SELECT * FROM new_flows"
            )
    country = (
        "coalesce(nullif(CAST(r.tsocountry AS VARCHAR), ''), NULL)"
        if "tsocountry" in cols
        else "NULL"
    )
    lk.write(
        con,
        "flows",
        f"""SELECT r.*, {country} AS iso2, i.iso3, NULL::VARCHAR AS admin1
            FROM ({query}) r LEFT JOIN iso_codes i ON i.iso2 = {country}""",
        sort=[
            "pointkey" if "pointkey" in cols else "point_key",
            "directionkey" if "directionkey" in cols else "direction_key",
            "gas_day",
        ],
        bloom=["pointkey" if "pointkey" in cols else "point_key"],
        partition={"year": str(year)},
    )
    load_rows(con, "pts", points, args.tmp)
    lk.write(
        con,
        "points",
        "SELECT p.*, NULL::VARCHAR AS iso2, NULL::VARCHAR AS iso3, NULL::VARCHAR AS admin1 FROM pts p",
        sort=["pointkey"],
    )
    load_rows(con, "opd", opd, args.tmp)
    lk.write(
        con,
        "operator_point_directions",
        "SELECT o.*, NULL::VARCHAR AS iso2, NULL::VARCHAR AS iso3, NULL::VARCHAR AS admin1 FROM opd o",
        sort=["pointkey", "directionkey"],
    )
    finish(lk, args.upload, merge=True)


# ---------------------------------------------------------------- EIA-930


EIA930_ROUTES = {
    "demand": "region-data",
    "generation_by_fuel": "fuel-type-data",
    "interchange": "interchange-data",
}


def eia930(args: argparse.Namespace) -> None:
    import fetch_us as fu

    con = duckdb.connect(str(args.tmp / "eia930.duckdb"))
    iso_join(con)
    lk = lake_for(
        "eia930",
        args.lake,
        f"EIA-930 Hourly Electric Grid Monitor ({fu.BASE})",
        "US public domain (EIA)",
        "scripts/build_lake_datasets.py",
    )
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    if args.year:
        start = datetime(args.year, 1, 1, tzinfo=UTC)
        end = min(datetime(args.year + 1, 1, 1, tzinfo=UTC), now)
    else:
        end = now
        start = max(datetime(now.year, 1, 1, tzinfo=UTC), now - timedelta(days=args.recent or 3))
    year = start.year
    if not args.year:
        lk.pull_catalog()
    with httpx.Client(timeout=300) as client:
        for table, route in EIA930_ROUTES.items():
            rows: list[dict] = []
            m = start
            while m < end:
                nxt = min(end, (m.replace(day=28) + timedelta(days=4)).replace(day=1, hour=0))
                got = fu.rows(
                    client,
                    route,
                    {
                        "start": m.strftime("%Y-%m-%dT%H"),
                        "end": (nxt - timedelta(hours=1)).strftime("%Y-%m-%dT%H"),
                    },
                )
                rows += got
                m = nxt
            print(f"  {route}: {len(rows):,} rows", flush=True)
            if not rows:
                continue
            load_rows(con, "raw", rows, args.tmp)
            new = """SELECT strptime(period, '%Y-%m-%dT%H')::TIMESTAMP AT TIME ZONE 'UTC' AS ts, 60 AS resolution_min, r.*
                     FROM (SELECT * REPLACE (CAST(period AS VARCHAR) AS period) FROM raw) r"""
            con.execute(f"CREATE OR REPLACE TABLE new_rows AS {new}")
            query = "SELECT * FROM new_rows"
            if not args.year:
                old = old_files(lk, table, f"year={year}", args.tmp)
                if old:
                    files = ", ".join(f"'{p}'" for p in old)
                    query = (
                        f"SELECT * EXCLUDE (iso2, iso3, admin1) FROM read_parquet([{files}]) "
                        f"WHERE ts < TIMESTAMPTZ '{start.isoformat()}' UNION ALL BY NAME SELECT * FROM new_rows"
                    )
            sort = {
                "demand": ["respondent", "type", "ts"],
                "generation_by_fuel": ["respondent", "fueltype", "ts"],
                "interchange": ["fromba", "toba", "ts"],
            }[table]
            lk.write(
                con,
                table,
                f"SELECT q.*, 'US' AS iso2, 'USA' AS iso3, NULL::VARCHAR AS admin1 FROM ({query}) q WHERE year(ts AT TIME ZONE 'UTC') = {year}",
                sort=sort,
                partition={"year": str(year)},
            )
            if table == "demand":
                lk.write(
                    con,
                    "bas",
                    "SELECT DISTINCT respondent, \"respondent-name\" AS respondent_name, 'US' AS iso2, 'USA' AS iso3, NULL::VARCHAR AS admin1 FROM raw"
                    if "respondent-name" in {r[0] for r in con.execute("DESCRIBE raw").fetchall()}
                    else "SELECT DISTINCT respondent, respondent_name, 'US' AS iso2, 'USA' AS iso3, NULL::VARCHAR AS admin1 FROM raw",
                    sort=["respondent"],
                )
    finish(lk, args.upload, merge=True)


# ---------------------------------------------------------------- EIA-860M and LBNL


def xlsx_rows(path: Path, sheet: str, header_hint: str) -> list[dict]:
    """A sheet's rows as published, from the header row (the first row holding `header_hint`)."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    rows = ws.iter_rows(values_only=True)
    header: list[str] | None = None
    out = []
    for r in rows:
        if header is None:
            if any(isinstance(c, str) and header_hint.lower() in c.lower() for c in r):
                header = [str(c).strip() if c is not None else f"col{i}" for i, c in enumerate(r)]
            continue
        if all(c is None for c in r):
            continue
        out.append(
            {
                h: (c.isoformat() if isinstance(c, (datetime, date)) else c)
                for h, c in zip(header, r, strict=False)
            }
        )
    return out


def eia860m(args: argparse.Namespace) -> None:
    import fetch_us_grid as fg

    con = duckdb.connect()
    with httpx.Client(timeout=300, follow_redirects=True, headers=fg.UA) as client:
        url, release = fg.eia_link(fg.get(client, fg.EIA_PAGE).text)
        path = fg.download(client, url, fg.RAW / url.rsplit("/", 1)[1])
    snap = datetime.strptime(release, "%B %Y").strftime("%Y-%m")
    lk = lake_for(
        "eia860m",
        args.lake,
        f"EIA-860M Preliminary Monthly Electric Generator Inventory ({url})",
        "US public domain (EIA)",
        "scripts/build_lake_datasets.py",
        release,
    )
    import openpyxl

    sheets = openpyxl.load_workbook(path, read_only=True).sheetnames
    rows: list[dict] = []
    for sheet in sheets:
        got = xlsx_rows(path, sheet, "Plant ID")
        for r in got:
            r["sheet"] = sheet
        rows += got
        print(f"  {sheet}: {len(got):,} rows", flush=True)
    load_rows(con, "g", rows, args.tmp)
    lake.iso_codes(con)
    st = (
        "plant_state"
        if "plant_state" in {r[0] for r in con.execute("DESCRIBE g").fetchall()}
        else "NULL"
    )
    lk.write(
        con,
        "generators",
        f"SELECT g.*, 'US' AS iso2, 'USA' AS iso3, {st} AS admin1 FROM g",
        sort=[st if st != "NULL" else "sheet", "plant_id"],
        bloom=["plant_id"],
        partition={"snapshot": snap},
    )
    finish(lk, args.upload, merge=True)


def lbnl(args: argparse.Namespace) -> None:
    import fetch_us_grid as fg
    import openpyxl

    con = duckdb.connect()
    with httpx.Client(timeout=300, follow_redirects=True, headers=fg.UA) as client:
        url, release = fg.lbnl_link(fg.get(client, fg.LBNL_PAGE).text)
        path = fg.download(client, url, fg.RAW / release)
    lk = lake_for(
        "lbnl_queue",
        args.lake,
        f"LBNL Queued Up ({url})",
        "LBNL (public, attribution)",
        "scripts/build_lake_datasets.py",
        release,
    )
    wb = openpyxl.load_workbook(path, read_only=True)
    sheet = next(
        (s for s in wb.sheetnames if "data" in s.lower() and "complete" in s.lower()),
        wb.sheetnames[0],
    )
    rows = xlsx_rows(path, sheet, "q_id")
    print(f"  {sheet}: {len(rows):,} requests", flush=True)
    names = load_rows(con, "q", rows, args.tmp)
    st = "state" if "state" in names else "NULL"
    lk.write(
        con,
        "requests",
        f"SELECT q.*, 'US' AS iso2, 'USA' AS iso3, {st} AS admin1 FROM q",
        sort=[st if st != "NULL" else names[0], names[0]],
        partition={"release": snake(release)},
    )
    finish(lk, args.upload, merge=True)


# ---------------------------------------------------------------- IRENA


def jsonstat_rows(d: dict) -> list[dict]:
    """json-stat2 values as rows: every dimension's code and label, then the value."""
    ids, sizes, values = d["id"], d["size"], d["value"]
    cats = {k: list(d["dimension"][k]["category"]["index"]) for k in ids}
    labels = {k: d["dimension"][k]["category"].get("label", {}) for k in ids}
    strides = [1] * len(sizes)
    for k in range(len(sizes) - 2, -1, -1):
        strides[k] = strides[k + 1] * sizes[k + 1]
    rows = []
    for pos, v in enumerate(values):
        if v is None:
            continue
        row: dict[str, Any] = {}
        for k, dim in enumerate(ids):
            code = cats[dim][(pos // strides[k]) % sizes[k]]
            row[dim] = code
            row[f"{dim} label"] = labels[dim].get(code, code)
        row["value"] = v
        rows.append(row)
    return rows


def irena(args: argparse.Namespace) -> None:
    import fetch_irena as fi

    con = duckdb.connect()
    lake.iso_codes(con)
    with httpx.Client(timeout=300, verify=fi.tls(), headers=UA) as client:
        table = fi.country_table(client)
        url = f"{fi.FOLDER}/{table}"
        meta = {v["code"]: v for v in client.get(url).json()["variables"]}
        countries = meta["Country/area"]["values"]
        rows = []
        # one query per data type and grid connection, countries in batches (pxweb refuses
        # larger answers with 403)
        for dtype in meta["Data Type"]["values"]:
            for grid in meta["Grid connection"]["values"]:
                for i in range(0, len(countries), fi.BATCH):
                    sel = [
                        ("Country/area", countries[i : i + fi.BATCH]),
                        ("Data Type", [dtype]),
                        ("Grid connection", [grid]),
                    ]
                    q = {
                        "query": [
                            {"code": c, "selection": {"filter": "item", "values": v}}
                            for c, v in sel
                        ],
                        "response": {"format": "json-stat2"},
                    }
                    for attempt in range(6):  # PxWeb allows ~10 queries per 10 s
                        time.sleep(1.5)
                        r = client.post(url, json=q)
                        if r.status_code != 429:
                            break
                        time.sleep(15 * (attempt + 1))
                    r.raise_for_status()
                    rows += jsonstat_rows(r.json())
                print(f"  {dtype} / {grid}: {len(rows):,} values so far", flush=True)
    release = re.sub(r"_PX\.px$", "", table)
    lk = lake_for(
        "irena",
        args.lake,
        f"IRENASTAT Power Capacity and Generation ({url})",
        "IRENA (attribution)",
        "scripts/build_lake_datasets.py",
        release,
    )
    names = load_rows(con, "x", rows, args.tmp)
    dtype = next(n for n in names if n.startswith("data_type") and n.endswith("label"))
    country = next(n for n in names if n.startswith("country") and not n.endswith("label"))
    for table_name, word in (("capacity", "Capacity"), ("generation", "Generation")):
        lk.write(
            con,
            table_name,
            f"""SELECT x.*, i.iso2, x.{country} AS iso3, NULL::VARCHAR AS admin1 FROM x
                LEFT JOIN iso_codes i ON i.iso3 = x.{country} WHERE x.{dtype} ILIKE '%{word}%'""",
            sort=[country, next(n for n in names if n.startswith("technology")), "year"],
            partition={"release": release},
        )
    finish(lk, args.upload, merge=True)


# ---------------------------------------------------------------- JRC-PPDB, powerplantmatching


def jrc(args: argparse.Namespace) -> None:
    import build_eu_units as bu

    con = duckdb.connect()
    lake.iso_codes(con)
    lk = lake_for(
        "power_plants_eu",
        args.lake,
        f"JRC Open Power Plants Database (Zenodo 3574566); powerplantmatching ({PPM})",
        "CC BY 4.0 (JRC); MIT/CC BY 4.0 (powerplantmatching)",
        "scripts/build_lake_datasets.py",
    )
    bu.RAW.mkdir(parents=True, exist_ok=True)
    zpath = bu.RAW / "JRC-PPDB-OPEN.ver1.0.zip"
    if not zpath.exists():
        zpath.write_bytes(httpx.get(bu.JRC_URL, follow_redirects=True, timeout=300).content)
    with zipfile.ZipFile(zpath) as z:
        for name, table in (
            ("JRC_OPEN_UNITS.csv", "jrc_units"),
            ("JRC_OPEN_PERFORMANCE.csv", "jrc_performance"),
        ):
            if name not in z.namelist():
                continue
            rows = list(csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8")))
            names = load_rows(con, "t", rows, args.tmp)
            cc = "country" if "country" in names else None
            key = "eic_g" if "eic_g" in names else names[0]
            pos = (
                ", TRY_CAST(lon AS DOUBLE) AS lon_, TRY_CAST(lat AS DOUBLE) AS lat_"
                if "lon" in names and "lat" in names
                else ""
            )
            iso = (
                "NULL"
                if not cc
                else "(SELECT iso2 FROM iso_codes WHERE lower(name) = lower(t.country) LIMIT 1)"
            )
            lk.write(
                con,
                table,
                f"SELECT t.*{pos}, {iso} AS iso2, (SELECT iso3 FROM iso_codes WHERE iso2 = {iso}) AS iso3, NULL::VARCHAR AS admin1 FROM t",
                sort=[cc or key, key] if cc else [key],
                bloom=[key],
            )
    text = httpx.get(PPM, follow_redirects=True, timeout=300).text
    rows = list(csv.DictReader(io.StringIO(text)))
    names = load_rows(con, "p", rows, args.tmp)
    lk.write(
        con,
        "ppm_plants",
        """SELECT p.*, (SELECT iso2 FROM iso_codes WHERE lower(name) = lower(p.country) LIMIT 1) AS iso2,
                  (SELECT iso3 FROM iso_codes WHERE lower(name) = lower(p.country) LIMIT 1) AS iso3,
                  NULL::VARCHAR AS admin1 FROM p""",
        sort=["country", names[0]],
    )
    finish(lk, args.upload)


PPM = "https://raw.githubusercontent.com/PyPSA/powerplantmatching/master/powerplants.csv"


# ---------------------------------------------------------------- GEM (private licence)


def gem(args: argparse.Namespace) -> None:
    import openpyxl

    folder = ROOT / "data" / "world" / "gem"
    releases = json.loads((ROOT / "scripts" / "gem_releases.json").read_text(encoding="utf-8"))
    con = duckdb.connect()
    lake.iso_codes(con)
    lk = lake_for(
        "gem",
        args.lake,
        "Global Energy Monitor trackers (downloads under GEM's licence; never public)",
        "GEM licence (CC BY 4.0 for non-commercial use; see each tracker)",
        "scripts/build_lake_datasets.py",
    )
    files = [
        (snake(t), info.get("updated") or "", folder / t / f)
        for t, info in releases.items()
        for f in info.get("files", [])
        if f.endswith(".xlsx")
    ]
    for tracker, release, path in files:
        if not path.exists():
            print(f"  {path}: not pulled from R2")
            continue
        wb = openpyxl.load_workbook(path, read_only=True)
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            rows_iter = ws.iter_rows(values_only=True)
            header = next(rows_iter, None)
            if not header or sum(1 for h in header if h) < 4:
                continue
            hdr = [str(h).strip() if h is not None else f"col{i}" for i, h in enumerate(header)]
            rows = [
                dict(zip(hdr, r, strict=False)) for r in rows_iter if any(c is not None for c in r)
            ]
            if len(rows) < 10 or sheet.lower() in ("about", "metadata", "read me", "readme"):
                continue
            names = load_rows(con, "t", rows, args.tmp)
            cc = next(
                (n for n in names if n in ("country_area", "country", "country_area_1")), None
            )
            iso = (
                f"(SELECT iso2 FROM iso_codes WHERE lower(name) = lower(t.{cc}) LIMIT 1)"
                if cc
                else "NULL"
            )
            iso3 = (
                f"(SELECT iso3 FROM iso_codes WHERE lower(name) = lower(t.{cc}) LIMIT 1)"
                if cc
                else "NULL"
            )
            adm = next(
                (
                    n
                    for n in names
                    if n
                    in ("subnational_unit_province_state", "state_province", "subnational_unit")
                ),
                None,
            )
            lk.write(
                con,
                f"{tracker}_{snake(sheet)}"[:60],
                f"SELECT t.*, {iso} AS iso2, {iso3} AS iso3, {adm or 'NULL'} AS admin1 FROM t",
                sort=[cc or names[0], names[0]],
                partition={"release": snake(release)},
            )
    finish(lk, args.upload, merge=True)


# ---------------------------------------------------------------- OSM-derived snapshots


GEOM_SQL = "TRY(ST_GeomFromText(trim(CAST(t.geometry AS VARCHAR), '''''' || '\"')))"


def osm(args: argparse.Namespace) -> None:
    import fetch_eu_energy as fe

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    lake.iso_codes(con)
    snap = date.today().isoformat()
    lk = lake_for(
        "osm",
        args.lake,
        "OpenStreetMap contributors via PyPSA-Eur (Zenodo 18619025), Overpass (cables, data centres)",
        "ODbL",
        "scripts/build_lake_datasets.py",
        snap,
    )
    for name in ("lines", "buses", "links"):
        text = httpx.get(fe.FILES[f"{name}.csv"], follow_redirects=True, timeout=600).text
        rows = list(csv.DictReader(io.StringIO(text)))
        names = load_rows(con, "t", rows, args.tmp)
        geom = (
            GEOM_SQL
            if "geometry" in names
            else ("ST_Point(t.x, t.y)" if "x" in names and "y" in names else None)
        )
        cc = "country" if "country" in names else None
        iso = f"t.{cc}" if cc else "NULL"
        sel = (
            f"SELECT t.* EXCLUDE (geometry), {geom} AS geometry"
            if "geometry" in names
            else f"SELECT t.*, {geom} AS geometry"
            if geom
            else "SELECT t.*"
        )
        lk.write(
            con,
            f"eu_{name}",
            f"""{sel}, {iso} AS iso2, (SELECT iso3 FROM iso_codes WHERE iso2 = {iso}) AS iso3, NULL::VARCHAR AS admin1 FROM t""",
            sort=[lake.hilbert()] if geom else [names[0]],
            partition={"snapshot": snap},
            geometry="geometry" if geom else None,
        )
    store = args.store
    cables = store / "cables.json"
    if cables.exists():
        c = json.loads(cables.read_text(encoding="utf-8"))
        rows = [
            {
                "class": r[0],
                "kv": r[1],
                "name": r[2],
                "wkt": "LINESTRING("
                + ", ".join(f"{r[3][i]} {r[3][i + 1]}" for i in range(0, len(r[3]), 2))
                + ")",
            }
            for r in c["cables"]
            if len(r[3]) >= 4
        ]
        load_rows(con, "t", rows, args.tmp)
        lk.write(
            con,
            "cables",
            "SELECT t.* EXCLUDE (wkt), ST_GeomFromText(wkt) AS geometry, NULL::VARCHAR AS iso2, NULL::VARCHAR AS iso3, NULL::VARCHAR AS admin1 FROM t",
            sort=[lake.hilbert()],
            partition={"snapshot": snap},
            geometry="geometry",
        )
    dc = store / "datacentres.json"
    if dc.exists():
        d = json.loads(dc.read_text(encoding="utf-8"))
        pts = d.get("points") or d.get("sites") or []
        rows = [{"lon": p[0], "lat": p[1], **({"name": p[2]} if len(p) > 2 else {})} for p in pts]
        if rows:
            load_rows(con, "t", rows, args.tmp)
            lk.write(
                con,
                "datacentres",
                "SELECT t.*, ST_Point(lon, lat) AS geometry, NULL::VARCHAR AS iso2, NULL::VARCHAR AS iso3, NULL::VARCHAR AS admin1 FROM t",
                sort=[lake.hilbert()],
                partition={"snapshot": snap},
                geometry="geometry",
            )
    finish(lk, args.upload, merge=True)


# ---------------------------------------------------------------- EU ETS


def euets(args: argparse.Namespace) -> None:
    import fetch_eu_ets as fx

    con = duckdb.connect()
    lake.iso_codes(con)
    snap = date.today().isoformat()
    client = httpx.Client(timeout=300, follow_redirects=True)
    ops = fx.extract(client, "operator/operators_daily.csv.gz")
    yearly = fx.extract(client, "operators_yearly_activity/operators_yearly_activity_daily.csv.gz")
    ids = fx.sql(
        client,
        "SELECT e.ETSIdentifier AS ets, p.id, p.countryCode AS cc, p.reportingYear AS y, "
        "p.x_4326 AS lon, p.y_4326 AS lat "
        "FROM [IED].[latest].[ProductionInstallationETSIdentifier] e "
        "JOIN [IED].[latest].[ProductionInstallation] p ON p.id = e.installationId",
    )
    lk = lake_for(
        "euets",
        args.lake,
        f"EU Union Registry public extracts ({fx.EXTRACTS}); EEA industrial sites register ({fx.DISCO})",
        "European Commission (re-use with attribution); EEA CC BY 4.0",
        "scripts/build_lake_datasets.py",
        snap,
    )
    for table, rows, part in (
        ("installations", ops, {"snapshot": snap}),
        ("verified_emissions", yearly, None),
        ("eea_link", ids, None),
    ):
        names = load_rows(con, "t", rows, args.tmp)
        reg = next((n for n in names if n in ("registry_code", "registry_id", "cc")), None)
        iso = f"upper(CAST(t.{reg} AS VARCHAR))" if reg else "NULL"
        lk.write(
            con,
            table,
            f"SELECT t.*, {iso} AS iso2, (SELECT iso3 FROM iso_codes WHERE iso2 = {iso}) AS iso3, NULL::VARCHAR AS admin1 FROM t",
            sort=[reg or names[0], names[0]],
            partition=part,
        )
    finish(lk, args.upload, merge=True)


# ---------------------------------------------------------------- grid capacity registers


def connect(args: argparse.Namespace) -> None:
    import fetch_connect_here as fc
    import openpyxl

    snap = date.today().isoformat()
    client = httpx.Client(timeout=300, follow_redirects=True, headers=fc.UA)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    lake.iso_codes(con)
    # GB: NESO TEC register as published
    res = fc.get(client, fc.CKAN, {"id": fc.TEC}).json()["result"]
    tec = list(csv.DictReader(io.StringIO(fc.get(client, res["url"]).content.decode("utf-8-sig"))))
    lk = lake_for(
        "neso_tec",
        args.lake,
        f"NESO Transmission Entry Capacity register ({res['url']})",
        "NESO Open Data Licence",
        "scripts/build_lake_datasets.py",
        snap,
    )
    load_rows(con, "t", tec, args.tmp)
    lk.write(
        con,
        "projects",
        "SELECT t.*, 'GB' AS iso2, 'GBR' AS iso3, NULL::VARCHAR AS admin1 FROM t",
        sort=["project_id"]
        if "project_id" in {r[0] for r in con.execute("DESCRIBE t").fetchall()}
        else ["project_name"],
        partition={"snapshot": snap},
    )
    finish(lk, args.upload, merge=True)
    # NL: every area of the capacity map, attributes and outline
    feats: list[dict] = []
    offset = 0
    while True:
        d = fc.get(
            client,
            fc.NL,
            {
                "where": "1=1",
                "outFields": "*",
                "f": "geojson",
                "outSR": 4326,
                "geometryPrecision": 4,
                "resultRecordCount": 1000,
                "resultOffset": offset,
            },
        ).json()
        got = d.get("features", [])
        feats += got
        offset += len(got)
        if not got or not d.get("properties", {}).get("exceededTransferLimit") and len(got) < 1000:
            break
    rows = [{**f["properties"], "wkt_geom": json.dumps(f.get("geometry"))} for f in feats]
    lk = lake_for(
        "nl_capacity",
        args.lake,
        f"Netbeheer Nederland, capaciteitskaart ({fc.NL})",
        "Esri Nederland terms of use",
        "scripts/build_lake_datasets.py",
        snap,
    )
    load_rows(con, "t", rows, args.tmp)
    lk.write(
        con,
        "areas",
        "SELECT t.* EXCLUDE (wkt_geom), ST_GeomFromGeoJSON(wkt_geom) AS geometry, 'NL' AS iso2, 'NLD' AS iso3, NULL::VARCHAR AS admin1 FROM t",
        sort=[lake.hilbert()],
        partition={"snapshot": snap},
        geometry="geometry",
    )
    finish(lk, args.upload, merge=True)
    # ES: REE's node file, every column of "Ficha Capacidades"
    page = fc.get(client, fc.REE_PAGE).text
    m = re.search(r'href="([^"]+GRT_demanda[^"]*\.xlsx)"', page)
    if not m:
        print("  REE: no node file link on the page")
        return
    url = "https://www.ree.es" + m.group(1) if m.group(1).startswith("/") else m.group(1)
    path = args.tmp / "ree.xlsx"
    path.write_bytes(fc.get(client, url).content)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = next(s for s in wb.sheetnames if "ficha" in s.lower())
    rows = xlsx_rows(path, sheet, "Nudo")
    lk = lake_for(
        "ree_nodes",
        args.lake,
        f"Red Eléctrica, capacidad de acceso de demanda ({url})",
        "REE (re-use with attribution)",
        "scripts/build_lake_datasets.py",
        snap,
    )
    load_rows(con, "t", rows, args.tmp)
    lk.write(
        con,
        "nodes",
        "SELECT t.*, 'ES' AS iso2, 'ESP' AS iso3, NULL::VARCHAR AS admin1 FROM t",
        sort=[next(iter(r[0] for r in con.execute("DESCRIBE t").fetchall()))],
        partition={"snapshot": snap},
    )
    finish(lk, args.upload, merge=True)


DATASETS = {
    "entsog": entsog,
    "eia930": eia930,
    "eia860m": eia860m,
    "lbnl": lbnl,
    "irena": irena,
    "jrc": jrc,
    "gem": gem,
    "osm": osm,
    "euets": euets,
    "connect": connect,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=list(DATASETS))
    parser.add_argument("--year", type=int)
    parser.add_argument("--recent", type=int)
    parser.add_argument("--lake", type=Path, default=Path("lake-out"))
    parser.add_argument("--tmp", type=Path, default=Path("lake-tmp"))
    parser.add_argument(
        "--store",
        type=Path,
        default=ROOT / "frontend" / "public" / "data" / "eu",
        help="the map files (osm)",
    )
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()
    args.tmp.mkdir(parents=True, exist_ok=True)
    DATASETS[args.dataset](args)


if __name__ == "__main__":
    main()
