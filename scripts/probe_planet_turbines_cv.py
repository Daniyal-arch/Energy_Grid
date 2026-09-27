"""Step 0b: same 3 turbines, same before/after scenes as probe_planet_turbines.py's NDVI
test — but pull a real RGB chip around each turbine instead of computing an index, so a
vision model (a human, or an LLM with image input) can be asked directly "does this show
construction" rather than thresholding a number.

This is the CV/VLM half of "let's test both" — NDVI already showed a consistent drop at
all 3 turbines (see planet_probe_out.log). The question here is whether the disturbance
is also visually legible at PlanetScope's 3m/px, given the turbine pole itself (~4m dia.)
is at the resolution limit but the ~20m concrete foundation pad + access road should not
be.

Reuses the search/activate/auth plumbing from probe_planet_turbines.py unchanged (same
site, same windows, same already-activated assets from the last run -> should be fast).
"""

from __future__ import annotations

import os
from pathlib import Path

_rasterio_proj_data = Path(__file__).resolve().parents[1] / ".venv/Lib/site-packages/rasterio/proj_data"
if _rasterio_proj_data.exists():
    os.environ["PROJ_LIB"] = str(_rasterio_proj_data)
    os.environ["PROJ_DATA"] = str(_rasterio_proj_data)

import httpx  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from PIL import Image  # noqa: E402
from probe_planet_turbines import (  # noqa: E402
    AFTER_WINDOW,
    AUTH,
    BEFORE_WINDOW,
    TURBINES,
    activate_and_get_url,
    best_downloadable_item,
    turbine_bbox,
)
from rasterio.warp import transform as warp_transform  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "planet_chips"
CHIP_PX = 200  # ~600m at 3m/px -- wide enough to show pad + access road, not just the pole


def rgb_chip_at_point(location_url: str, lat: float, lon: float, size_px: int = CHIP_PX) -> np.ndarray:
    """Same /vsicurl/ windowed-read approach as the NDVI probe, just a much bigger window
    and 3 bands (true-color) instead of a 7x7 4-band window for one NDVI number."""
    with rasterio.Env(GDAL_HTTP_MAX_RETRY=3, GDAL_HTTP_TIMEOUT=60, CPL_VSIL_CURL_USE_HEAD=False):
        with rasterio.open(f"/vsicurl/{location_url}") as ds:
            xs, ys = warp_transform("EPSG:4326", ds.crs, [lon], [lat])
            row, col = ds.index(xs[0], ys[0])
            half = size_px // 2
            window = rasterio.windows.Window(col - half, row - half, size_px, size_px)
            # PlanetScope 4-band order is Blue, Green, Red, NIR -> true color is bands 3,2,1
            red, green, blue = (ds.read(b, window=window).astype("float32") for b in (3, 2, 1))
            rgb = np.stack([red, green, blue], axis=-1)
            # simple percentile stretch per chip so it's actually visible (raw DN values are
            # low-contrast) -- not a calibrated radiometric correction, just for eyeballing
            lo, hi = np.percentile(rgb, 2), np.percentile(rgb, 98)
            rgb = np.clip((rgb - lo) / max(hi - lo, 1e-6), 0, 1)
            return (rgb * 255).astype("uint8")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with httpx.Client(auth=AUTH, timeout=60) as c:
        for t in TURBINES:
            geom = turbine_bbox(t["lat"], t["lon"])
            before_item = best_downloadable_item(c, geom, BEFORE_WINDOW)
            after_item = best_downloadable_item(c, geom, AFTER_WINDOW)
            if not before_item or not after_item:
                print(f"{t['id']}: missing scene in one window, skipping")
                continue
            before_dl = activate_and_get_url(c, before_item)
            after_dl = activate_and_get_url(c, after_item)
            if not before_dl or not after_dl:
                print(f"{t['id']}: activation failed, skipping")
                continue
            for label, dl in (("before", before_dl), ("after", after_dl)):
                chip = rgb_chip_at_point(dl[1], t["lat"], t["lon"])
                out_path = OUT_DIR / f"{t['id']}_{label}.png"
                Image.fromarray(chip).save(out_path)
                print(f"{t['id']} {label}: wrote {out_path}")


if __name__ == "__main__":
    main()
