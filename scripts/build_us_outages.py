"""US power outages per county (EAGLE-I, ORNL; figshare article 24237376, CC BY 4.0).

EAGLE-I records, every 15 minutes, the customers without power per county as utilities
report them (rows only where customers are out; "customers" are utility meters, not people).
One CSV per year, 0.08-1.4 GB each: .github/workflows/us-outages.yml runs one job per year
(DuckDB over the CSV) and a last job combining them; nothing large runs on a laptop.

Per year (`--year`): for each county the customer-hours without power (sum of customers out
x the interval, computed); for each day the largest number of customers out at one moment in
the country (sum over counties at one timestamp, computed), when, and the state with the most
customers out then; the year's largest events (below); the newest month's national total at
each timestamp (the replay). With `--lake`, the year's rows go to lake/eaglei/outages/year=Y.

An event (computed): a run of timestamps in one state with at least EVENT_MIN customers out
in the state (sum over its counties), gaps up to EVENT_GAP allowed; its peak is the largest
sum, start and end are the first and last timestamp of the run (+ one interval).

Combine (`--combine`): writes frontend/public/data/eu/us_outages.json:
  {"fetched", "source", "years", "partial": {year: note}, "step_min", "customers": {fips: n},
   "counties": {fips: [customer-hours per year]}, "names": {fips: "County, State"},
   "national": [customer-hours per year], "top_days": [[date, peak, at, state, state peak]],
   "events": [[state, start, end, peak, peak at]], "month": {"month", "start", "step_min", "values"}}
customers per county: EAGLE-I's MCC.csv (ORNL's modelled customer count per county), used to
show hours without power per customer (customer-hours / customers, computed).
County outlines: Census cartographic boundaries 1:20m, 2020 (public domain; Connecticut's
eight old counties, as EAGLE-I and MCC.csv use), simplified, written to
frontend/public/data/us/counties.json in the shape of us/states.json. With `--lake` the
`counties`, `coverage` and `dqi` tables are written too.

    python scripts/build_us_outages.py --year 2024 --csv eaglei_outages_2024.csv --out part-2024.json --lake lake-out
    python scripts/build_us_outages.py --combine part-*.json --mcc MCC.csv --counties cb_2020_us_county_20m.zip \
        --coverage coverage_history.csv --dqi DQI.csv --lake lake-out --partials cat-*/_catalog.json
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import lake

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu" / "us_outages.json"
COUNTIES_OUT = ROOT / "frontend" / "public" / "data" / "us" / "counties.json"
SOURCE = "EAGLE-I recorded electricity outages (Oak Ridge National Laboratory, CC BY 4.0)"
LAKE_SOURCE = "EAGLE-I recorded electricity outages 2014-2025, ORNL (figshare 24237376)"
TOP_DAYS = 50
TOP_EVENTS = 50
EVENT_MIN = 10_000
EVENT_GAP_MIN = 60
# years EAGLE-I does not cover whole (its own documentation and coverage_history.csv)
PARTIAL = {2014: "from 1 November"}
# ISO 3166-1 codes of the territories EAGLE-I covers, by state FIPS (the rest is US/USA)
TERRITORIES = {
    "60": ("AS", "ASM"),
    "66": ("GU", "GUM"),
    "69": ("MP", "MNP"),
    "72": ("PR", "PRI"),
    "78": ("VI", "VIR"),
}
ISO2_SQL = (
    "CASE left(fips, 2) "
    + " ".join(f"WHEN '{k}' THEN '{v[0]}'" for k, v in TERRITORIES.items())
    + " ELSE 'US' END"
)
ISO3_SQL = (
    "CASE left(fips, 2) "
    + " ".join(f"WHEN '{k}' THEN '{v[1]}'" for k, v in TERRITORIES.items())
    + " ELSE 'USA' END"
)


def lake_of(root: Path) -> lake.Lake:
    return lake.Lake(
        "eaglei",
        root,
        source=LAKE_SOURCE,
        licence="CC BY 4.0",
        script="scripts/build_us_outages.py",
        source_version="figshare 24237376",
    )


def load_year(con: duckdb.DuckDBPyConnection, csv_path: Path) -> None:
    """The year's CSV as table `raw` (fips, county, state, out, ts, total_customers)."""
    src = f"read_csv('{csv_path}', all_varchar=true, header=true)"
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()]
    # the 2023 file names its count column `sum`; 2024 adds `total_customers`
    out_col = "customers_out" if "customers_out" in cols else "sum"
    total = "TRY_CAST(total_customers AS INTEGER)" if "total_customers" in cols else "NULL::INTEGER"
    con.execute(
        f"""CREATE OR REPLACE TABLE raw AS
            SELECT lpad(trim(fips_code), 5, '0') AS fips, county, state,
                   TRY_CAST({out_col} AS DOUBLE) AS out,
                   CAST(run_start_time AS TIMESTAMP) AS ts, {total} AS total_customers
            FROM {src}"""
    )


def step_minutes(con: duckdb.DuckDBPyConnection) -> int:
    """The most common gap between the year's timestamps (EAGLE-I: 15 minutes)."""
    return int(
        con.execute(
            """SELECT mode(d) FROM (SELECT epoch(ts - lag(ts) OVER (ORDER BY ts)) / 60 AS d
               FROM (SELECT DISTINCT ts FROM raw)) WHERE d > 0"""
        ).fetchone()[0]  # type: ignore[index]
    )


def year_part(con: duckdb.DuckDBPyConnection, year: int) -> dict:
    step = step_minutes(con)
    hours = step / 60
    counties = con.execute(
        f"SELECT fips, any_value(county), any_value(state), sum(out) * {hours} FROM raw GROUP BY fips"
    ).fetchall()
    days = con.execute(
        """
        WITH nat AS (SELECT ts, sum(out) AS n FROM raw GROUP BY ts),
             st AS (SELECT ts, state, sum(out) AS n FROM raw GROUP BY ts, state),
             peak AS (SELECT CAST(ts AS DATE) AS d, arg_max(ts, n) AS ts, max(n) AS n FROM nat GROUP BY d)
        SELECT CAST(p.d AS VARCHAR), p.n, strftime(p.ts, '%Y-%m-%d %H:%M'), arg_max(st.state, st.n), max(st.n)
        FROM peak p JOIN st ON st.ts = p.ts GROUP BY p.d, p.n, p.ts ORDER BY p.d
        """
    ).fetchall()
    events = con.execute(
        f"""
        WITH s AS (SELECT state, ts, sum(out) AS n FROM raw GROUP BY state, ts HAVING sum(out) >= {EVENT_MIN}),
             g AS (SELECT *, CASE WHEN ts - lag(ts) OVER (PARTITION BY state ORDER BY ts)
                                      <= INTERVAL {EVENT_GAP_MIN} MINUTE THEN 0 ELSE 1 END AS brk FROM s),
             e AS (SELECT *, sum(brk) OVER (PARTITION BY state ORDER BY ts) AS eid FROM g)
        SELECT state, strftime(min(ts), '%Y-%m-%d %H:%M'),
               strftime(max(ts) + INTERVAL {step} MINUTE, '%Y-%m-%d %H:%M'),
               max(n), strftime(arg_max(ts, n), '%Y-%m-%d %H:%M')
        FROM e GROUP BY state, eid ORDER BY max(n) DESC LIMIT {TOP_EVENTS}
        """
    ).fetchall()
    last = con.execute("SELECT max(ts) FROM raw").fetchone()[0]  # type: ignore[index]
    month_start = datetime(last.year, last.month, 1)
    series = dict(
        con.execute(
            "SELECT ts, sum(out) FROM raw WHERE ts >= ? GROUP BY ts ORDER BY ts", [month_start]
        ).fetchall()
    )
    n_steps = int((last - month_start).total_seconds() // (step * 60)) + 1
    values = [
        round(series[t]) if (t := month_start + timedelta(minutes=k * step)) in series else 0
        for k in range(n_steps)
    ]
    return {
        "year": year,
        "step_min": step,
        "counties": {f: round(ch) for f, _, _, ch in counties if ch},
        "names": {f: f"{c}, {s}" for f, c, s, _ in counties},
        "days": [[d, round(n), at, s, round(sn)] for d, n, at, s, sn in days],
        "events": [[s, a, b, round(n), at] for s, a, b, n, at in events],
        "month": {
            "month": month_start.strftime("%Y-%m"),
            "start": month_start.strftime("%Y-%m-%d %H:%M"),
            "step_min": step,
            # timestamps with no row: no customer reported out (EAGLE-I lists only outages)
            "values": values,
        },
    }


def year_lake(con: duckdb.DuckDBPyConnection, year: int, root: Path, upload: bool = False) -> Path:
    """lake/eaglei/outages/year=Y: every row as published, sorted by county and time."""
    whole = con.execute(
        "SELECT count(*) FILTER (WHERE out IS NOT NULL AND out <> round(out)) FROM raw"
    ).fetchone()[0]  # type: ignore[index]
    kind = "INTEGER" if whole == 0 else "FLOAT"
    print(f"  customers_out as {kind} ({whole} rows not whole numbers)", flush=True)
    lk = lake_of(root)
    lk.write(
        con,
        "outages",
        f"""SELECT fips, ts, CAST(out AS {kind}) AS customers_out, total_customers,
                   {ISO2_SQL} AS iso2, {ISO3_SQL} AS iso3, state AS admin1, county
            FROM raw""",
        sort=["fips", "ts"],
        bloom=["fips"],
        partition={"year": str(year)},
    )
    path = lk.finish()
    if upload:  # the files only; the combine job merges and uploads the catalogue
        lk.upload(catalog=False)
    return path


def counties_outlines(con: duckdb.DuckDBPyConnection, zip_path: Path) -> dict:
    """Census cartographic boundary counties (shapefile in a zip) -> us/states.json's shape."""
    import shapely
    import shapely.geometry

    con.execute("INSTALL spatial; LOAD spatial")
    stem = Path(zip_path).name.removesuffix(".zip")
    rows = con.execute(
        f"""SELECT GEOID, NAME, STUSPS, ST_AsWKB(geom)
            FROM ST_Read('/vsizip/{zip_path}/{stem}.shp')"""
    ).fetchall()
    out = []
    for geoid, name, st, wkb in rows:
        geom = shapely.from_wkb(bytes(wkb)).simplify(0.01)
        polys = []
        for p in getattr(geom, "geoms", [geom]):
            if p.is_empty or p.geom_type != "Polygon":
                continue
            rings = [p.exterior, *p.interiors]
            polys.append([[round(v, 3) for xy in ring.coords for v in xy] for ring in rings])
        c = geom.representative_point()
        out.append(
            {
                "code": geoid,
                "name": name,
                "state": st,
                "label": [round(c.x, 3), round(c.y, 3)],
                "polygons": polys,
            }
        )
    return {
        "source": "US Census Bureau, cartographic boundary file, counties 1:20m, 2020 (public domain)",
        "counties": sorted(out, key=lambda c: c["code"]),
    }


def read_mcc(mcc: Path) -> dict[str, int]:
    with mcc.open(encoding="utf-8-sig") as fh:
        return {
            str(r["County_FIPS"]).zfill(5): int(float(r["Customers"]))
            for r in csv.DictReader(fh)
            if r["Customers"]
        }


def combine(parts: list[dict], customers: dict[str, int]) -> dict:
    parts = sorted(parts, key=lambda p: p["year"])
    years = [p["year"] for p in parts]
    counties: dict[str, list] = {}
    names: dict[str, str] = {}
    for k, p in enumerate(parts):
        names.update(p["names"])
        for f, ch in p["counties"].items():
            counties.setdefault(f, [None] * len(years))[k] = ch
    days = [d for p in parts for d in p["days"]]
    events = [e for p in parts for e in p.get("events", [])]
    steps = sorted({p.get("step_min", 15) for p in parts})
    return {
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": SOURCE,
        "years": years,
        "partial": {str(y): PARTIAL[y] for y in years if y in PARTIAL},
        "step_min": steps[0] if len(steps) == 1 else steps,
        "event_rule": {"min_customers": EVENT_MIN, "gap_min": EVENT_GAP_MIN},
        "customers": customers,
        "counties": dict(sorted(counties.items())),
        "names": dict(sorted(names.items())),
        "national": [sum(p["counties"].values()) for p in parts],
        "top_days": sorted(days, key=lambda d: -d[1])[:TOP_DAYS],
        "events": sorted(events, key=lambda e: -e[3])[:TOP_EVENTS],
        "month": parts[-1].get("month"),
    }


def small_tables_lake(
    con: duckdb.DuckDBPyConnection,
    root: Path,
    names: dict[str, str],
    customers: dict[str, int],
    coverage: Path | None,
    dqi: Path | None,
    partials: list[Path],
    upload: bool = False,
) -> Path:
    """lake/eaglei/counties, coverage and dqi (as published), then the merged catalogue."""
    lk = lake_of(root)
    pulled = False
    try:
        pulled = lk.pull_catalog()
    except SystemExit as e:  # no Cloudflare token: local run
        print(f"  catalogue not pulled: {e}")
    rows = [
        (f, *(names[f].split(", ", 1) if f in names else (None, None)), customers.get(f))
        for f in sorted(set(names) | set(customers))
    ]
    con.execute(
        "CREATE OR REPLACE TABLE c (fips VARCHAR, county VARCHAR, state VARCHAR, mcc INTEGER)"
    )
    con.executemany("INSERT INTO c VALUES (?, ?, ?, ?)", rows)
    lk.write(
        con,
        "counties",
        f"""SELECT fips, county, state, mcc AS mcc_customers,
                   {ISO2_SQL} AS iso2, {ISO3_SQL} AS iso3, state AS admin1 FROM c""",
        sort=["fips"],
    )
    if coverage:
        lk.write(
            con,
            "coverage",
            f"""SELECT *, CASE state {" ".join(f"WHEN '{v[0]}' THEN '{v[0]}'" for v in TERRITORIES.values())}
                         ELSE 'US' END AS iso2,
                   CASE state {" ".join(f"WHEN '{v[0]}' THEN '{v[1]}'" for v in TERRITORIES.values())}
                         ELSE 'USA' END AS iso3,
                   state AS admin1
                FROM read_csv('{coverage}', header=true)""",
            sort=["state", "year"],
        )
    if dqi:
        lk.write(
            con,
            "dqi",
            f"SELECT *, 'US' AS iso2, 'USA' AS iso3 FROM read_csv('{dqi}', header=true)",
            sort=["fema", "year"],
        )
    print(f"  catalogue from R2: {pulled}; partial catalogues: {len(partials)}")
    path = lk.finish(partials=partials)
    if upload:
        lk.upload()
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--combine", nargs="*", type=Path)
    parser.add_argument("--mcc", type=Path)
    parser.add_argument("--counties", type=Path, help="Census cb_2020_us_county_20m.zip")
    parser.add_argument("--coverage", type=Path, help="EAGLE-I coverage_history.csv")
    parser.add_argument("--dqi", type=Path, help="EAGLE-I DQI.csv")
    parser.add_argument("--lake", type=Path, help="write the lake tables under this folder")
    parser.add_argument("--partials", nargs="*", type=Path, default=[])
    parser.add_argument("--upload", action="store_true", help="to R2 (GitHub Actions)")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    con = duckdb.connect()
    if args.year:
        load_year(con, args.csv)
        part = year_part(con, args.year)
        args.out.write_text(json.dumps(part, separators=(",", ":")), encoding="utf-8")
        print(
            f"{args.year}: {len(part['counties'])} counties, every {part['step_min']} min, "
            f"{sum(part['counties'].values()) / 1e6:.1f} M customer-hours, "
            f"largest event {part['events'][0] if part['events'] else None}"
        )
        if args.lake:
            year_lake(con, args.year, args.lake, args.upload)
        return
    parts = [json.loads(p.read_text(encoding="utf-8")) for p in args.combine]
    customers = read_mcc(args.mcc)
    out = combine(parts, customers)
    path = args.out or OUT
    path.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(
        f"{path}: years {out['years']}, {len(out['counties'])} counties, "
        f"{path.stat().st_size / 1e6:.2f} MB, top event {out['events'][:1]}"
    )
    if args.counties:
        outlines = counties_outlines(con, args.counties)
        COUNTIES_OUT.write_text(json.dumps(outlines, separators=(",", ":")), encoding="utf-8")
        codes = {c["code"] for c in outlines["counties"]}
        missing = sorted(set(out["counties"]) - codes)
        print(
            f"{COUNTIES_OUT}: {COUNTIES_OUT.stat().st_size / 1e6:.1f} MB; "
            f"{len(missing)} EAGLE-I counties without an outline: {missing[:20]}"
        )
    if args.lake:
        small_tables_lake(
            con,
            args.lake,
            out["names"],
            customers,
            args.coverage,
            args.dqi,
            args.partials,
            args.upload,
        )


if __name__ == "__main__":
    main()
