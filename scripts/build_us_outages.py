"""US power outages per county (EAGLE-I, ORNL; figshare article 24237376, CC BY 4.0).

EAGLE-I records, every 15 minutes, the customers without power per county as utilities
report them (rows only where customers are out; "customers" are utility meters, not people).
One CSV per year, 0.08-1.4 GB each: .github/workflows/us-outages.yml runs one job per year
(DuckDB over the CSV) and a last job combining them; nothing large runs on a laptop.

Per year (`--year`): for each county the customer-hours without power (sum of customers out
x 0.25 h, computed) and, for each day, the largest number of customers out at one moment in
the country (sum over counties at one 15-min timestamp, computed), when, and the state with
the most customers out at that moment.

Combine (`--combine`): writes frontend/public/data/eu/us_outages.json:
  {"fetched", "source", "years", "partial": {year: note}, "customers": {fips: n},
   "counties": {fips: [customer-hours per year]}, "names": {fips: "County, State"},
   "national": [customer-hours per year], "top_days": [[date, peak, at, state, state peak]]}
customers per county: EAGLE-I's MCC.csv (ORNL's modelled customer count per county), used to
show hours without power per customer (customer-hours / customers, computed).
County outlines: Census cartographic boundaries 1:20m (public domain), simplified, written to
frontend/public/data/us/counties.json in the shape of us/states.json.

    python scripts/build_us_outages.py --year 2024 --csv eaglei_outages_2024.csv --out part-2024.json
    python scripts/build_us_outages.py --combine part-*.json --mcc MCC.csv --counties cb_2024_us_county_20m.zip
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu" / "us_outages.json"
COUNTIES_OUT = ROOT / "frontend" / "public" / "data" / "us" / "counties.json"
SOURCE = "EAGLE-I recorded electricity outages (Oak Ridge National Laboratory, CC BY 4.0)"
TOP_DAYS = 50
# years EAGLE-I does not cover whole (its own documentation and coverage_history.csv)
PARTIAL = {2014: "from 1 November"}


def year_part(csv_path: Path, year: int) -> dict:
    import duckdb

    con = duckdb.connect()
    cols = [
        r[0]
        for r in con.execute(
            f"DESCRIBE SELECT * FROM read_csv_auto('{csv_path}', all_varchar=true)"
        ).fetchall()
    ]
    out_col = "customers_out" if "customers_out" in cols else "sum"
    src = f"""(SELECT lpad(fips_code, 5, '0') AS fips, county, state,
                      TRY_CAST({out_col} AS DOUBLE) AS out, CAST(run_start_time AS TIMESTAMP) AS ts
               FROM read_csv_auto('{csv_path}', all_varchar=true))"""
    counties = con.execute(
        f"SELECT fips, any_value(county), any_value(state), sum(out) * 0.25 FROM {src} GROUP BY fips"
    ).fetchall()
    days = con.execute(
        f"""
        WITH nat AS (SELECT ts, sum(out) AS n FROM {src} GROUP BY ts),
             st AS (SELECT ts, state, sum(out) AS n FROM {src} GROUP BY ts, state),
             peak AS (SELECT CAST(ts AS DATE) AS d, arg_max(ts, n) AS ts, max(n) AS n FROM nat GROUP BY d)
        SELECT CAST(p.d AS VARCHAR), p.n, strftime(p.ts, '%Y-%m-%d %H:%M'), arg_max(st.state, st.n), max(st.n)
        FROM peak p JOIN st ON st.ts = p.ts GROUP BY p.d, p.n, p.ts ORDER BY p.d
        """
    ).fetchall()
    return {
        "year": year,
        "counties": {f: round(ch) for f, _, _, ch in counties if ch},
        "names": {f: f"{c}, {s}" for f, c, s, _ in counties},
        "days": [[d, round(n), at, s, round(sn)] for d, n, at, s, sn in days],
    }


def counties_outlines(zip_path: Path) -> dict:
    """Census cartographic boundary counties (shapefile in a zip) -> us/states.json's shape."""
    import shapefile  # pyshp
    import shapely.geometry

    z = zipfile.ZipFile(zip_path)
    stem = next(n[:-4] for n in z.namelist() if n.endswith(".shp"))
    r = shapefile.Reader(
        shp=io.BytesIO(z.read(stem + ".shp")),
        dbf=io.BytesIO(z.read(stem + ".dbf")),
        shx=io.BytesIO(z.read(stem + ".shx")),
    )
    fields = [f[0] for f in r.fields[1:]]
    out = []
    for sr in r.iterShapeRecords():
        rec = dict(zip(fields, sr.record, strict=True))
        geom = shapely.geometry.shape(sr.shape.__geo_interface__).simplify(0.01)
        parts = getattr(geom, "geoms", [geom])
        polys = []
        for p in parts:
            if p.is_empty or p.geom_type != "Polygon":
                continue
            rings = [p.exterior, *p.interiors]
            polys.append([[round(v, 3) for xy in ring.coords for v in xy] for ring in rings])
        c = geom.representative_point()
        out.append(
            {
                "code": rec["GEOID"],
                "name": rec["NAME"],
                "state": rec.get("STUSPS") or rec.get("STATE_NAME") or rec["STATEFP"],
                "label": [round(c.x, 3), round(c.y, 3)],
                "polygons": polys,
            }
        )
    return {
        "source": "US Census Bureau, cartographic boundary file, counties 1:20m (public domain)",
        "counties": out,
    }


def combine(parts: list[dict], mcc: Path) -> dict:
    parts = sorted(parts, key=lambda p: p["year"])
    years = [p["year"] for p in parts]
    counties: dict[str, list] = {}
    names: dict[str, str] = {}
    for k, p in enumerate(parts):
        names.update(p["names"])
        for f, ch in p["counties"].items():
            counties.setdefault(f, [None] * len(years))[k] = ch
    with mcc.open(encoding="utf-8-sig") as fh:
        customers = {
            str(r["County_FIPS"]).zfill(5): int(float(r["Customers"]))
            for r in csv.DictReader(fh)
            if r["Customers"]
        }
    days = [d for p in parts for d in p["days"]]
    return {
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": SOURCE,
        "years": years,
        "partial": {str(y): PARTIAL[y] for y in years if y in PARTIAL},
        "customers": customers,
        "counties": dict(sorted(counties.items())),
        "names": dict(sorted(names.items())),
        "national": [sum(p["counties"].values()) for p in parts],
        "top_days": sorted(days, key=lambda d: -d[1])[:TOP_DAYS],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--combine", nargs="*", type=Path)
    parser.add_argument("--mcc", type=Path)
    parser.add_argument("--counties", type=Path, help="Census cb_*_us_county_20m.zip")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.year:
        part = year_part(args.csv, args.year)
        args.out.write_text(json.dumps(part, separators=(",", ":")), encoding="utf-8")
        print(
            f"{args.year}: {len(part['counties'])} counties, {sum(part['counties'].values()) / 1e6:.1f} M customer-hours"
        )
        return
    out = combine([json.loads(p.read_text(encoding="utf-8")) for p in args.combine], args.mcc)
    path = args.out or OUT
    path.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(
        f"{path}: years {out['years']}, {len(out['counties'])} counties, top day {out['top_days'][0]}"
    )
    if args.counties:
        COUNTIES_OUT.write_text(
            json.dumps(counties_outlines(args.counties), separators=(",", ":")), encoding="utf-8"
        )
        print(f"{COUNTIES_OUT}: {COUNTIES_OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
