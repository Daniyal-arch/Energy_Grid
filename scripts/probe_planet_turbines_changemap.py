"""Step 0c: a visual "what changed" map for the same 3 turbines — before/after RGB chips
side by side with a third panel highlighting per-pixel NDVI change in color (red = lost
vegetation/new disturbance, blue = vegetation gain), instead of either a single NDVI number
or a chip a human has to eyeball unaided.

This is a quick-look diagnostic, not a calibrated change-detection product: the before/after
scenes come from different dates/sensors with their own atmospheric correction, so some of
the color difference is radiometric noise, not ground truth -- the turbine pad should still
stand out because its NDVI shift (~0.04-0.13, see planet_probe_out.log) is much larger than
typical scene-to-scene noise.
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
from PIL import Image, ImageDraw  # noqa: E402
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
CHIP_PX = 400  # ~1200m at 3m/px -- more context around the turbine
UPSCALE = 3  # native 3m pixels read as blocky/tiny at display size; upscale for legibility
DIFF_CLIP = 0.3  # NDVI diff magnitude that maps to full-strength color
LABEL_H = 26


def chip_rgb_ndvi(location_url: str, lat: float, lon: float, size_px: int) -> tuple[np.ndarray, np.ndarray]:
    """One windowed read, two products: a true-color uint8 chip and a float NDVI array,
    same window/registration so the two line up pixel-for-pixel."""
    with rasterio.Env(GDAL_HTTP_MAX_RETRY=3, GDAL_HTTP_TIMEOUT=60, CPL_VSIL_CURL_USE_HEAD=False):
        with rasterio.open(f"/vsicurl/{location_url}") as ds:
            xs, ys = warp_transform("EPSG:4326", ds.crs, [lon], [lat])
            row, col = ds.index(xs[0], ys[0])
            half = size_px // 2
            window = rasterio.windows.Window(col - half, row - half, size_px, size_px)
            blue, green, red, nir = (ds.read(b, window=window).astype("float32") for b in (1, 2, 3, 4))
    rgb = np.stack([red, green, blue], axis=-1)
    lo, hi = np.percentile(rgb, 2), np.percentile(rgb, 98)
    rgb_u8 = (np.clip((rgb - lo) / max(hi - lo, 1e-6), 0, 1) * 255).astype("uint8")
    ndvi = (nir - red) / (nir + red + 1e-9)
    return rgb_u8, ndvi


def diff_overlay(after_rgb: np.ndarray, diff: np.ndarray, clip: float = DIFF_CLIP) -> np.ndarray:
    """diff = before_ndvi - after_ndvi. Positive (vegetation lost) tints red over the
    after photo; negative (vegetation gained) tints blue. Strength scales with magnitude
    so unchanged ground stays a plain true-color photo."""
    d = np.clip(diff, -clip, clip) / clip
    alpha = np.abs(d)
    out = after_rgb.astype("float32").copy()
    lost = d > 0
    gained = d < 0
    out[..., 0] = np.where(lost, out[..., 0] * (1 - alpha) + 255 * alpha, out[..., 0])
    out[..., 1] = np.where(lost, out[..., 1] * (1 - alpha * 0.8), out[..., 1])
    out[..., 2] = np.where(lost, out[..., 2] * (1 - alpha * 0.8), out[..., 2])
    out[..., 2] = np.where(gained, out[..., 2] * (1 - alpha) + 255 * alpha, out[..., 2])
    out[..., 0] = np.where(gained, out[..., 0] * (1 - alpha * 0.8), out[..., 0])
    return np.clip(out, 0, 255).astype("uint8")


def labeled_panel(img: np.ndarray, label: str) -> Image.Image:
    """Upscale (native 3m pixels are tiny/blocky at 1:1 display size), mark the turbine's
    known position (always the exact center of the chip -- that's how the window was cut),
    then add a label strip on top."""
    big = Image.fromarray(img).resize(
        (img.shape[1] * UPSCALE, img.shape[0] * UPSCALE), Image.Resampling.LANCZOS
    )
    cx, cy = big.width // 2, big.height // 2
    draw_big = ImageDraw.Draw(big)
    r = 14
    draw_big.line([(cx - r, cy), (cx - 5, cy)], fill=(255, 60, 60), width=2)
    draw_big.line([(cx + 5, cy), (cx + r, cy)], fill=(255, 60, 60), width=2)
    draw_big.line([(cx, cy - r), (cx, cy - 5)], fill=(255, 60, 60), width=2)
    draw_big.line([(cx, cy + 5), (cx, cy + r)], fill=(255, 60, 60), width=2)

    panel = Image.new("RGB", (big.width, big.height + LABEL_H), (15, 17, 21))
    panel.paste(big, (0, LABEL_H))
    draw = ImageDraw.Draw(panel)
    draw.text((6, 5), label, fill=(220, 225, 230))
    return panel


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with httpx.Client(auth=AUTH, timeout=60) as c:
        for t in TURBINES:
            geom = turbine_bbox(t["lat"], t["lon"])
            before_item = best_downloadable_item(c, geom, BEFORE_WINDOW)
            after_item = best_downloadable_item(c, geom, AFTER_WINDOW)
            if not before_item or not after_item:
                print(f"{t['id']}: missing scene, skipping")
                continue
            before_dl = activate_and_get_url(c, before_item)
            after_dl = activate_and_get_url(c, after_item)
            if not before_dl or not after_dl:
                print(f"{t['id']}: activation failed, skipping")
                continue

            before_rgb, before_ndvi = chip_rgb_ndvi(before_dl[1], t["lat"], t["lon"], CHIP_PX)
            after_rgb, after_ndvi = chip_rgb_ndvi(after_dl[1], t["lat"], t["lon"], CHIP_PX)
            diff = before_ndvi - after_ndvi
            overlay = diff_overlay(after_rgb, diff)

            panels = [
                labeled_panel(before_rgb, f"before {before_item['properties']['acquired'][:10]}"),
                labeled_panel(after_rgb, f"after {after_item['properties']['acquired'][:10]}"),
                labeled_panel(overlay, "change (red=lost veg, blue=gained)"),
            ]
            gap = 6
            combo = Image.new("RGB", (sum(p.width for p in panels) + gap * 2, panels[0].height), (8, 9, 11))
            x = 0
            for p in panels:
                combo.paste(p, (x, 0))
                x += p.width + gap
            out_path = OUT_DIR / f"{t['id']}_changemap.png"
            combo.save(out_path)
            print(f"{t['id']}: wrote {out_path}")


if __name__ == "__main__":
    main()
