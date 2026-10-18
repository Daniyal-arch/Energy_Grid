"""Every wind turbine and solar farm worldwide: Global Renewables Watch (brief 17, dataset 12).

Microsoft / Planet, MIT licence (probe: GitHub licence API), release v1.0: `solar_all_2024q2_v1.gpkg`
(395 MB, polygons) and `wind_all_2024q2_v1.gpkg` (58 MB, points), detected from satellite images
up to 2024 Q2. Downloaded and processed in GitHub Actions only.

Passed through: every feature with its published fields. Computed: the country (the feature's
centroid inside `world.json`'s outline; offshore and coastal features outside every outline stay
without a country), a polygon's area in km2 (for the tiles' zoom levels and the card; equal-area
approximation: area in square degrees x 111.2 km x 111.2 km x cos(latitude)), and per country the
count of turbines and of solar polygons and the solar area (sums), by the quarter field the files
carry (else the release quarter, 2024 Q2).

-> R2 public `grid/grw.pmtiles` (tippecanoe: layer `wind` points, layer `solar` polygons; small
polygons only when zoomed in); frontend/public/data/eu/grw_countries.json; lake `grw/solar`,
`grw/wind` (GeoParquet).

    python scripts/build_grw.py [--lake lake-out] [--upload]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import wave5_common as w

BASE = "https://github.com/microsoft/global-renewables-watch/releases/download/v1.0"
FILES = {"solar": "solar_all_2024q2_v1.gpkg", "wind": "wind_all_2024q2_v1.gpkg"}
RELEASE_QUARTER = "2024Q2"
TMP = Path("/tmp/wave5/grw")
KM_PER_DEG = 111.2


def find(cols: list[str], pattern: str) -> str | None:
    return next((c for c in cols if re.search(pattern, c, re.I)), None)


def quarter_of(v: object) -> str:
    """A quarter label from a published value: '2023Q4', a date '2023-11-02', or a year."""
    s = str(v or "").strip()
    m = re.match(r"(\d{4})\s*-?\s*Q([1-4])", s, re.I)
    if m:
        return f"{m.group(1)}Q{m.group(2)}"
    m = re.match(r"(\d{4})-(\d{2})", s)
    if m:
        return f"{m.group(1)}Q{(int(m.group(2)) - 1) // 3 + 1}"
    return s[:4] if s[:4].isdigit() else RELEASE_QUARTER


def main() -> None:
    import duckdb

    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--tiles", action="store_true", help="cut grid/grw.pmtiles with tippecanoe")
    args = ap.parse_args()
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    con.execute(
        f"CREATE TABLE world AS SELECT iso3, name, geom FROM ST_Read('{w.EU / 'world.json'}')"
    )
    import lake

    lake.iso_codes(con)
    lk = w.lake_for(
        "grw",
        args.lake,
        "Global Renewables Watch v1.0 (Microsoft, Planet)",
        "MIT",
        "scripts/build_grw.py",
        RELEASE_QUARTER,
    )
    summary: dict[str, dict] = {}
    fields: dict[str, dict] = {}
    for kind, name in FILES.items():
        src = w.download(f"{BASE}/{name}", TMP / name)
        con.execute(f"CREATE OR REPLACE TABLE {kind} AS SELECT * FROM ST_Read('{src}')")
        cols = [r[0] for r in con.execute(f"DESCRIBE {kind}").fetchall()]
        geom = find(cols, r"^geom$|^geometry$|^shape$") or "geom"
        cap = find(cols, r"capacity|_mw$|^mw$|power")
        when = find(cols, r"quarter|construct|first|date|year")
        n = con.execute(f"SELECT count(*) FROM {kind}").fetchone()[0]  # type: ignore[index]
        print(f"  {name}: {n:,} features; columns {cols}; capacity {cap}; time {when}", flush=True)
        fields[kind] = {"capacity": cap, "time": when, "count": n}
        area = (
            f"ST_Area({geom}) * {KM_PER_DEG}^2 * cos(radians(ST_Y(ST_Centroid({geom}))))"
            if kind == "solar"
            else "NULL::DOUBLE"
        )
        con.execute(
            f"""CREATE OR REPLACE TABLE {kind}_x AS
                SELECT t.* EXCLUDE ({geom}), t.{geom} AS geometry, {area} AS area_km2, w.iso3
                FROM {kind} t LEFT JOIN world w ON ST_Intersects(w.geom, ST_Centroid(t.{geom}))"""
        )
        q = when or "NULL"
        rows = con.execute(
            f"SELECT iso3, {q}, count(*), sum(area_km2), {f'sum({cap})' if cap else 'NULL'} FROM {kind}_x GROUP BY ALL"
        ).fetchall()
        for iso3, t, cnt, km2, mw in rows:
            d = summary.setdefault(iso3 or "none", {}).setdefault(kind, {})
            qq = quarter_of(t) if when else RELEASE_QUARTER
            prev = d.get(qq, [0, 0.0, None])
            d[qq] = [
                prev[0] + cnt,
                round(prev[1] + (km2 or 0), 3),
                None if mw is None else round((prev[2] or 0) + mw, 1),
            ]
        lk.write(
            con,
            kind,
            f"""SELECT x.*, i.iso2, NULL::VARCHAR AS admin1 FROM {kind}_x x LEFT JOIN iso_codes i ON i.iso3 = x.iso3""",
            sort=[lake.hilbert()],
            partition={"release": RELEASE_QUARTER},
            geometry="geometry",
        )
        if args.tiles:
            seq = TMP / f"{kind}.geojsons"
            props = "area_km2" if kind == "solar" else ""
            sel = f"SELECT {props + ', ' if props else ''}{cap + ', ' if cap else ''}geometry FROM {kind}_x"
            con.execute(f"COPY ({sel}) TO '{seq}' (FORMAT GDAL, DRIVER 'GeoJSONSeq')")
    w.write_json(
        w.EU / "grw_countries.json",
        {
            "fetched": w.now(),
            "source": "Global Renewables Watch v1.0 (Microsoft, Planet; MIT): solar_all_2024q2_v1, wind_all_2024q2_v1",
            "release": RELEASE_QUARTER,
            "fields": fields,
            "columns": [
                "count",
                "area km2 (computed)",
                "MW as published (null: the files publish none)",
            ],
            "countries": summary,
        },
    )
    w.lake_done(lk, args.upload)
    if args.tiles:
        out = TMP / "grw.pmtiles"
        subprocess.run(
            [
                "tippecanoe", "-o", str(out), "--force", "-Z0", "-z12",
                "-L", f"solar:{TMP / 'solar.geojsons'}", "-L", f"wind:{TMP / 'wind.geojsons'}",
                # large arrays from the start, small ones only when zoomed in
                "-j", json.dumps({"solar": ["any", [">=", "$zoom", 10], [">=", "area_km2", 1],
                                            ["all", [">=", "$zoom", 6], [">=", "area_km2", 0.05]]]}),
                "--drop-densest-as-needed", "--extend-zooms-if-still-dropping",
                "--simplification=4", "--no-tile-size-limit",
                "--attribution=Global Renewables Watch (Microsoft, Planet), MIT",
            ],
            check=True,
        )  # fmt: skip
        print(f"  {out}: {out.stat().st_size / 1e6:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
