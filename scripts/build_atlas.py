"""Solar and wind resource atlases: map tiles, a lookup grid for "Check a site", COGs in the lake.

Runs in GitHub Actions only (.github/workflows/atlas.yml; the owner approved the downloads,
docs/tasks/16-wrap-up.md part E). scripts/probe_atlas.py found the files (2026-10-18):

  Global Solar Atlas (World Bank / Solargis, CC BY 4.0): PVOUT, long-term average of daily
    totals of PV output in kWh/kWp, EPSG:4326 GeoTIFF in a 362 MB zip (version of 2026-04).
    The atlas's own map gives yearly totals as daily x 365 (730 = 2.0 x 365).
  Global Wind Atlas 3 (DTU, CC BY 4.0): mean wind speed at 100 m, m/s, a 14.07 GB float32
    Cloud-Optimized GeoTIFF at 0.0025 degrees (~250 m), 80 N to 64 S, no data = NaN.

Steps per variable (GDAL command line tools):
  tiles   warp to Web Mercator at zoom 7 (average of the source pixels in each tile pixel),
          colour by the source's own classes (solar: the atlas legend's 0.2 kWh/kWp steps from
          2.0 to 6.4; wind: 1 m/s steps over the atlas's 0-10 m/s scale), PNG tiles zoom 0-7
          as MBTiles (lower zooms by nearest, so classes stay classes); then pmtiles-convert.
  lookup  the mean of the source pixels in each 0.1 degree cell (computed), as a row-major
          int16 grid from 90 N / 180 W (3600 x 1800 cells; solar kWh/kWp per day x 1000,
          wind m/s x 100; -32768 = no data): the app reads one cell with an HTTP range request.
  cog     the full raster as a Cloud-Optimized GeoTIFF for the lake (the wind file already is
          one and goes as downloaded).

    python scripts/build_atlas.py tiles pvout PVOUT.tif out/
    python scripts/build_atlas.py lookup wind wind.tif out/
    python scripts/build_atlas.py meta          (frontend/public/data/eu/atlas.json)
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path

VARS: dict[str, dict] = {
    "pvout": {
        "title": "Photovoltaic power potential (PVOUT), long-term average of daily totals",
        "unit": "kWh/kWp per day",
        "source": "Global Solar Atlas 2.13 (World Bank, Solargis), CC BY 4.0",
        # the atlas legend: 2.0 .. 6.4 kWh/kWp per day in 0.2 steps
        "breaks": [round(2.0 + 0.2 * i, 1) for i in range(23)],
        "colors": [
            (64, 58, 96),
            (128, 104, 128),
            (196, 150, 104),
            (240, 196, 112),
            (252, 232, 176),
        ],
        "scale": 1000,
    },
    "wind": {
        "title": "Mean wind speed at 100 m",
        "unit": "m/s",
        "source": "Global Wind Atlas 3 (DTU), CC BY 4.0",
        # the atlas draws 0 .. 10 m/s; classes of 1 m/s, the last open (10 and more)
        "breaks": [float(v) for v in range(1, 11)],
        "colors": [(36, 52, 78), (44, 92, 120), (64, 148, 164), (128, 206, 206), (224, 246, 240)],
        "scale": 100,
    },
}
WORLD = 20037508.342789244
Z = 7
RES = 2 * WORLD / (256 * 2**Z)  # metres per pixel at zoom 7
CELL = 0.1
NODATA = -32768


def run(*cmd: str) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def class_colors(var: str) -> list[tuple[int, int, int]]:
    """One colour per class (breaks + 1), spread along the palette's stops."""
    v = VARS[var]
    n = len(v["breaks"]) + 1
    stops = v["colors"]
    out = []
    for i in range(n):
        t = i / (n - 1) * (len(stops) - 1)
        a, b = stops[int(math.floor(t))], stops[min(len(stops) - 1, int(math.floor(t)) + 1)]
        f = t - math.floor(t)
        out.append(tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3)))
    return out


def color_file(var: str, path: Path) -> list[list]:
    """gdaldem colour table with steps: each class one flat colour (two entries per break)."""
    v = VARS[var]
    cols = class_colors(var)
    lines = ["nv 0 0 0 0", f"-100000 {' '.join(map(str, cols[0]))} 255"]
    for i, b in enumerate(v["breaks"]):
        lines.append(f"{b - 1e-6:.6f} {' '.join(map(str, cols[i]))} 255")
        lines.append(f"{b:.6f} {' '.join(map(str, cols[i + 1]))} 255")
    lines.append(f"100000 {' '.join(map(str, cols[-1]))} 255")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    lows = [None, *v["breaks"]]
    highs = [*v["breaks"], None]
    return [[lo, hi, list(c)] for lo, hi, c in zip(lows, highs, cols, strict=True)]


def tiles(var: str, src: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    merc = out / f"{var}_3857.tif"
    # the data's latitudes, snapped to whole zoom-7 tiles (Mercator stops at 85.05 degrees)
    north, south = 81.0, -66.0

    def y(lat: float) -> float:
        return WORLD / math.pi * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

    tile = 256 * RES
    top = math.ceil(y(north) / tile) * tile
    bottom = math.floor(y(south) / tile) * tile
    run(
        "gdalwarp", "-overwrite", "-t_srs", "EPSG:3857", "-r", "average",
        "-te", str(-WORLD), str(bottom), str(WORLD), str(top), "-tr", str(RES), str(RES),
        "-dstnodata", "nan", "-ot", "Float32", "-multi", "-wo", "NUM_THREADS=ALL_CPUS",
        "-co", "TILED=YES", "-co", "COMPRESS=ZSTD", "-co", "BIGTIFF=YES", str(src), str(merc),
    )  # fmt: skip
    classes = color_file(var, out / f"{var}_colors.txt")
    rgba = out / f"{var}_rgba.tif"
    run(
        "gdaldem", "color-relief", "-alpha", "-co", "TILED=YES", "-co", "COMPRESS=ZSTD",
        "-co", "BIGTIFF=YES", str(merc), str(out / f"{var}_colors.txt"), str(rgba),
    )  # fmt: skip
    mb = out / f"{var}.mbtiles"
    mb.unlink(missing_ok=True)
    run(
        "gdal_translate", "-of", "MBTILES", "-co", "TILE_FORMAT=PNG", "-co", "ZOOM_LEVEL_STRATEGY=LOWER",
        "-co", f"NAME={VARS[var]['title']}", str(rgba), str(mb),
    )  # fmt: skip
    run("gdaladdo", "-r", "nearest", str(mb), *[str(2**k) for k in range(1, Z + 1)])
    meta = {**{k: VARS[var][k] for k in ("title", "unit", "source")}, "classes": classes}
    (out / f"{var}_classes.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"{var}: {mb} {mb.stat().st_size / 1e6:.1f} MB", flush=True)


def lookup(var: str, src: Path, out: Path) -> None:
    import numpy as np

    out.mkdir(parents=True, exist_ok=True)
    raw = out / f"{var}_lookup.envi"
    run(
        "gdalwarp", "-overwrite", "-t_srs", "EPSG:4326", "-r", "average",
        "-te", "-180", "-90", "180", "90", "-tr", str(CELL), str(CELL),
        "-dstnodata", "nan", "-ot", "Float32", "-of", "ENVI", "-multi",
        "-wo", "NUM_THREADS=ALL_CPUS", str(src), str(raw),
    )  # fmt: skip
    w, h = round(360 / CELL), round(180 / CELL)
    a = np.fromfile(raw, dtype="<f4").reshape(h, w)
    scaled = np.where(np.isfinite(a), np.round(a * VARS[var]["scale"]), NODATA)
    grid = out / f"{var}_0.1deg.i16"
    scaled.astype("<i2").tofile(grid)
    meta = {
        **{k: VARS[var][k] for k in ("title", "unit", "source", "scale")},
        "cell_deg": CELL,
        "width": w,
        "height": h,
        "origin": [-180, 90],
        "nodata": NODATA,
        "dtype": "int16 little-endian, row-major from the north-west corner",
        "computed": f"mean of the source pixels in each {CELL} degree cell",
        "cells_with_data": int(np.isfinite(a).sum()),
    }
    (out / f"{var}_lookup.json").write_text(json.dumps(meta), encoding="utf-8")
    print(
        f"{var}: {grid} {grid.stat().st_size / 1e6:.1f} MB, {meta['cells_with_data']:,} cells",
        flush=True,
    )


def cog(src: Path, dst: Path) -> None:
    run(
        "gdal_translate", "-of", "COG", "-co", "COMPRESS=ZSTD", "-co", "PREDICTOR=YES",
        "-co", "BIGTIFF=YES", "-co", "NUM_THREADS=ALL_CPUS", str(src), str(dst),
    )  # fmt: skip


PUBLIC = "https://pub-73b8a23457984ffc93f888f77e1bebde.r2.dev/grid"
FILES = {"pvout": "atlas-pvout", "wind": "atlas-wind100"}


def meta(out: Path) -> None:
    """frontend/public/data/eu/atlas.json: what the app needs to draw and read both atlases
    (classes and colours, the tiles, the lookup grid's layout); no GDAL needed."""
    tmp = Path("/tmp/atlas-meta")
    tmp.mkdir(parents=True, exist_ok=True)
    payload = {
        var: {
            **{k: v[k] for k in ("title", "unit", "source", "scale")},
            "classes": color_file(var, tmp / f"{var}.txt"),
            "tiles": f"pmtiles://{PUBLIC}/{FILES[var]}.pmtiles",
            "max_zoom": Z,
            "lookup": {
                "url": f"{PUBLIC}/{FILES[var]}-0.1deg.i16",
                "cell_deg": CELL,
                "width": round(360 / CELL),
                "height": round(180 / CELL),
                "origin": [-180, 90],
                "nodata": NODATA,
                "computed": f"mean of the source pixels in each {CELL} degree cell",
            },
        }
        for var, v in VARS.items()
    }
    out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["tiles", "lookup", "cog", "meta"])
    ap.add_argument("var", nargs="?", choices=list(VARS), default=None)
    ap.add_argument("src", nargs="?", type=Path)
    ap.add_argument("out", nargs="?", type=Path)
    args = ap.parse_args()
    if args.step == "meta":
        meta(Path("frontend/public/data/eu/atlas.json"))
    elif args.step == "tiles":
        tiles(args.var, args.src, args.out)
    elif args.step == "lookup":
        lookup(args.var, args.src, args.out)
    else:
        cog(args.src, args.out)


if __name__ == "__main__":
    main()
