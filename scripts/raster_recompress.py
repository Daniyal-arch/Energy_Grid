"""Brief 32 Step 5: lossless recompression of the largest rasters, and the lossy options measured
for the owner (never applied here).

    python scripts/raster_recompress.py test [--keys KEY ...] [--out data/raster_recompress.json]
    python scripts/raster_recompress.py apply --keys KEY ...      # only bit-identical, smaller files

`test`, per raster (a key under r2://infraatlas-raw/):

- its current compression, data type, size;
- lossless candidates written with GDAL as cloud-optimised GeoTIFFs: ZSTD level 22 with the
  predictor for its type (2 integers, 3 floats), and LERC with a maximum error of 0 plus ZSTD;
  each candidate's size and whether its decoded values are bit-identical to the original (a
  SHA-256 over every block of every band, NaN and nodata included);
- lossy options, on the whole raster for the size and on the decoded values for the change:
  wind speeds as int16 in 0.01 m/s steps, float64 population as float32: the saving, the
  largest change of any cell and the change of the sum over a few areas (windows).

`apply` writes the best bit-identical candidate over the original key, only when it saves 10 %
or more, after checking the uploaded copy's hash once more. Lossy options are written to
docs/owner-questions.md by hand, never applied. Runs in Actions (job `rasters` of
`lake-catalog.yml`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.windows import Window

BUCKET = "infraatlas-raw"
# smallest first, so results arrive before the 14 GB wind raster (run it on its own: --keys)
DEFAULT_KEYS = [
    "lake/rasters/ghsl_pop_e2025_3ss/R6_C10.tif",
    "lake/rasters/ghsl_pop_e2025_30ss.tif",
    "lake/rasters/slope_1km_shares.tif",
    "lake/rasters/worldcover_1km_shares.tif",
]
# ZSTD 22 on one thread did not finish the 14 GB wind raster in 5 hours; 15 on every core
ZSTD_LEVEL = 15
WORK = Path("/tmp/rasters")


def aws(*args: str) -> None:
    acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    subprocess.run(
        ["aws", *args, "--endpoint-url", f"https://{acct}.r2.cloudflarestorage.com"], check=True
    )


def values_hash(path: Path) -> str:
    """SHA-256 of every band's decoded values, block by block (NaN bit patterns included)."""
    h = hashlib.sha256()
    with rasterio.open(path) as r:
        for b in range(1, r.count + 1):
            for _, w in r.block_windows(b):
                h.update(np.ascontiguousarray(r.read(b, window=w)).tobytes())
    return h.hexdigest()


def info(path: Path) -> dict[str, Any]:
    with rasterio.open(path) as r:
        return {"dtype": r.dtypes[0], "bands": r.count, "size": [r.width, r.height],
                "compress": (r.compression.value if r.compression else None), "nodata": r.nodata,
                "predictor": r.tags(ns="IMAGE_STRUCTURE").get("PREDICTOR")}  # fmt: skip


def translate(src: Path, dst: Path, opts: list[str]) -> float:
    t0 = time.time()
    subprocess.run(["gdal_translate", "-q", "-of", "COG", *sum((["-co", o] for o in opts), []), str(src), str(dst)],
                   check=True)  # fmt: skip
    return time.time() - t0


def lossy(src: Path, kind: str) -> dict[str, Any]:
    """The change a lossy option would make, on every cell (block by block) and on the sums of
    four windows (quarters of the raster's middle), and the file size it would have."""
    out = WORK / f"lossy_{kind}.tif"
    if kind == "wind_int16":
        subprocess.run(["gdal_translate", "-q", "-of", "COG", "-ot", "Int16", "-scale", "0", "327.67", "0", "32767",
                        "-a_scale", "0.01", "-co", "COMPRESS=ZSTD", "-co", "PREDICTOR=2", "-co", f"LEVEL={ZSTD_LEVEL}", "-co", "NUM_THREADS=ALL_CPUS",
                        str(src), str(out)], check=True)  # fmt: skip
    else:
        subprocess.run(["gdal_translate", "-q", "-of", "COG", "-ot", "Float32", "-co", "COMPRESS=ZSTD",
                        "-co", "PREDICTOR=3", "-co", f"LEVEL={ZSTD_LEVEL}", "-co", "NUM_THREADS=ALL_CPUS", str(src), str(out)], check=True)  # fmt: skip
    worst = 0.0
    with rasterio.open(src) as a, rasterio.open(out) as b:
        scale = b.scales[0] if kind == "wind_int16" else 1.0
        for _, w in a.block_windows(1):
            x = a.read(1, window=w).astype("float64")
            y = b.read(1, window=w).astype("float64") * scale
            ok = np.isfinite(x) & np.isfinite(y)
            if a.nodata is not None:
                ok &= x != a.nodata
            if ok.any():
                worst = max(worst, float(np.max(np.abs(x[ok] - y[ok]))))
        sums = []
        W, H = a.width, a.height
        for i in range(4):
            win = Window(W // 4 + (i % 2) * W // 4, H // 4 + (i // 2) * H // 4, W // 4, H // 4)
            x = a.read(1, window=win).astype("float64")
            y = b.read(1, window=win).astype("float64") * scale
            ok = np.isfinite(x) & np.isfinite(y)
            if a.nodata is not None:
                ok &= x != a.nodata
            sx, sy = float(x[ok].sum()), float(y[ok].sum())
            sums.append(
                {
                    "window": i,
                    "sum": sx,
                    "change": sy - sx,
                    "relative": (sy - sx) / sx if sx else None,
                }
            )
    size = out.stat().st_size
    out.unlink()
    return {"option": kind, "bytes": size, "largest_cell_change": worst, "window_sums": sums}


def test(keys: list[str], out: Path) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    res = []
    for key in keys:
        src = WORK / Path(key).name
        t0 = time.time()
        aws("s3", "cp", "--only-show-errors", f"s3://{BUCKET}/{key}", str(src))
        rec: dict[str, Any] = {
            "key": key,
            "bytes": src.stat().st_size,
            **info(src),
            "download_s": round(time.time() - t0),
        }
        base = values_hash(src)
        is_float = rec["dtype"].startswith("float")
        cands = {
            "zstd22": [
                "COMPRESS=ZSTD",
                f"LEVEL={ZSTD_LEVEL}",
                f"PREDICTOR={3 if is_float else 2}",
                "NUM_THREADS=ALL_CPUS",
                "BIGTIFF=IF_SAFER",
            ],
            "lerc0_zstd": [
                "COMPRESS=LERC_ZSTD",
                "MAX_Z_ERROR=0",
                "NUM_THREADS=ALL_CPUS",
                "BIGTIFF=IF_SAFER",
            ],
        }
        rec["candidates"] = {}
        for name, opts in cands.items():
            dst = WORK / f"{name}_{Path(key).name}"
            try:
                secs = translate(src, dst, opts)
                same = values_hash(dst) == base
                rec["candidates"][name] = {"bytes": dst.stat().st_size, "identical": same, "seconds": round(secs),
                                           "saving": round(1 - dst.stat().st_size / rec["bytes"], 3)}  # fmt: skip
            except subprocess.CalledProcessError as e:
                rec["candidates"][name] = {"error": str(e)[:200]}
            dst.unlink(missing_ok=True)
        if "wind" in key and is_float:
            rec["lossy"] = [lossy(src, "wind_int16")]
        if "pop" in key and rec["dtype"] == "float64":
            rec["lossy"] = [lossy(src, "pop_float32")]
        src.unlink()
        res.append(rec)
        print(json.dumps(rec), flush=True)
        out.write_text(
            json.dumps(res, indent=1) + "\n", encoding="utf-8"
        )  # kept if a later key times out
    out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(
        "| raster | GB | type | now | zstd22 (identical) | lerc0 (identical) |\n|---|---:|---|---|---|---|"
    )
    for r in res:
        c = r["candidates"]

        def cell(k: str) -> str:
            v = c.get(k, {})
            return (
                f"{v['bytes'] / 1e9:.3f} GB, {v['saving']:+.1%} ({v['identical']})"
                if "bytes" in v
                else v.get("error", "")[:60]
            )

        print(
            f"| `{r['key']}` | {r['bytes'] / 1e9:.3f} | {r['dtype']} | {r['compress']} | {cell('zstd22')} | {cell('lerc0_zstd')} |"
        )
    for r in res:
        for lo in r.get("lossy", []):
            print(f"lossy {r['key']} {lo['option']}: {lo['bytes'] / 1e9:.3f} GB ({1 - lo['bytes'] / r['bytes']:.1%} saving), "
                  f"largest cell change {lo['largest_cell_change']:.6g}, window sums {[round(s['relative'] or 0, 9) for s in lo['window_sums']]}")  # fmt: skip


def apply(keys: list[str]) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    for key in keys:
        src = WORK / Path(key).name
        aws("s3", "cp", "--only-show-errors", f"s3://{BUCKET}/{key}", str(src))
        base = values_hash(src)
        is_float = info(src)["dtype"].startswith("float")
        best = None
        for name, opts in {
            "zstd22": [
                "COMPRESS=ZSTD",
                f"LEVEL={ZSTD_LEVEL}",
                f"PREDICTOR={3 if is_float else 2}",
                "NUM_THREADS=ALL_CPUS",
                "BIGTIFF=IF_SAFER",
            ],
            "lerc0_zstd": [
                "COMPRESS=LERC_ZSTD",
                "MAX_Z_ERROR=0",
                "NUM_THREADS=ALL_CPUS",
                "BIGTIFF=IF_SAFER",
            ],
        }.items():
            dst = WORK / f"{name}.tif"
            translate(src, dst, opts)
            if values_hash(dst) == base and (
                best is None or dst.stat().st_size < best[1].stat().st_size
            ):
                if best:
                    best[1].unlink()
                best = (name, dst)
            else:
                dst.unlink()
        if best is None or best[1].stat().st_size > 0.9 * src.stat().st_size:
            print(f"{key}: kept (no bit-identical candidate saves 10 %)")
            continue
        aws("s3", "cp", "--only-show-errors", str(best[1]), f"s3://{BUCKET}/{key}")
        check = WORK / "check.tif"
        aws("s3", "cp", "--only-show-errors", f"s3://{BUCKET}/{key}", str(check))
        assert values_hash(check) == base, f"{key}: uploaded copy differs"
        print(
            f"{key}: {best[0]}, {src.stat().st_size:,} -> {best[1].stat().st_size:,} bytes, values identical"
        )
        for p in (src, best[1], check):
            p.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["test", "apply"])
    ap.add_argument("--keys", nargs="*", default=DEFAULT_KEYS)
    ap.add_argument("--out", type=Path, default=Path("data/raster_recompress.json"))
    a = ap.parse_args()
    if a.action == "test":
        test(a.keys, a.out)
    else:
        apply(a.keys)


if __name__ == "__main__":
    main()
