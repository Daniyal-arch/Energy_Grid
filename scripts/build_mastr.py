"""Every generating unit in Germany: the Marktstammdatenregister (Bundesnetzagentur, dl-de/by-2-0).

Source: the daily bulk export https://download.marktstammdatenregister.de/Gesamtdatenexport_<date>_<version>.zip
(3.2 GB zip, ~66 GB of UTF-16 XML; scripts/probe_mastr.py). .github/workflows/mastr.yml
downloads it in GitHub Actions; each job streams some of its XML files (never unpacked) into
Parquet for the lake and writes a small summary; a last job combines the summaries into the
map files. Nothing large runs on a laptop.

    python scripts/build_mastr.py --zip export.zip --part units --lake lake-out --out part-units.json
    python scripts/build_mastr.py --combine part-*.json --vg5000 vg5000.zip --lake lake-out --partials ...

Parts: `units` (wind, biomass, hydro, combustion, nuclear, other), `solar`, `storage`,
`operators` (Marktakteure), `connection` (Netzanschlusspunkte), `locations` (Lokationen).

Units: every column as published (MaStR's names, codes as published) plus the lake's
standard columns: mastr_nr, eeg_mastr_nr, status (the code's name from Katalogwerte), gross_kw,
net_kw, commissioned, decommissioned, ags (Gemeindeschluessel), postcode, lon, lat (where
public: MaStR publishes coordinates only for larger units), operator_nr, location_nr, iso2,
iso3, admin1 (the Land). `catalog_values` holds every code's name.

Map files (frontend/public/data/eu/mastr/):
  units_large.json: operating units of 1 MW and more with coordinates:
    {"fetched", "snapshot", "source", "techs": [...], "units": [[lon, lat, tech, MW, "YYYY-MM"]]}
  municipalities.json: operating MW and units per technology per municipality (AGS), the
    national totals and the newest additions per month, with VG5000 outlines (BKG, dl-de/by-2-0):
    {"fetched", "snapshot", "source", "techs", "national": {tech: [units, MW]},
     "offshore": {tech: [units, MW]}, "no_ags": {tech: [units, MW]},
     "months": [...], "additions": {tech: [[units, MW] per month]},
     "gemeinden": [{"ags", "name", "label": [lon, lat], "polygons": [[flat ring]], "mw": [MW per tech], "n": [units per tech]}]}
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from xml.etree.ElementTree import iterparse

import duckdb
import lake

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu" / "mastr"
SOURCE = "Marktstammdatenregister (Bundesnetzagentur), Gesamtdatenexport"
LICENCE = "dl-de/by-2-0"
PAGE = "https://www.marktstammdatenregister.de/MaStR/Datendownload"
LARGE_KW = 1000
ADDITION_MONTHS = 24
CHUNK = 400_000
# XML file stem -> (lake table, technology on the map)
UNIT_FILES = {
    "EinheitenSolar": ("units_solar", "solar"),
    "EinheitenWind": ("units_wind", "wind"),
    "EinheitenStromSpeicher": ("units_storage", "storage"),
    "EinheitenBiomasse": ("units_biomass", "biomass"),
    "EinheitenWasser": ("units_hydro", "hydro"),
    "EinheitenVerbrennung": ("units_combustion", "combustion"),
    "EinheitenKernkraft": ("units_nuclear", "nuclear"),
    "EinheitenGeothermieGrubengasDruckentspannung": ("units_other", "other"),
}
TECHS = ["solar", "wind", "storage", "biomass", "hydro", "combustion", "nuclear", "other"]
OTHER_FILES = {
    "Marktakteure": ("operators", "MastrNummer"),
    "Netzanschlusspunkte": ("grid_connection_points", "NetzanschlusspunktMastrNummer"),
    "Lokationen": ("locations", "MastrNummer"),
}
PARTS = {
    "units": [
        "EinheitenWind",
        "EinheitenBiomasse",
        "EinheitenWasser",
        "EinheitenVerbrennung",
        "EinheitenKernkraft",
        "EinheitenGeothermieGrubengasDruckentspannung",
    ],
    "solar": ["EinheitenSolar"],
    "storage": ["EinheitenStromSpeicher"],
    "operators": ["Marktakteure"],
    "connection": ["Netzanschlusspunkte"],
    "locations": ["Lokationen"],
}


def stem(name: str) -> str:
    return re.sub(r"(_\d+)?\.xml$", "", Path(name).name)


def records(z: zipfile.ZipFile, name: str):  # noqa: ANN201 (a generator of dicts)
    """Each record element (one level below the root) as {tag: text}, streamed."""
    with z.open(name) as fh:
        depth = 0
        for event, el in iterparse(fh, events=("start", "end")):
            if event == "start":
                depth += 1
                continue
            depth -= 1
            if depth == 1:
                yield {c.tag: c.text for c in el}
                el.clear()


def catalog(z: zipfile.ZipFile) -> dict[str, str]:
    """Katalogwerte: code id -> name."""
    out: dict[str, str] = {}
    for r in records(z, "Katalogwerte.xml"):
        if r.get("Id") and r.get("Wert") is not None:
            out[r["Id"]] = r["Wert"]
    if not out:
        raise SystemExit("Katalogwerte.xml has no Id/Wert records: has the export changed?")
    return out


def to_parquet(z: zipfile.ZipFile, stems: list[str], tmp: Path) -> dict[str, list[Path]]:
    """Every record of the files of each stem into chunked Parquet (all columns VARCHAR):
    each chunk goes through a CSV file that DuckDB converts."""
    con = duckdb.connect()
    out: dict[str, list[Path]] = defaultdict(list)
    names = sorted(
        (n for n in z.namelist() if stem(n) in stems),
        key=lambda n: (stem(n), int(m.group(1)) if (m := re.search(r"_(\d+)\.xml$", n)) else 0),
    )
    for s in stems:
        rows: list[dict] = []
        n = 0

        def flush() -> None:
            if not rows:
                return
            cols = sorted({k for r in rows for k in r})
            path = tmp / f"{s}-{len(out[s])}.parquet"
            text = path.with_suffix(".csv")
            with text.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=cols)
                w.writeheader()
                w.writerows(rows)
            types = "{" + ", ".join(f"{lake._quote(c)}: 'VARCHAR'" for c in cols) + "}"
            con.execute(
                f"COPY (SELECT * FROM read_csv({lake._quote(str(text))}, header = true, "
                f"columns = {types}, quote = '\"', escape = '\"')) "
                f"TO {lake._quote(str(path))} (FORMAT parquet, COMPRESSION zstd)"
            )
            text.unlink()
            out[s].append(path)
            rows.clear()

        for name in (x for x in names if stem(x) == s):
            for r in records(z, name):
                rows.append(r)
                n += 1
                if len(rows) >= CHUNK:
                    flush()
            print(f"  {name}: {n:,} records so far", flush=True)
        flush()
    return out


def lake_of(root: Path, snapshot: str) -> lake.Lake:
    return lake.Lake(
        "mastr",
        root,
        source=f"{SOURCE} {snapshot}; {PAGE}",
        licence=LICENCE,
        script="scripts/build_mastr.py",
        source_version=snapshot,
    )


def register_catalog(con: duckdb.DuckDBPyConnection, values: dict[str, str]) -> None:
    con.execute("CREATE OR REPLACE TABLE kat (id VARCHAR, wert VARCHAR)")
    con.executemany("INSERT INTO kat VALUES (?, ?)", list(values.items()))


def unit_sql(src: str, cols: set[str]) -> str:
    """The units as published plus the lake's standard columns."""

    def col(name: str) -> str:
        return f'"{name}"' if name in cols else "NULL"

    return f"""
        SELECT {col("EinheitMastrNummer")} AS mastr_nr, {col("EegMaStRNummer")} AS eeg_mastr_nr,
               st.wert AS status, TRY_CAST({col("Bruttoleistung")} AS DOUBLE) AS gross_kw,
               TRY_CAST({col("Nettonennleistung")} AS DOUBLE) AS net_kw,
               TRY_CAST({col("Inbetriebnahmedatum")} AS DATE) AS commissioned,
               TRY_CAST({col("DatumEndgueltigeStilllegung")} AS DATE) AS decommissioned,
               {col("Gemeindeschluessel")} AS ags, {col("Postleitzahl")} AS postcode,
               TRY_CAST({col("Laengengrad")} AS DOUBLE) AS lon,
               TRY_CAST({col("Breitengrad")} AS DOUBLE) AS lat,
               {col("AnlagenbetreiberMastrNummer")} AS operator_nr,
               {col("LokationMaStRNummer")} AS location_nr,
               'DE' AS iso2, 'DEU' AS iso3, bl.wert AS admin1, u.*
        FROM {src} u
        LEFT JOIN kat st ON st.id = u.{col("EinheitBetriebsstatus")}
        LEFT JOIN kat bl ON bl.id = u.{col("Bundesland")}"""


def build_part(zip_path: Path, part: str, root: Path, upload: bool, tmp: Path) -> dict:
    z = zipfile.ZipFile(zip_path)
    snapshot = snapshot_of(zip_path)
    values = catalog(z)
    tmp.mkdir(parents=True, exist_ok=True)
    # a database file, so the solar table (millions of rows, ~60 columns) spills to disk
    con = duckdb.connect(str(tmp / f"{part}.duckdb"))
    con.execute(f"SET temp_directory = {lake._quote(str(tmp / 'spill'))}")
    con.execute("SET memory_limit = '4GB'")  # three parts run side by side on one runner
    register_catalog(con, values)
    lk = lake_of(root, snapshot)
    chunks = to_parquet(z, PARTS[part], tmp)
    summary: dict = {"snapshot": snapshot, "part": part, "techs": {}}
    if part == "units":
        con.execute("CREATE TABLE catalog_values AS SELECT id, wert AS value FROM kat")
        lk.write(
            con,
            "catalog_values",
            "SELECT TRY_CAST(id AS INTEGER) AS id, value FROM catalog_values",
            sort=["id"],
            partition={"snapshot": snapshot},
        )
    for s, paths in chunks.items():
        src = f"read_parquet({[str(p) for p in paths]}, union_by_name = true)"
        cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()}
        if s in UNIT_FILES:
            table, tech = UNIT_FILES[s]
            con.execute(f"CREATE OR REPLACE TABLE u AS {unit_sql(src, cols)}")
            if table == "units_solar":  # partition by Land: each file stays small
                for (land,) in con.execute("SELECT DISTINCT admin1 FROM u ORDER BY 1").fetchall():
                    where = "admin1 IS NULL" if land is None else f"admin1 = {lake._quote(land)}"
                    lk.write(
                        con,
                        table,
                        f"SELECT * FROM u WHERE {where}",
                        sort=["ags", "mastr_nr"],
                        bloom=["mastr_nr"],
                        partition={"snapshot": snapshot, "land": land_key(land)},
                    )
            else:
                lk.write(
                    con,
                    table,
                    "SELECT * FROM u",
                    sort=["ags", "mastr_nr"],
                    bloom=["mastr_nr"],
                    partition={"snapshot": snapshot},
                )
            summary["techs"][tech] = summarise(con, tech, values)
        else:
            table, key = OTHER_FILES[s]
            id_col = key if key in cols else sorted(cols)[0]
            lk.write(
                con,
                table,
                f"SELECT u.*, 'DE' AS iso2, 'DEU' AS iso3 FROM {src} u",
                sort=[f'"{id_col}"'],
                bloom=[id_col],
                partition={"snapshot": snapshot},
            )
    summary["catalog"] = json.loads(lk.finish().read_text(encoding="utf-8"))
    if upload:
        lk.upload(catalog=False)
    return summary


def land_key(land: str | None) -> str:
    """The Land as a path-safe key (e.g. Baden-Württemberg -> baden-wuerttemberg)."""
    if land is None:
        return "none"
    s = land.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def snapshot_of(zip_path: Path) -> str:
    m = re.search(r"(\d{4})(\d{2})(\d{2})", zip_path.name)
    if not m:
        raise SystemExit(f"no date in {zip_path.name}: name the file as downloaded")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def summarise(con: duckdb.DuckDBPyConnection, tech: str, values: dict[str, str]) -> dict:
    """Operating units per municipality, national totals, additions per month, large units."""
    op = "status = 'In Betrieb'"
    per_ags = con.execute(
        f"SELECT ags, count(*), sum(gross_kw) / 1000 FROM u WHERE {op} AND ags IS NOT NULL GROUP BY ags"
    ).fetchall()
    national = con.execute(f"SELECT count(*), sum(gross_kw) / 1000 FROM u WHERE {op}").fetchone()
    no_ags = con.execute(
        f"SELECT count(*), coalesce(sum(gross_kw), 0) / 1000 FROM u WHERE {op} AND ags IS NULL"
    ).fetchone()
    offshore = [0, 0.0]
    if tech == "wind":
        # WindAnLandOderAufSee: the code's name ("Windkraft auf See")
        sea = [k for k, v in values.items() if v == "Windkraft auf See"]
        if sea:
            offshore = list(
                con.execute(
                    f"""SELECT count(*), coalesce(sum(gross_kw), 0) / 1000 FROM u
                        WHERE {op} AND "WindAnLandOderAufSee" IN ({",".join(repr(s) for s in sea)})"""
                ).fetchone()
            )
    months = con.execute(
        f"""SELECT strftime(commissioned, '%Y-%m') AS m, count(*), sum(gross_kw) / 1000 FROM u
            WHERE commissioned >= date_trunc('month', current_date) - INTERVAL {ADDITION_MONTHS} MONTH
              AND status <> 'In Planung'
            GROUP BY m ORDER BY m"""
    ).fetchall()
    large = con.execute(
        f"""SELECT round(lon, 4), round(lat, 4), round(gross_kw / 1000, 2), strftime(commissioned, '%Y-%m')
            FROM u WHERE {op} AND gross_kw >= {LARGE_KW} AND lon IS NOT NULL AND lat IS NOT NULL
            ORDER BY gross_kw DESC"""
    ).fetchall()
    print(
        f"  {tech}: {national[0]:,} operating units, {national[1] or 0:,.0f} MW; {len(large):,} ≥ 1 MW placed"
    )
    return {
        "per_ags": {a: [n, round(mw, 3)] for a, n, mw in per_ags},
        "national": [national[0], round(national[1] or 0, 1)],
        "no_ags": [no_ags[0], round(no_ags[1], 1)],
        "offshore": [offshore[0], round(offshore[1], 1)],
        "months": {m: [n, round(mw or 0, 1)] for m, n, mw in months if m},
        "large": [list(r) for r in large],
    }


def outlines(con: duckdb.DuckDBPyConnection, vg5000: Path) -> list[dict]:
    """VG5000 municipalities (BKG, UTM 32N) in lon/lat, simplified (~100 m)."""
    import shapely

    con.execute("INSTALL spatial; LOAD spatial")
    rows = con.execute(
        f"""SELECT AGS, GEN, ST_AsWKB(ST_Transform(geom, 'EPSG:25832', 'EPSG:4326', always_xy := true))
            FROM ST_Read('/vsizip/{vg5000}/vg5000_ebenen_0101/VG5000_GEM.shp')
            WHERE GF = 4"""
    ).fetchall()
    out: dict[str, dict] = {}
    for ags, name, wkb in rows:
        geom = shapely.from_wkb(bytes(wkb)).simplify(0.002, preserve_topology=True)
        polys = [
            [[round(v, 3) for xy in p.exterior.coords for v in xy]]
            for p in getattr(geom, "geoms", [geom])
            if p.geom_type == "Polygon" and not p.is_empty
        ]
        c = geom.representative_point()
        g = out.setdefault(
            ags, {"ags": ags, "name": name, "label": [round(c.x, 3), round(c.y, 3)], "polygons": []}
        )
        g["polygons"].extend(polys)
    return sorted(out.values(), key=lambda g: g["ags"])


def combine(parts: list[dict], vg5000: Path | None) -> tuple[dict, dict]:
    snapshot = parts[0]["snapshot"]
    techs: dict[str, dict] = {}
    for p in parts:
        techs.update(p["techs"])
    order = [t for t in TECHS if t in techs]
    now = datetime.now(UTC).isoformat(timespec="seconds")
    first = date.fromisoformat(snapshot).replace(day=1)
    months = []
    y, m = first.year, first.month
    for _ in range(ADDITION_MONTHS):
        months.insert(0, f"{y:04d}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    large = {
        "fetched": now,
        "snapshot": snapshot,
        "source": f"{SOURCE} {snapshot} ({LICENCE})",
        "techs": order,
        "units": sorted(
            ([u[0], u[1], k, u[2], u[3]] for k, t in enumerate(order) for u in techs[t]["large"]),
            key=lambda u: -u[3],
        ),
    }
    agss = sorted({a for t in order for a in techs[t]["per_ags"]})
    shapes = {}
    if vg5000:
        shapes = {g["ags"]: g for g in outlines(duckdb.connect(), vg5000)}
    gemeinden = []
    for a in agss:
        g = shapes.get(a, {"ags": a, "name": None, "label": None, "polygons": []})
        gemeinden.append(
            {
                **g,
                "mw": [techs[t]["per_ags"].get(a, [0, 0])[1] for t in order],
                "n": [techs[t]["per_ags"].get(a, [0, 0])[0] for t in order],
            }
        )
    missing = [g["ags"] for g in gemeinden if not g["polygons"]]
    print(
        f"  {len(gemeinden):,} municipalities with units; {len(missing):,} without an outline: {missing[:10]}"
    )
    muni = {
        "fetched": now,
        "snapshot": snapshot,
        "source": f"{SOURCE} {snapshot} ({LICENCE}); outlines: BKG VG5000 ({LICENCE})",
        "techs": order,
        "national": {t: techs[t]["national"] for t in order},
        "no_ags": {t: techs[t]["no_ags"] for t in order},
        "offshore": {t: techs[t]["offshore"] for t in order if techs[t]["offshore"][0]},
        "months": months,
        "additions": {t: [techs[t]["months"].get(m, [0, 0]) for m in months] for t in order},
        "gemeinden": gemeinden,
    }
    return large, muni


def keep_snapshots(snapshots: list[str], today: date) -> set[str]:
    """The newest snapshot, the first of each year, and every one younger than a year."""
    keep = {max(snapshots)} if snapshots else set()
    by_year: dict[str, str] = {}
    for s in sorted(snapshots):
        by_year.setdefault(s[:4], s)
        if (today - date.fromisoformat(s)).days < 366:
            keep.add(s)
    return keep | set(by_year.values())


def prune(root: Path, upload: bool) -> list[str]:
    """Drop old snapshots from the catalogue (and from R2 when uploading)."""
    path = root / "mastr" / "_catalog.json"
    cat = json.loads(path.read_text(encoding="utf-8"))
    snaps = sorted(
        {
            m.group(1)
            for t in cat["tables"].values()
            for f in t["files"]
            if (m := re.search(r"snapshot=([\d-]+)", f))
        }
    )
    keep = keep_snapshots(snaps, date.today())
    dropped = []
    for t in cat["tables"].values():
        for f in list(t["files"]):
            m = re.search(r"snapshot=([\d-]+)", f)
            if m and m.group(1) not in keep:
                if upload and not lake.wrangler(
                    "r2", "object", "delete", f"{lake.BUCKET}/{lake.PREFIX}/mastr/{f}", "--remote"
                ):
                    raise SystemExit(f"could not delete {f}")
                t["files"].remove(f)
                t["file_stats"].pop(f, None)
                dropped.append(f)
        stats = t.get("file_stats", {})
        t["rows"] = sum(v[0] for v in stats.values())
        t["bytes"] = sum(v[1] for v in stats.values())
    path.write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding="utf-8")
    return dropped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--part", choices=list(PARTS))
    parser.add_argument("--combine", nargs="*", type=Path)
    parser.add_argument("--vg5000", type=Path)
    parser.add_argument("--lake", type=Path, default=Path("lake-out"))
    parser.add_argument("--partials", nargs="*", type=Path, default=[])
    parser.add_argument("--upload", action="store_true", help="to R2 (GitHub Actions)")
    parser.add_argument("--tmp", type=Path, default=Path("mastr-tmp"))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.part:
        summary = build_part(args.zip, args.part, args.lake, args.upload, args.tmp)
        args.out.write_text(json.dumps(summary, separators=(",", ":")), encoding="utf-8")
        return
    parts = [json.loads(p.read_text(encoding="utf-8")) for p in args.combine]
    large, muni = combine([p for p in parts if p["techs"]], args.vg5000)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in (("units_large.json", large), ("municipalities.json", muni)):
        path = OUT / name
        path.write_text(
            json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
        )
        print(f"{path}: {path.stat().st_size / 1e6:.2f} MB")
    for t in muni["techs"]:
        n, mw = muni["national"][t]
        print(f"  {t}: {n:,} operating units, {mw / 1000:,.2f} GW")
    lk = lake_of(args.lake, muni["snapshot"])
    try:
        lk.pull_catalog()
    except SystemExit as e:
        print(f"  catalogue not pulled: {e}")
    partials = []
    for p in parts:
        path = args.tmp / f"catalog-{p['part']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(p["catalog"]), encoding="utf-8")
        partials.append(path)
    lk.finish(partials=partials)
    dropped = prune(args.lake, args.upload)
    print(f"  snapshots dropped: {len(dropped)} files")
    if args.upload:
        lk.upload(catalog_only=True)


if __name__ == "__main__":
    main()
