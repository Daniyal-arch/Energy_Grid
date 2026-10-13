"""Water risk per river basin: WRI Aqueduct 4.0 (CC BY 4.0), map file and lake tables.

Source: https://files.wri.org/aqueduct/aqueduct-4-0-water-risk-data.zip (262 MB; downloaded in
GitHub Actions by .github/workflows/water-risk.yml). The zip holds a File Geodatabase with three
layers (baseline_annual: 68,506 units = HydroBASINS level-6 basin x province x aquifer;
baseline_monthly and future_annual: 16,395 basins, `pfaf_id`) and the same tables as CSV. The
data dictionary is github.com/wri/Aqueduct40.

Map file frontend/public/data/eu/water.json: per basin (`pfaf_id`) WRI's category of
baseline water stress (bws), riverine flood risk (rfr), coastal flood risk (cfr) and drought
risk (drr), with WRI's own labels; outlines from the basin layer, simplified until the file
stays under MAX_BYTES. Where a basin's units carry different categories (an indicator WRI
computes per unit, not per basin), the map takes the highest (computed, counted in `mixed`).

    {"fetched", "source", "indicators": {"bws": {"name", "labels": {cat: label}}, ...},
     "order": ["bws", "rfr", "cfr", "drr"], "mixed": {ind: basins}, "tolerance",
     "basins": [{"id": pfaf_id, "c": [cat per indicator, null = no data], "polygons": [[flat ring]]}]}

Lake (lake/aqueduct/v4.0/): baseline_annual (GeoParquet, every indicator), basins
(GeoParquet), baseline_monthly (long: pfaf_id, month), future_annual (long: pfaf_id,
scenario, year).

    python scripts/build_aqueduct.py --zip aqueduct-4-0-water-risk-data.zip --lake lake-out [--upload]
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import lake

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu" / "water.json"
SOURCE = "WRI Aqueduct 4.0 water risk atlas (World Resources Institute, CC BY 4.0)"
URL = "https://files.wri.org/aqueduct/aqueduct-4-0-water-risk-data.zip"
VERSION = "Y2023M07D05"
MAX_BYTES = 5_000_000
TOLERANCES = [0.02, 0.04, 0.06, 0.1, 0.15, 0.2, 0.3]
# the 13 indicators (data dictionary)
INDICATORS = {
    "bws": "Baseline water stress",
    "bwd": "Baseline water depletion",
    "iav": "Interannual variability",
    "sev": "Seasonal variability",
    "gtd": "Groundwater table decline",
    "rfr": "Riverine flood risk",
    "cfr": "Coastal flood risk",
    "drr": "Drought risk",
    "ucw": "Unimproved/no drinking water",
    "cep": "Coastal eutrophication potential",
    "udw": "Unimproved/no sanitation",
    "usa": "Untreated connected wastewater",
    "rri": "Peak RepRisk country ESG risk index",
}
MAP_INDICATORS = ["bws", "rfr", "cfr", "drr"]
# future_annual: scenario x year columns (`bau30_ws_x_r`): business as usual, optimistic,
# pessimistic; 2030, 2050, 2080; indicators and suffixes as the data dictionary names them
FUTURE_SCENARIOS = {"bau": "business as usual", "opt": "optimistic", "pes": "pessimistic"}
FUTURE_YEARS = {"30": 2030, "50": 2050, "80": 2080}
FUTURE_SUFFIX = {"r": "raw", "s": "score", "c": "cat", "l": "label"}


def gdb_path(zip_path: Path) -> str:
    return f"/vsizip/{zip_path}/Aqueduct40_waterrisk_download_{VERSION}/GDB/Aq40_Y2023D07M05.gdb"


CASTS = {"raw": "DOUBLE", "score": "FLOAT", "weight_fraction": "FLOAT", "cat": "SMALLINT"}


def typed(col: str, alias: str | None = None) -> str:
    """The lake's types: _raw DOUBLE, _score FLOAT, _cat SMALLINT (WRI's -9999 = no data
    does not fit a TINYINT), _label VARCHAR; other columns as read."""
    alias = alias or col
    for suffix, kind in CASTS.items():
        if col.endswith("_" + suffix):
            return f'CAST("{col}" AS {kind}) AS "{alias}"'
    return f'"{col}" AS "{alias}"'


def load(con: duckdb.DuckDBPyConnection, gdb: str) -> None:
    """The GDB's three layers as tables `annual` (68,506 units), `monthly` and `future`
    (16,395 basins each), with their geometry."""
    con.execute("INSTALL spatial; LOAD spatial")
    con.execute(f"CREATE TABLE annual AS SELECT * FROM ST_Read('{gdb}', layer='baseline_annual')")
    con.execute(f"CREATE TABLE monthly AS SELECT * FROM ST_Read('{gdb}', layer='baseline_monthly')")
    con.execute(f"CREATE TABLE future AS SELECT * FROM ST_Read('{gdb}', layer='future_annual')")
    for t in ("annual", "monthly", "future"):
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]  # type: ignore[index]
        print(f"  {t}: {n:,} rows", flush=True)


def columns(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    return [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]


def geom_col(con: duckdb.DuckDBPyConnection, table: str) -> str:
    return next(r[0] for r in con.execute(f"DESCRIBE {table}").fetchall() if "GEOMETRY" in r[1])


def basin_country(con: duckdb.DuckDBPyConnection) -> None:
    """`basin_iso`: per basin the country (GADM gid_0) and province holding most of its area
    (sum of area_km2 over the basin's units, computed)."""
    lake.iso_codes(con)
    con.execute(
        """CREATE TABLE basin_iso AS
           WITH a AS (SELECT pfaf_id, gid_0, name_1, sum(area_km2) AS km2
                      FROM annual WHERE gid_0 IS NOT NULL AND gid_0 <> '-9999'
                      GROUP BY ALL),
                c AS (SELECT pfaf_id, gid_0, sum(km2) AS km2 FROM a GROUP BY ALL),
                top AS (SELECT pfaf_id, arg_max(gid_0, km2) AS iso3 FROM c GROUP BY pfaf_id)
           SELECT t.pfaf_id, t.iso3, arg_max(a.name_1, a.km2) AS admin1
           FROM top t JOIN a ON a.pfaf_id = t.pfaf_id AND a.gid_0 = t.iso3
           GROUP BY t.pfaf_id, t.iso3"""
    )


def write_lake(con: duckdb.DuckDBPyConnection, root: Path, upload: bool) -> Path:
    lk = lake.Lake(
        "aqueduct",
        root,
        source=f"{SOURCE}; {URL}",
        licence="CC BY 4.0",
        script="scripts/build_aqueduct.py",
        source_version=f"4.0 ({VERSION})",
    )
    # GDB copies of joined fields (`string_id_1`, `aq30_id_1`, `pfaf_id_1`, `fid_1`) and
    # ArcGIS's shape fields are left out; everything else as published
    drop = re.compile(r"^(.*_1|fid|Shape_Leng|Shape_Length|Shape_Area)$")
    g = geom_col(con, "annual")
    keep = [c for c in columns(con, "annual") if c != g and not drop.match(c)]
    iso2 = "coalesce(i.iso2, CASE a.gid_0 WHEN 'XKO' THEN 'XK' END)"
    lk.write(
        con,
        "baseline_annual",
        f"""SELECT {", ".join(typed(c) for c in keep)},
                   {iso2} AS iso2, a.gid_0 AS iso3, a.name_1 AS admin1, a."{g}" AS geometry
            FROM annual a LEFT JOIN iso_codes i ON i.iso3 = a.gid_0""",
        sort=[
            "ST_Hilbert(geometry, {'min_x': -180, 'min_y': -90, 'max_x': 180, 'max_y': 90}::BOX_2D)"
        ],
        bloom=["pfaf_id", "aq30_id"],
        geometry="geometry",
    )
    gm = geom_col(con, "monthly")
    keys = "coalesce(i.iso2, CASE b.iso3 WHEN 'XKO' THEN 'XK' END) AS iso2, b.iso3, b.admin1"
    lk.write(
        con,
        "basins",
        f"""SELECT m.pfaf_id, {keys}, m."{gm}" AS geometry
            FROM monthly m LEFT JOIN basin_iso b USING (pfaf_id)
            LEFT JOIN iso_codes i ON i.iso3 = b.iso3""",
        sort=[
            "ST_Hilbert(geometry, {'min_x': -180, 'min_y': -90, 'max_x': 180, 'max_y': 90}::BOX_2D)"
        ],
        bloom=["pfaf_id"],
        geometry="geometry",
    )
    # monthly: one row per basin and month
    mcols = columns(con, "monthly")
    inds = sorted({m.group(1) for c in mcols if (m := re.match(r"^([a-z]{3})_01_raw$", c))})
    months = []
    for k in range(1, 13):
        parts = [
            typed(f"{ind}_{k:02d}_{s}", f"{ind}_{s}")
            for ind in inds
            for s in ("raw", "score", "cat", "label")
        ]
        months.append(f"SELECT pfaf_id, {k}::TINYINT AS month, {', '.join(parts)} FROM monthly")
    lk.write(
        con,
        "baseline_monthly",
        f"""SELECT u.*, {keys} FROM ({" UNION ALL ".join(months)}) u
            LEFT JOIN basin_iso b USING (pfaf_id) LEFT JOIN iso_codes i ON i.iso3 = b.iso3""",
        sort=["pfaf_id", "month"],
        bloom=["pfaf_id"],
    )
    # future: one row per basin, scenario and year
    fcols = set(columns(con, "future"))
    finds = sorted({m.group(1) for c in fcols if (m := re.match(r"^bau30_([a-z]{2})_x_r$", c))})
    rows = []
    for sc in FUTURE_SCENARIOS:
        for yy, year in FUTURE_YEARS.items():
            parts = []
            for ind in finds:
                for suf, name in FUTURE_SUFFIX.items():
                    col = f"{sc}{yy}_{ind}_x_{suf}"
                    # ba and ww publish only raw and label
                    kind = {"r": "DOUBLE", "s": "FLOAT", "c": "SMALLINT", "l": "VARCHAR"}[suf]
                    value = f'"{col}"' if col in fcols else "NULL"
                    parts.append(f'CAST({value} AS {kind}) AS "{ind}_{name}"')
            rows.append(
                f"SELECT pfaf_id, '{sc}' AS scenario, {year}::SMALLINT AS year, "
                f"{', '.join(parts)} FROM future"
            )
    lk.write(
        con,
        "future_annual",
        f"""SELECT u.*, {keys} FROM ({" UNION ALL ".join(rows)}) u
            LEFT JOIN basin_iso b USING (pfaf_id) LEFT JOIN iso_codes i ON i.iso3 = b.iso3""",
        sort=["pfaf_id", "scenario", "year"],
        bloom=["pfaf_id"],
    )
    path = lk.finish()
    if upload:
        lk.upload()
    return path


def map_file(con: duckdb.DuckDBPyConnection) -> dict:
    import shapely

    labels: dict[str, dict[str, str]] = {}
    for ind in MAP_INDICATORS:
        labels[ind] = {
            str(int(c)): lab
            for c, lab in con.execute(
                f"SELECT DISTINCT {ind}_cat, {ind}_label FROM annual "
                f"WHERE {ind}_cat IS NOT NULL ORDER BY 1"
            ).fetchall()
        }
    # per basin: the category if all its units agree, else the highest (counted)
    sel = ", ".join(
        f"max({i}_cat) FILTER (WHERE {i}_cat >= -1), count(DISTINCT {i}_cat) FILTER (WHERE {i}_cat >= -1)"
        for i in MAP_INDICATORS
    )
    cats: dict[int, list[int | None]] = {}
    mixed = dict.fromkeys(MAP_INDICATORS, 0)
    for row in con.execute(f"SELECT pfaf_id, {sel} FROM annual GROUP BY pfaf_id").fetchall():
        vals: list[int | None] = []
        for k, ind in enumerate(MAP_INDICATORS):
            v, n = row[1 + 2 * k], row[2 + 2 * k]
            vals.append(None if v is None else int(v))
            if n and n > 1:
                mixed[ind] += 1
        cats[int(row[0])] = vals
    g = geom_col(con, "monthly")
    shapes = [
        (int(pid), shapely.from_wkb(bytes(wkb)))
        for pid, wkb in con.execute(f'SELECT pfaf_id, ST_AsWKB("{g}") FROM monthly').fetchall()
    ]
    for tol in TOLERANCES:
        basins = []
        for pid, geom in shapes:
            simple = geom.simplify(tol, preserve_topology=True)
            polys = []
            for p in getattr(simple, "geoms", [simple]):
                if p.is_empty or p.geom_type != "Polygon" or p.area < tol * tol:
                    continue
                ring = [round(v, 2) for xy in p.exterior.coords for v in xy]
                polys.append([ring])
            if polys:
                basins.append({"id": pid, "c": cats.get(pid, [None] * 4), "polygons": polys})
        out = {
            "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
            "source": SOURCE,
            "version": f"4.0 ({VERSION})",
            "indicators": {i: {"name": INDICATORS[i], "labels": labels[i]} for i in MAP_INDICATORS},
            "order": MAP_INDICATORS,
            "mixed": mixed,
            "tolerance": tol,
            "basins": basins,
        }
        size = len(json.dumps(out, separators=(",", ":")))
        print(f"  tolerance {tol}°: {len(basins):,} basins, {size / 1e6:.2f} MB", flush=True)
        if size <= MAX_BYTES:
            return out
    raise SystemExit("water.json stays over the size limit")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--lake", type=Path)
    parser.add_argument("--upload", action="store_true", help="to R2 (GitHub Actions)")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    con = duckdb.connect()
    load(con, gdb_path(args.zip.resolve()))
    out = map_file(con)
    args.out.write_text(
        json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
    )
    print(f"{args.out}: {args.out.stat().st_size / 1e6:.2f} MB; mixed {out['mixed']}")
    if args.lake:
        basin_country(con)
        write_lake(con, args.lake, args.upload)


if __name__ == "__main__":
    main()
