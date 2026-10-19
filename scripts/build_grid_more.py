"""Grid and networks (brief 21, group B): from our lake and public sources.

    python scripts/build_grid_more.py substations|operators|utilities|emodnet [--lake lake-out] [--upload]

substations  Every substation in the lake's Overture power extract (`lake/overture_power/sites`,
             class "substation"; OpenStreetMap via Overture Maps, ODbL): one point each (the
             centroid of a mapped outline, computed), kV as tagged (the highest), name, operator ->
             GeoJSONSeq for tippecanoe -> `grid/world-substations.pmtiles` on R2 (the workflow
             cuts and uploads it), read by "Check a site" outside Europe.
operators    Germany's grid operator per municipality from the lake's MaStR snapshot: each unit's
             location (`location_nr`) -> its grid connection points -> the grid operator's MaStR
             number -> the operator's name (`operators`). Computed per municipality (AGS): the
             operator with most units connected, its share of the units, and the number of
             operators -> frontend/public/data/eu/de_grid_operators.json; lake `mastr_grid/operators`.
utilities    EIA-861 service territories (PUDL `core_eia861__yearly_service_territory`, in place,
             CC BY 4.0): the utilities serving each county in the newest year, as reported ->
             frontend/public/data/us/utilities.json (no lake copy: PUDL is the store).
emodnet      EMODnet Human Activities (CC BY 4.0, WFS, no key): power cables in European seas (the
             national `pcables*` layers) and pipelines at sea -> frontend/public/data/eu/sea_cables.json;
             lines simplified 0.002 degrees (shapely), attributes as published.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import wave5_common as w

TMP = Path("/tmp/wave6/grid")
PUDL = "https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/stable"
WFS = "https://ows.emodnet-humanactivities.eu/wfs"
SITES = "r2://infraatlas-raw/lake/overture_power/sites/*/*.parquet"
MASTR = "r2://infraatlas-raw/lake/mastr"


def duck():  # noqa: ANN201 - a DuckDB connection with httpfs, spatial and the lake's R2 secret
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial")
    key, secret = os.environ.get("AWS_ACCESS_KEY_ID"), os.environ.get("AWS_SECRET_ACCESS_KEY")
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if key and secret and acct:
        con.execute(
            f"CREATE SECRET lake (TYPE r2, KEY_ID '{key}', SECRET '{secret}', ACCOUNT_ID '{acct}')"
        )
    return con


# ---------------------------------------------------------------- substations worldwide


def minzoom(kv: int | None) -> int:
    """Shown on a map from: 220 kV and more at zoom 4, 60 kV and more at 6, the rest at 8."""
    return 4 if (kv or 0) >= 220 else 6 if (kv or 0) >= 60 else 8


def substation_feature(
    lon: float, lat: float, kv: int | None, name: str | None, operator: str | None, iso3: str | None
) -> dict:
    props = {
        k: v
        for k, v in {"kv": kv, "name": name, "operator": operator, "iso3": iso3}.items()
        if v not in (None, "")
    }
    return {"type": "Feature", "tippecanoe": {"minzoom": minzoom(kv)}, "properties": props,
            "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]}}  # fmt: skip


def build_substations(args: argparse.Namespace) -> None:
    con = duck()
    rel = con.execute(
        f"SELECT max(release) FROM read_parquet('{SITES}', hive_partitioning = 1)"
    ).fetchone()[0]  # type: ignore[index]
    rows = con.execute(
        f"""SELECT ST_X(c), ST_Y(c), kv, name, operator, iso3 FROM (
              SELECT ST_Centroid(geometry) AS c, kv, name, operator, iso3
              FROM read_parquet('{SITES}', hive_partitioning = 1)
              WHERE release = '{rel}' AND class = 'substation') WHERE c IS NOT NULL"""
    ).fetchall()
    TMP.mkdir(parents=True, exist_ok=True)
    out = TMP / "substations.geojsons"
    kv = Counter()
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            kv[
                "220+"
                if (r[2] or 0) >= 220
                else "60-219"
                if (r[2] or 0) >= 60
                else "under 60"
                if r[2]
                else "not tagged"
            ] += 1
            f.write(json.dumps(substation_feature(*r), ensure_ascii=False) + "\n")
    print(f"  release {rel}: {len(rows):,} substations; by kV {dict(kv)}", flush=True)
    (TMP / "substations-summary.json").write_text(
        json.dumps({"release": rel, "count": len(rows), "kv": kv}), encoding="utf-8"
    )


# ---------------------------------------------------------------- Germany: grid operator per municipality


def find(cols: list[str], *patterns: str) -> str:
    for p in patterns:
        for c in cols:
            if re.fullmatch(p, c, re.I):
                return c
    raise SystemExit(f"no column like {patterns} in {cols}")


def top_operator(counts: dict[str, int]) -> tuple[str, int, int, int]:
    """(operator with most units, its units, operators, units) for one municipality."""
    best = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return best[0], best[1], len(counts), sum(counts.values())


def build_operators(args: argparse.Namespace) -> None:
    con = duck()
    snap = con.execute(
        f"SELECT max(snapshot) FROM read_parquet('{MASTR}/operators/*/*.parquet', hive_partitioning = 1)"
    ).fetchone()[0]  # type: ignore[index]

    def src(t: str) -> str:
        return f"read_parquet('{MASTR}/{t}/snapshot={snap}/**/*.parquet', hive_partitioning = 1, union_by_name = true)"

    gcp_cols = [
        r[0]
        for r in con.execute(f"DESCRIBE SELECT * FROM {src('grid_connection_points')}").fetchall()
    ]
    op_cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src('operators')}").fetchall()]
    print(f"  snapshot {snap}; grid_connection_points columns {gcp_cols[:40]}", flush=True)
    loc = find(gcp_cols, r"LokationMa[Ss]t[Rr]Nummer", r"location_nr", r".*Lokation.*Nummer.*")
    net = find(
        gcp_cols,
        r"NetzbetreiberMa[Ss]t[Rr]Nummer",
        r".*Netzbetreiber.*Nummer.*",
        r"grid_operator_nr",
    )
    op_id = find(op_cols, r"MastrNummer", r"mastr_nr")
    op_name = find(op_cols, r"Firmenname", r"name", r".*Name.*")
    units = [
        "units_solar",
        "units_wind",
        "units_storage",
        "units_biomass",
        "units_hydro",
        "units_combustion",
        "units_other",
    ]
    unions = " UNION ALL ".join(f"SELECT ags, location_nr FROM {src(t)}" for t in units)
    con.execute(
        f"""CREATE TABLE per_ags AS
            WITH u AS ({unions}),
                 g AS (SELECT DISTINCT "{loc}" AS location_nr, "{net}" AS grid_nr FROM {src("grid_connection_points")} WHERE "{net}" IS NOT NULL)
            SELECT u.ags, g.grid_nr, count(*) AS units
            FROM u JOIN g USING (location_nr)
            WHERE u.ags IS NOT NULL
            GROUP BY 1, 2"""
    )
    names = dict(con.execute(f'SELECT "{op_id}", "{op_name}" FROM {src("operators")}').fetchall())
    by: dict[str, dict[str, int]] = defaultdict(dict)
    for ags, nr, n in con.execute("SELECT * FROM per_ags").fetchall():
        by[ags][nr] = n
    total_units = con.execute(f"SELECT count(*), count(location_nr) FROM ({unions})").fetchone()
    out = {}
    for ags, counts in by.items():
        nr, n, ops, all_n = top_operator(counts)
        out[ags] = [names.get(nr) or nr, nr, n, ops, all_n]
    print(f"  {len(out):,} municipalities; units (all, with a location) {total_units}", flush=True)
    w.write_json(w.EU / "de_grid_operators.json", {
        "fetched": w.now(), "snapshot": str(snap),
        "source": "Marktstammdatenregister (Bundesnetzagentur, dl-de/by-2-0): units -> locations -> grid connection points -> grid operator",
        # AGS -> [operator name, operator MaStR number, its units, operators, units connected]
        "municipalities": out,
    })  # fmt: skip
    lk = w.lake_for(
        "mastr_grid",
        args.lake,
        "Marktstammdatenregister (Bundesnetzagentur)",
        "dl-de/by-2-0",
        "scripts/build_grid_more.py",
        str(snap),
    )
    con.execute("CREATE TABLE names AS SELECT * FROM (VALUES ('', '')) t(nr, name) WHERE false")
    con.executemany("INSERT INTO names VALUES (?, ?)", list(names.items()))
    lk.write(
        con, "operators",
        """SELECT p.ags, p.grid_nr AS grid_operator_nr, n.name AS grid_operator, p.units,
                  'DE' AS iso2, 'DEU' AS iso3, NULL::VARCHAR AS admin1
           FROM per_ags p LEFT JOIN names n ON n.nr = p.grid_nr""",
        sort=["ags", "grid_operator_nr"], partition={"snapshot": str(snap)},
    )  # fmt: skip
    w.lake_done(lk, args.upload)


# ---------------------------------------------------------------- US utility service territories


def build_utilities(args: argparse.Namespace) -> None:
    con = duck()
    url = f"{PUDL}/core_eia861__yearly_service_territory.parquet"
    # the newest year reported for most counties (county_id_fips is the 5-digit county code)
    year = con.execute(
        f"""SELECT max(report_date) FROM (SELECT report_date, count(DISTINCT county_id_fips) n
            FROM '{url}' GROUP BY 1) WHERE n >= 2500"""
    ).fetchone()[0]  # type: ignore[index]
    rows = con.execute(
        f"""SELECT lpad(CAST(county_id_fips AS VARCHAR), 5, '0') AS fips,
                   utility_id_eia, utility_name_eia, state, county
            FROM '{url}' WHERE report_date = '{year}' AND county_id_fips IS NOT NULL
            ORDER BY fips, utility_name_eia"""
    ).fetchall()
    counties: dict[str, list[int]] = defaultdict(list)
    utilities: dict[int, str] = {}
    states: dict[str, set[int]] = defaultdict(set)
    for fips, uid, name, st, _county in rows:
        if int(fips[2:]) == 0:
            continue
        uid = int(uid)
        utilities[uid] = name
        if uid not in counties[fips]:
            counties[fips].append(uid)
        states[st].add(uid)
    print(
        f"  {str(year)[:4]}: {len(rows):,} rows, {len(counties):,} counties, {len(utilities):,} utilities",
        flush=True,
    )
    w.write_json(w.US / "utilities.json", {
        "fetched": w.now(), "year": str(year)[:4],
        "source": "EIA-861 service territory (via PUDL core_eia861__yearly_service_territory, CC BY 4.0)",
        "utilities": {str(k): v for k, v in sorted(utilities.items())},
        # county FIPS -> utility ids serving it, as reported
        "counties": counties,
        "states": {s: len(v) for s, v in sorted(states.items())},
    })  # fmt: skip


# ---------------------------------------------------------------- EMODnet sea cables and pipelines


def wfs(layer: str) -> list[dict]:
    params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": layer,
              "outputFormat": "application/json", "srsName": "EPSG:4326"}  # fmt: skip
    d = w.get_json(WFS + "?" + "&".join(f"{k}={v}" for k, v in params.items()), timeout=600)
    return d["features"]  # type: ignore[index]


def lines_of(geom: dict) -> list[list[float]]:
    """A (multi)line as flat lon/lat lists, simplified 0.002 degrees, 4 decimals."""
    import shapely
    from shapely.geometry import shape

    g = shapely.simplify(shape(geom), 0.002)
    parts = [g] if g.geom_type == "LineString" else list(getattr(g, "geoms", []))
    return [
        [round(c, 4) for xy in p.coords for c in xy[:2]]
        for p in parts
        if p.geom_type == "LineString" and len(p.coords) > 1
    ]


def clean(v: object) -> object:
    if isinstance(v, str):
        v = v.strip()
        return None if v in ("", "n/a", "N/A", "-") else v
    return v


def build_emodnet(args: argparse.Namespace) -> None:
    import httpx

    xml = httpx.get(
        WFS,
        params={"service": "WFS", "request": "GetCapabilities", "version": "2.0.0"},
        timeout=120,
    ).text
    layers = sorted(set(re.findall(r"<(?:wfs:)?Name>(emodnet:pcables[a-z]*)</", xml)))
    cables, pipes = [], []
    for layer in layers:
        feats = wfs(layer)
        for f in feats:
            p = {k: clean(v) for k, v in (f.get("properties") or {}).items()}
            name = p.get("name") or p.get("name_") or p.get("naam") or p.get("omschrijvi")
            status = p.get("status") or p.get("rpl_status")
            for flat in lines_of(f["geometry"]) if f.get("geometry") else []:
                cables.append([layer.split(":")[1], name, status, flat])
        print(f"  {layer}: {len(feats)} features", flush=True)
    feats = wfs("emodnet:pipelines")
    media = Counter()
    for f in feats:
        p = {k: clean(v) for k, v in (f.get("properties") or {}).items()}
        media[p.get("medium")] += 1
        for flat in lines_of(f["geometry"]) if f.get("geometry") else []:
            pipes.append(
                [
                    p.get("name"),
                    p.get("medium"),
                    p.get("status"),
                    p.get("operator"),
                    p.get("country"),
                    p.get("size_in"),
                    flat,
                ]
            )
    print(f"  pipelines: {len(feats)} features; media {media.most_common(12)}", flush=True)
    w.write_json(w.EU / "sea_cables.json", {
        "fetched": w.now(), "source": "EMODnet Human Activities (CC BY 4.0), WFS", "layers": layers,
        # [EMODnet layer, name, status, flat lon/lat]
        "cables": cables,
        # [name, medium, status, operator, country, size (inches), flat lon/lat]
        "pipelines": pipes,
    })  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["substations", "operators", "utilities", "emodnet"])
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    {
        "substations": build_substations,
        "operators": build_operators,
        "utilities": build_utilities,
        "emodnet": build_emodnet,
    }[args.what](args)


if __name__ == "__main__":
    main()
