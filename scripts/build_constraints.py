"""What stops a build (brief 21, group C): protected areas, river flood hazard, major roads and rail.

    python scripts/build_constraints.py protected [--lake lake-out] [--upload]
    python scripts/build_constraints.py flood eu|world SRC.zip OUT/
    python scripts/build_constraints.py roads [--lake lake-out] [--upload]
    python scripts/build_constraints.py meta

protected  Natura 2000 (EEA, the network as of end 2024, re-use with attribution) from the EEA's
           ArcGIS service `ProtectedSites/Natura2000Sites` layer 2 (every site once) and PAD-US 4.1
           Fee (USGS, public domain) from `PAD-US/PAD_US_4_1` layer 0, both paged as GeoJSON in
           EPSG:4326 with the services' own generalisation (maxAllowableOffset 0.0005 degrees,
           about 50 m): the 1.36 GB GeoPackage and the 1.01 GB GeoParquet are over the 1 GB
           download limit. Passed through: code, name, type, area as published (Natura 2000 km2,
           PAD-US acres), PAD-US designation, manager and GAP status. -> GeoJSONSeq for tippecanoe
           (`grid/protected.pmtiles`, the workflow cuts and uploads it), per-country counts and
           areas as published (frontend/public/data/eu/protected.json), lake `protected/*`.
flood      JRC river flood hazard maps, 100-year return period (CC BY 4.0): Europe at 100 m (EPSG:3035),
           the world at 30 arc-seconds. Water depth in metres as published; drawn in five depth
           classes (JRC's own: under 0.5, 0.5-1, 1-2, 2-4 and 4 m or more) as PNG tiles (Europe
           zoom 0-9, world 0-7) and a lookup grid for "Check a site": the deepest class of the
           source pixels in each cell (computed; Europe 0.01 degrees, world 0.05 degrees; uint8,
           0 = no flooding mapped or outside the map).
roads      Overture Maps transportation segments (OpenStreetMap, ODbL), the newest release:
           roads of class motorway, trunk and primary and standard-gauge railways in Europe and
           the US (bounding boxes below) -> GeoJSONSeq for tippecanoe (`grid/roads-rail.pmtiles`),
           lake `overture_transport/segments` (GeoParquet).
meta       frontend/public/data/eu/constraints.json: the tiles, classes and lookup layouts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections import defaultdict
from pathlib import Path

import wave5_common as w

TMP = Path("/tmp/wave6/constraints")
PUBLIC = "https://pub-73b8a23457984ffc93f888f77e1bebde.r2.dev/grid"
N2K = "https://bio.discomap.eea.europa.eu/arcgis/rest/services/ProtectedSites/Natura2000Sites/MapServer/2"
PADUS = "https://edits.nationalmap.gov/arcgis/rest/services/PAD-US/PAD_US_4_1/MapServer/0"
N2K_FIELDS = ["SITECODE", "SITENAME", "SITETYPE", "MS", "Area_km2", "RELEASE_DATE"]
PADUS_FIELDS = [
    "Unit_Nm",
    "Des_Tp",
    "Category",
    "Mang_Name",
    "Mang_Type",
    "State_Nm",
    "GIS_Acres",
    "GAP_Sts",
    "IUCN_Cat",
    "WDPA_Cd",
    "Pub_Access",
]
N2K_TYPE = {
    "A": "SPA (Birds Directive)",
    "B": "SCI/SAC (Habitats Directive)",
    "C": "SPA and SCI/SAC",
}
GAP = {"1": "GAP 1: managed for biodiversity, natural disturbance allowed", "2": "GAP 2: managed for biodiversity",
       "3": "GAP 3: multiple uses, some protection", "4": "GAP 4: no known mandate for protection"}  # fmt: skip

FLOOD = {
    "eu": {"zip": "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/FLOODS/EuropeanMaps/floodMap_RP100.zip",
           "zoom": 9, "cell": 0.01, "bounds": [-32.0, 26.0, 46.0, 72.0], "title": "Europe, 100 m"},
    "world": {"zip": "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/FLOODS/GlobalMaps/floodMapGL_rp100y.zip",
              "zoom": 7, "cell": 0.05, "bounds": [-180.0, -60.0, 180.0, 85.0], "title": "world, 30 arc-seconds"},
}  # fmt: skip
# JRC's depth classes (m): [from, to)
DEPTH = [[0.0, 0.5], [0.5, 1.0], [1.0, 2.0], [2.0, 4.0], [4.0, None]]
DEPTH_COLORS = [(170, 214, 240), (110, 176, 232), (60, 130, 210), (36, 84, 176), (22, 46, 120)]
OUTSIDE = 255  # the warp's no-data, read back as 0

ROAD_CLASSES = ["motorway", "trunk", "primary"]
BOXES = {
    "europe": (-25.0, 34.0, 45.0, 72.0),
    "us": (-125.0, 24.0, -66.0, 50.0),
    "alaska_hawaii": (-170.0, 18.0, -140.0, 72.0),
}


# ---------------------------------------------------------------- protected areas


def arcgis_pages(url: str, fields: list[str], page: int) -> list[dict]:
    """Every feature of an ArcGIS layer as GeoJSON in EPSG:4326, paged by OBJECTID."""
    import httpx

    n = w.get_json(f"{url}/query?where=1%3D1&returnCountOnly=true&f=json")["count"]  # type: ignore[index]
    out: list[dict] = []
    for offset in range(0, n, page):
        params = {"where": "1=1", "outFields": ",".join(fields), "returnGeometry": "true", "outSR": "4326",
                  "maxAllowableOffset": "0.0005", "geometryPrecision": "5", "orderByFields": "OBJECTID",
                  "resultOffset": str(offset), "resultRecordCount": str(page), "f": "geojson"}  # fmt: skip
        for attempt in range(1, 6):
            try:
                r = httpx.post(f"{url}/query", data=params, headers=w.UA, timeout=300)
                r.raise_for_status()
                out += r.json()["features"]
                break
            except (httpx.HTTPError, ValueError, KeyError) as e:
                print(
                    f"  {offset}: {type(e).__name__} {str(e)[:120]} (try {attempt}/5)", flush=True
                )
                time.sleep(15 * attempt)
        else:
            raise SystemExit(f"{url}: page at {offset} failed")
        if offset // page % 20 == 0:
            print(f"  {url.split('/')[-3]}: {len(out):,} of {n:,}", flush=True)
    return out


def n2k_props(p: dict) -> dict:
    return {"src": "n2k", "id": p.get("SITECODE"), "name": p.get("SITENAME"), "kind": N2K_TYPE.get(p.get("SITETYPE") or "", p.get("SITETYPE")),
            "iso2": p.get("MS"), "km2": p.get("Area_km2")}  # fmt: skip


def padus_props(p: dict) -> dict:
    acres = p.get("GIS_Acres")
    return {"src": "padus", "name": p.get("Unit_Nm"), "kind": p.get("Des_Tp"), "manager": p.get("Mang_Name"),
            "state": p.get("State_Nm"), "gap": str(p.get("GAP_Sts") or ""), "acres": round(acres, 1) if isinstance(acres, int | float) else None}  # fmt: skip


def build_protected(args: argparse.Namespace) -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    seq = TMP / "protected.geojsons"
    summary: dict[str, dict] = {
        "natura2000": defaultdict(lambda: [0, 0.0]),
        "padus": defaultdict(lambda: [0, 0.0]),
    }
    lake_rows: dict[str, list] = {"natura2000": [], "padus": []}
    with seq.open("w", encoding="utf-8") as f:
        for src, url, fields, props in (
            ("natura2000", N2K, N2K_FIELDS, n2k_props),
            ("padus", PADUS, PADUS_FIELDS, padus_props),
        ):
            feats = arcgis_pages(url, fields, 500 if src == "natura2000" else 250)
            for ft in feats:
                if not ft.get("geometry"):
                    continue
                p = props(ft.get("properties") or {})
                key = p.get("iso2") if src == "natura2000" else p.get("state")
                summary[src][key][0] += 1
                summary[src][key][1] += (
                    (p.get("km2") or 0) if src == "natura2000" else (p.get("acres") or 0)
                )
                tags = {k: v for k, v in p.items() if v not in (None, "")}
                f.write(
                    json.dumps(
                        {"type": "Feature", "properties": tags, "geometry": ft["geometry"]},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                lake_rows[src].append(
                    {**(ft.get("properties") or {}), "geometry": json.dumps(ft["geometry"])}
                )
            print(f"  {src}: {len(feats):,} areas", flush=True)
    w.write_json(w.EU / "protected.json", {
        "fetched": w.now(),
        "tiles": f"pmtiles://{PUBLIC}/protected.pmtiles",
        "natura2000": {"source": "Natura 2000, end 2024 (EEA), via the EEA's ProtectedSites/Natura2000Sites service",
                       "by_country": {k: [v[0], round(v[1], 1)] for k, v in sorted(summary["natura2000"].items(), key=lambda kv: str(kv[0]))}, "unit": "km2"},
        "padus": {"source": "PAD-US 4.1 Fee (USGS GAP), via the USGS PAD_US_4_1 service",
                  "by_state": {k: [v[0], round(v[1])] for k, v in sorted(summary["padus"].items(), key=lambda kv: str(kv[0]))}, "unit": "acres"},
        "gap": GAP,
    })  # fmt: skip
    import duckdb
    import lake

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    lake.iso_codes(con)
    lk = w.lake_for("protected", args.lake, "EEA Natura 2000 (end 2024); USGS PAD-US 4.1 Fee", "EEA re-use with attribution; PAD-US public domain",
                    "scripts/build_constraints.py", "Natura 2000 end 2024; PAD-US 4.1")  # fmt: skip
    for src, rows in lake_rows.items():
        tmp = TMP / f"{src}.json"
        tmp.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        iso = "t.MS AS iso2, i.iso3" if src == "natura2000" else "'US' AS iso2, 'USA' AS iso3"
        join = "LEFT JOIN iso_codes i ON i.iso2 = t.MS" if src == "natura2000" else ""
        admin = "NULL::VARCHAR" if src == "natura2000" else "t.State_Nm"
        lk.write(
            con, src,
            f"""SELECT t.* EXCLUDE (geometry), {iso}, {admin} AS admin1, ST_GeomFromGeoJSON(t.geometry) AS geometry
                FROM read_json('{tmp}', sample_size = -1, maximum_object_size = 1000000000) t {join}""",
            sort=["iso3", "ST_Hilbert(geometry, ST_Extent(ST_MakeEnvelope(-180, -90, 180, 90)))"], geometry="geometry",
        )  # fmt: skip
    w.lake_done(lk, args.upload)


# ---------------------------------------------------------------- flood hazard


def run(*cmd: str) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def depth_class(v: float) -> int:
    """1..5 for JRC's depth classes, 0 for no flooding (depth 0 or below)."""
    if not v > 0:
        return 0
    for i, (lo, hi) in enumerate(DEPTH):
        if hi is None or (lo <= v < hi):
            return i + 1
    return len(DEPTH)


def flood(which: str, src_zip: Path, out: Path) -> None:
    import numpy as np

    cfg = FLOOD[which]
    out.mkdir(parents=True, exist_ok=True)
    folder = w.unzip(src_zip)
    tifs = sorted(p for p in folder.rglob("*") if p.suffix.lower() in (".tif", ".tiff"))
    print(f"  {which}: {[(t.name, round(t.stat().st_size / 1e6)) for t in tifs]}", flush=True)
    if not tifs:
        raise SystemExit("no GeoTIFF in the zip")
    vrt = out / f"{which}.vrt"
    run("gdalbuildvrt", "-overwrite", str(vrt), *map(str, tifs))
    # classes as bytes (1..5, 0 = no flooding), in the source's projection
    cls = out / f"{which}_classes.tif"
    expr = "(A>0)*(1+(A>=0.5)+(A>=1)+(A>=2)+(A>=4))"
    run("gdal_calc.py", "-A", str(vrt), "--calc", expr, "--type", "Byte", "--NoDataValue", "0", "--overwrite",
        "--co", "TILED=YES", "--co", "COMPRESS=ZSTD", "--co", "BIGTIFF=YES", "--outfile", str(cls))  # fmt: skip
    # lookup grid: the deepest class in each cell (max), EPSG:4326
    w0, s0, e0, n0 = cfg["bounds"]
    cell = cfg["cell"]
    raw = out / f"{which}_lookup.envi"
    run("gdalwarp", "-overwrite", "-t_srs", "EPSG:4326", "-r", "max", "-te", str(w0), str(s0), str(e0), str(n0),
        "-tr", str(cell), str(cell), "-srcnodata", "0", "-dstnodata", str(OUTSIDE), "-ot", "Byte", "-of", "ENVI",
        "-multi", "-wo", "NUM_THREADS=ALL_CPUS", str(cls), str(raw))  # fmt: skip
    width, height = round((e0 - w0) / cell), round((n0 - s0) / cell)
    a = np.fromfile(raw, dtype="u1").reshape(height, width)
    # no flooding mapped and outside the map both read 0 (the source marks neither)
    a = np.where(a == OUTSIDE, 0, a).astype("u1")
    grid = out / f"flood-{which}-{cell}deg.u8"
    a.tofile(grid)
    print(
        f"  {which}: lookup {grid.name} {grid.stat().st_size / 1e6:.1f} MB, flooded cells {int((a > 0).sum()):,}",
        flush=True,
    )
    # tiles: Web Mercator at the zoom, coloured by class, PNG MBTiles -> PMTiles (the workflow converts)
    z = cfg["zoom"]
    world = 20037508.342789244
    res = 2 * world / (256 * 2**z)
    merc = out / f"{which}_3857.tif"
    run("gdalwarp", "-overwrite", "-t_srs", "EPSG:3857", "-r", "max", "-tr", str(res), str(res), "-tap",
        "-srcnodata", "0", "-dstnodata", "0", "-ot", "Byte", "-multi", "-wo", "NUM_THREADS=ALL_CPUS",
        "-co", "TILED=YES", "-co", "COMPRESS=ZSTD", "-co", "BIGTIFF=YES", str(cls), str(merc))  # fmt: skip
    colors = out / "colors.txt"
    colors.write_text(
        "0 0 0 0 0\n"
        + "".join(f"{i + 1} {c[0]} {c[1]} {c[2]} 255\n" for i, c in enumerate(DEPTH_COLORS)),
        encoding="utf-8",
    )
    rgba = out / f"{which}_rgba.tif"
    run("gdaldem", "color-relief", "-alpha", "-nearest_color_entry", "-co", "TILED=YES", "-co", "COMPRESS=ZSTD", "-co", "BIGTIFF=YES",
        str(merc), str(colors), str(rgba))  # fmt: skip
    mb = out / f"flood-{which}.mbtiles"
    mb.unlink(missing_ok=True)
    run("gdal_translate", "-of", "MBTILES", "-co", "TILE_FORMAT=PNG", "-co", "ZOOM_LEVEL_STRATEGY=LOWER",
        "-co", f"NAME=JRC river flood hazard, 100-year return period ({cfg['title']})", str(rgba), str(mb))  # fmt: skip
    run("gdaladdo", "-r", "nearest", str(mb), *[str(2**k) for k in range(1, z + 1)])
    print(f"  {which}: {mb.name} {mb.stat().st_size / 1e6:.1f} MB", flush=True)


# ---------------------------------------------------------------- major roads and rail


def build_roads(args: argparse.Namespace) -> None:
    import duckdb
    from fetch_world_hv_overture import newest_release

    rel = newest_release()
    con = duckdb.connect()
    con.execute(
        "INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2'"
    )
    path = f"s3://overturemaps-us-west-2/release/{rel}/theme=transportation/type=segment/*"
    TMP.mkdir(parents=True, exist_ok=True)
    parts = []
    for name, (x0, y0, x1, y1) in BOXES.items():
        t = time.time()
        out = TMP / f"roads_{name}.parquet"
        con.execute(
            f"""COPY (
                  SELECT id, subtype, class, names.primary AS name, ST_GeomFromWKB(geometry) AS geometry
                  FROM read_parquet('{path}', hive_partitioning = 1)
                  WHERE bbox.xmin < {x1} AND bbox.xmax > {x0} AND bbox.ymin < {y1} AND bbox.ymax > {y0}
                    AND ((subtype = 'road' AND class IN ({", ".join(f"'{c}'" for c in ROAD_CLASSES)}))
                         OR (subtype = 'rail' AND class = 'standard_gauge'))
                ) TO '{out}' (FORMAT PARQUET)"""
        )
        n = con.execute(
            f"SELECT subtype, class, count(*) FROM '{out}' GROUP BY ALL ORDER BY 1, 2"
        ).fetchall()
        print(f"  {name}: {n} in {time.time() - t:.0f} s", flush=True)
        parts.append(str(out))
    seq = TMP / "roads.geojsons"
    rows = con.execute(
        f"SELECT subtype, class, name, ST_AsGeoJSON(ST_Simplify(geometry, 0.0002)) FROM read_parquet({parts})"
    ).fetchall()
    with seq.open("w", encoding="utf-8") as f:
        for sub, cls, name, gj in rows:
            minz = 5 if cls in ("motorway", "standard_gauge") else 6 if cls == "trunk" else 7
            props = {"class": cls, **({"name": name} if name else {})}
            f.write(json.dumps({"type": "Feature", "tippecanoe": {"minzoom": minz, "layer": "rail" if sub == "rail" else "roads"},
                                "properties": props, "geometry": json.loads(gj)}, ensure_ascii=False) + "\n")  # fmt: skip
    print(f"  {len(rows):,} segments -> {seq}", flush=True)
    import lake

    lake.iso_codes(con)
    lk = w.lake_for("overture_transport", args.lake, f"Overture Maps transportation, release {rel}", "ODbL (OpenStreetMap)",
                    "scripts/build_constraints.py", rel)  # fmt: skip
    lk.write(
        con, "segments",
        f"""SELECT id, subtype, class, name, NULL::VARCHAR AS iso2, NULL::VARCHAR AS iso3, NULL::VARCHAR AS admin1, geometry
            FROM read_parquet({parts})""",
        sort=["subtype", "class", "ST_Hilbert(geometry, ST_Extent(ST_MakeEnvelope(-180, -90, 180, 90)))"],
        partition={"release": rel}, geometry="geometry",
    )  # fmt: skip
    w.lake_done(lk, args.upload)


# ---------------------------------------------------------------- the app's description


def meta() -> None:
    lows = [None if i == 0 else d[0] for i, d in enumerate(DEPTH)]
    payload = {
        "fetched": w.now(),
        "flood": {
            "title": "River flood hazard, 100-year return period: water depth",
            "source": "JRC river flood hazard maps (European and global), CC BY 4.0",
            "classes": [[lo, d[1], list(c)] for lo, d, c in zip(lows, DEPTH, DEPTH_COLORS, strict=True)],
            "maps": {
                k: {"title": v["title"], "tiles": f"pmtiles://{PUBLIC}/flood-{k}.pmtiles", "max_zoom": v["zoom"],
                    "lookup": {"url": f"{PUBLIC}/flood-{k}-{v['cell']}deg.u8", "cell_deg": v["cell"], "origin": [v["bounds"][0], v["bounds"][3]],
                               "width": round((v["bounds"][2] - v["bounds"][0]) / v["cell"]), "height": round((v["bounds"][3] - v["bounds"][1]) / v["cell"]),
                               "computed": f"the deepest class of the source pixels in each {v['cell']} degree cell"}}
                for k, v in FLOOD.items()
            },
        },
        "roads": {"tiles": f"pmtiles://{PUBLIC}/roads-rail.pmtiles", "source": "Overture Maps transportation (OpenStreetMap, ODbL)",
                  "classes": ROAD_CLASSES, "rail": "standard_gauge", "coverage": "Europe and the United States"},
    }  # fmt: skip
    w.write_json(w.EU / "constraints.json", payload)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["protected", "flood", "roads", "meta"])
    ap.add_argument("which", nargs="?", choices=list(FLOOD))
    ap.add_argument("src", nargs="?", type=Path)
    ap.add_argument("out", nargs="?", type=Path)
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    if args.what == "protected":
        build_protected(args)
    elif args.what == "flood":
        flood(args.which, args.src, args.out)
    elif args.what == "roads":
        build_roads(args)
    else:
        meta()


if __name__ == "__main__":
    main()
