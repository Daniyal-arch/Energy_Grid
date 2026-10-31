"""Rasters for area_stats (docs/tasks/27, B2) -> R2 `lake/rasters/` (COG, private), read by range.

    python scripts/build_rasters.py ghsl pop|built [--upload]
    python scripts/build_rasters.py shares worldcover|slope --band N/M [--upload]
    python scripts/build_rasters.py mosaic worldcover|slope [--upload]

ghsl    GHSL R2023A, epoch 2025 (CC BY 4.0, JRC): the 3 arc-second tiles (10 x 10 degrees, about
        150 MB zipped each) that cover the EU-27, the UK and the US become one COG each,
        `lake/rasters/ghsl_<var>_e2025_3ss/R<row>_C<col>.tif` (values as published, Float64,
        ZSTD); the 30 arc-second world file becomes `lake/rasters/ghsl_<var>_e2025_30ss.tif`.
        One tile at a time on disk. Run in GitHub Actions (about 18 GB downloaded per variable).
shares  1 km class shares from the 10 m WorldCover 2021 v200 tiles (AWS open data, read in
        place) or from slope computed on Copernicus DEM GLO-30 tiles: for every 30 arc-second
        cell the share of the fine cells in each class (computed), one band per class, for the
        29 places. `--band N/M` splits the longitudes into M jobs.
mosaic  the band pieces into `lake/rasters/<name>_1km_shares.tif`.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import httpx
import wave5_common as w

TMP = Path("/tmp/wave8/rasters")
GHSL = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL"
PRODUCTS = {
    "pop": ("GHS_POP_GLOBE_R2023A", "GHS_POP_E2025_GLOBE_R2023A_4326"),
    "built": ("GHS_BUILT_S_GLOBE_R2023A", "GHS_BUILT_S_E2025_GLOBE_R2023A_4326"),
}
# the boxes the 29 places lie in [west, south, east, north]: Europe (Azores to Cyprus, Canaries
# to the North Cape), the contiguous US, Alaska (both sides of 180°), Hawaii, Puerto Rico
BOXES = [
    (-32.0, 27.0, 35.0, 72.0),
    (-125.0, 24.0, -66.0, 50.0),
    (-180.0, 51.0, -129.0, 72.0),
    (172.0, 51.0, 180.0, 54.0),
    (-161.0, 18.5, -154.0, 22.5),
    (-68.0, 17.5, -64.5, 18.6),
]
# the GHSL 4326 tile grid: column 1 starts at -180.0079°, row 1 at 89.0996° (from tile R4_C20)
X0, Y0, STEP = -180.00792, 89.09958, 10.0
BUCKET = "infraatlas-raw"


def run(*cmd: str) -> None:
    subprocess.run(cmd, check=True)


def s3(*args: str) -> None:
    run(
        "aws", "s3", "cp", "--only-show-errors",
        "--endpoint-url", f"https://{w.env('CLOUDFLARE_ACCOUNT_ID')}.r2.cloudflarestorage.com", *args,
    )  # fmt: skip


def cog(src: Path, dst: Path, predictor: str = "YES") -> None:
    run(
        "gdal_translate", "-of", "COG", "-co", "COMPRESS=ZSTD", "-co", f"PREDICTOR={predictor}",
        "-co", "BIGTIFF=YES", "-co", "NUM_THREADS=ALL_CPUS", "-co", "OVERVIEWS=NONE", str(src), str(dst),
    )  # fmt: skip


def tiles_needed() -> list[tuple[int, int]]:
    out = set()
    for x0, y0, x1, y1 in BOXES:
        for c in range(1, 37):
            left = X0 + (c - 1) * STEP
            if left + STEP <= x0 or left >= x1:
                continue
            for r in range(1, 19):
                top = Y0 - (r - 1) * STEP
                if top <= y0 or top - STEP >= y1:
                    continue
                out.add((r, c))
    return sorted(out)


def ghsl(args: argparse.Namespace) -> None:
    folder, stem = PRODUCTS[args.var]
    base = f"{GHSL}/{folder}/{stem}_3ss/V1-0/tiles/"
    listing = httpx.get(base, timeout=120).text
    published = set(re.findall(r"_R(\d+)_C(\d+)\.zip", listing))
    want = [(r, c) for r, c in tiles_needed() if (str(r), str(c)) in published]
    print(
        f"{args.var}: {len(want)} of {len(published)} published 3 arc-second tiles cover the 29 places",
        flush=True,
    )
    TMP.mkdir(parents=True, exist_ok=True)
    done, t0 = [], time.time()
    for i, (r, c) in enumerate(want, 1):
        name = f"{stem}_3ss_V1_0_R{r}_C{c}"
        z = w.download(f"{base}{name}.zip", TMP / f"{name}.zip")
        tif = next(w.unzip(z).rglob("*.tif"))
        out = TMP / f"R{r}_C{c}.tif"
        cog(tif, out)
        if args.upload:
            s3(str(out), f"s3://{BUCKET}/lake/rasters/ghsl_{args.var}_e2025_3ss/R{r}_C{c}.tif")
        done.append({"tile": f"R{r}_C{c}", "bytes": out.stat().st_size})
        shutil.rmtree(tif.parent, ignore_errors=True)
        z.unlink()
        if args.upload:
            out.unlink()
        print(
            f"  {i}/{len(want)} R{r}_C{c}: {done[-1]['bytes'] / 1e6:.0f} MB COG ({time.time() - t0:.0f} s)",
            flush=True,
        )
    world = f"{GHSL}/{folder}/{stem}_30ss/V1-0/{stem}_30ss_V1_0.zip"
    z = w.download(world, TMP / f"{stem}_30ss.zip")
    tif = next(w.unzip(z).rglob("*.tif"))
    out = TMP / f"ghsl_{args.var}_e2025_30ss.tif"
    cog(tif, out)
    if args.upload:
        s3(str(out), f"s3://{BUCKET}/lake/rasters/{out.name}")
    cat = {
        "updated": w.now(),
        "source": f"{folder} {stem} (JRC, CC BY 4.0)",
        "tiles_3ss": done,
        "grid": {"origin": [X0, Y0], "step_deg": STEP, "name": "R<row>_C<col>"},
        "world_30ss": {"file": out.name, "bytes": out.stat().st_size},
    }
    p = TMP / f"ghsl_{args.var}_catalog.json"
    p.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    if args.upload:
        s3(str(p), f"s3://{BUCKET}/lake/rasters/ghsl_{args.var}_e2025_3ss/_catalog.json")
    print(
        f"{args.var}: {len(done)} tiles, {sum(d['bytes'] for d in done) / 1e9:.2f} GB; world {out.stat().st_size / 1e6:.0f} MB",
        flush=True,
    )


# ---------------------------------------------------------------------- 1 km class shares

CELL = 1 / 120  # 30 arc-seconds
SHARES = {
    "worldcover": {
        "classes": [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100],
        "tile_deg": 3,
        "url": "/vsis3/esa-worldcover/v200/2021/map/ESA_WorldCover_10m_2021_v200_{NS}{lat:02d}{EW}{lon:03d}_Map.tif",
    },
    "slope": {
        "classes": [1, 2, 3, 4, 5, 6],
        "breaks": [2, 5, 10, 15, 30],
        "tile_deg": 1,
        "url": "/vsis3/copernicus-dem-30m/Copernicus_DSM_COG_10_{NS}{lat:02d}_00_{EW}{lon:03d}_00_DEM/Copernicus_DSM_COG_10_{NS}{lat:02d}_00_{EW}{lon:03d}_00_DEM.tif",
    },
}


def shares(args: argparse.Namespace) -> None:
    """Per tile: classes of the fine cells -> share per 30 arc-second cell, written as one small
    GeoTIFF per tile with a band per class; the mosaic step joins them."""
    import numpy as np
    import rasterio
    from rasterio.windows import Window

    spec = SHARES[args.name]
    step = spec["tile_deg"]
    n, m = (int(x) for x in args.band.split("/"))
    os.environ.update(
        {
            "AWS_NO_SIGN_REQUEST": "YES",
            "AWS_REGION": "eu-central-1",
            "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        }
    )
    out_dir = TMP / f"{args.name}_pieces"
    out_dir.mkdir(parents=True, exist_ok=True)
    tiles = set()
    for x0, y0, x1, y1 in BOXES:
        for lat in range(math.floor(y0 / step) * step, math.ceil(y1), step):
            for lon in range(math.floor(x0 / step) * step, math.ceil(x1), step):
                tiles.add((lat, lon))
    lons = sorted({lon for _, lon in tiles})
    mine = {lon for i, lon in enumerate(lons) if i % m == n - 1}
    todo = sorted(t for t in tiles if t[1] in mine)
    print(f"{args.name} band {n}/{m}: {len(todo)} tiles", flush=True)
    t0, kept = time.time(), 0
    for k, (lat, lon) in enumerate(todo, 1):
        url = spec["url"].format(
            NS="N" if lat >= 0 else "S", lat=abs(lat), EW="E" if lon >= 0 else "W", lon=abs(lon)
        )
        try:
            src = rasterio.open(url)
        except rasterio.errors.RasterioIOError:
            continue  # sea: no tile published
        with src:
            h, wd = src.height, src.width
            cols, rows = round(step / CELL), round(step / CELL)
            fy, fx = h / rows, wd / cols  # fine cells per 30" cell
            counts = np.zeros((len(spec["classes"]), rows, cols), dtype="float32")
            total = np.zeros((rows, cols), dtype="float32")
            block = max(1, round(fy)) * 64
            for r0 in range(0, h, block):
                a = src.read(1, window=Window(0, r0, wd, min(block, h - r0)))
                if args.name == "slope":
                    lat_mid = src.transform.f + src.transform.e * (r0 + np.arange(a.shape[0]) + 0.5)
                    dy = abs(src.transform.e) * 111_320.0
                    dx = abs(src.transform.a) * 111_320.0 * np.cos(np.radians(lat_mid))[:, None]
                    gy, gx = np.gradient(a.astype("float64"))
                    a = (
                        np.digitize(
                            np.degrees(np.arctan(np.hypot(gx / dx, gy / dy))), spec["breaks"]
                        )
                        + 1
                    )
                ri = ((r0 + np.arange(a.shape[0])) / fy).astype(int).clip(0, rows - 1)
                ci = (np.arange(wd) / fx).astype(int).clip(0, cols - 1)
                idx = (ri[:, None] * cols + ci[None, :]).ravel()
                flat = a.ravel()
                for b, cls in enumerate(spec["classes"]):
                    counts[b] += np.bincount(idx[flat == cls], minlength=rows * cols).reshape(
                        rows, cols
                    )
                total += np.bincount(idx[flat > 0], minlength=rows * cols).reshape(rows, cols)
            with np.errstate(invalid="ignore", divide="ignore"):
                share = np.where(total > 0, counts / total, np.nan).astype("float32")
            west, north = src.bounds.left, src.bounds.top
        prof = {
            "driver": "GTiff", "width": cols, "height": rows, "count": len(spec["classes"]), "dtype": "float32",
            "crs": "EPSG:4326", "transform": rasterio.transform.from_origin(west, north, CELL, CELL),
            "nodata": float("nan"), "compress": "zstd",
        }  # fmt: skip
        with rasterio.open(out_dir / f"{lat}_{lon}.tif", "w", **prof) as dst:
            dst.write(share)
        kept += 1
        if k % 20 == 0:
            print(f"  {k}/{len(todo)} tiles, {kept} kept, {time.time() - t0:.0f} s", flush=True)
    print(f"{args.name} band {n}/{m}: {kept} tiles in {time.time() - t0:.0f} s", flush=True)


def mosaic(args: argparse.Namespace) -> None:
    pieces = sorted((TMP / f"{args.name}_pieces").rglob("*.tif"))
    vrt = TMP / f"{args.name}.vrt"
    run("gdalbuildvrt", "-overwrite", str(vrt), *map(str, pieces))
    out = TMP / f"{args.name}_1km_shares.tif"
    cog(vrt, out, predictor="3")
    print(f"{out.name}: {len(pieces)} pieces, {out.stat().st_size / 1e6:.0f} MB", flush=True)
    if args.upload:
        s3(str(out), f"s3://{BUCKET}/lake/rasters/{out.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("ghsl")
    g.add_argument("var", choices=list(PRODUCTS))
    s = sub.add_parser("shares")
    s.add_argument("name", choices=list(SHARES))
    s.add_argument("--band", default="1/1")
    mo = sub.add_parser("mosaic")
    mo.add_argument("name", choices=list(SHARES))
    for p in (g, s, mo):
        p.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    {"ghsl": ghsl, "shares": shares, "mosaic": mosaic}[args.cmd](args)


if __name__ == "__main__":
    main()
