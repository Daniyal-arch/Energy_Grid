"""area_stats (docs/tasks/27, A4): rasters summed, averaged or counted by class inside an area.

Zonal statistics over cloud-optimised GeoTIFFs read by HTTP range (rasterio / GDAL): the cells
whose centre lies inside the outline count (GDAL's rasterize rule). Sums use the finest
published product within the cell budget, else the next published one (GHSL publishes 3 and
30 arc-second grids); means and classes may read a COG overview above the budget. Every figure
names the raster, the cell size used and the rule. Nothing is interpolated.

The measures and their rasters: agent/rasters.yaml.
"""

from __future__ import annotations

import math
import os
import time
from contextlib import ExitStack
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from data.areas import Area
from tools.context import ToolContext, result

Measure = Literal["people", "built_up", "land_cover", "slope", "solar", "wind", "flood"]
BLOCK = 2048  # rows per read


class AreaStatsArgs(BaseModel):
    area_id: str = Field(pattern=r"^a_[0-9a-f]{12}$", description="from resolve_area")
    measures: list[Measure] = Field(
        min_length=1,
        max_length=7,
        description="people, built_up (m²), land_cover (class shares), slope (class shares), "
        "solar (PVOUT mean), wind (100 m mean speed), flood (RP100 depth class shares)",
    )


class StatsError(RuntimeError):
    """The raster could not be read for this area; the message says why."""


@lru_cache
def measures(agent_dir: str) -> dict[str, Any]:
    p = Path(agent_dir) / "rasters.yaml"
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("measures") or {}


def gdal_path(ctx: ToolContext, url: str) -> str | None:
    """The GDAL path of a raster URL; a local copy (settings.rasters_dir) wins. None: unreadable
    here (an r2:// raster without R2 keys)."""
    s = ctx.settings
    local = getattr(s, "rasters_dir", None)
    if local:
        p = Path(local) / url.rsplit("/", 1)[-1]
        if p.exists():
            return str(p)
    if url.startswith("r2://"):
        if not s.r2_configured:
            return None
        return "/vsis3/" + url.removeprefix("r2://")
    if url.startswith("s3://"):
        return "/vsis3/" + url.removeprefix("s3://")
    if url.startswith("https://"):
        return "/vsicurl/" + url
    return url


def gdal_env(ctx: ToolContext, url: str) -> dict[str, Any]:
    """rasterio.Env arguments: GDAL options and, for S3 paths, the AWS session (rasterio does
    not take AWS_* options directly)."""
    from rasterio.session import AWSSession

    s = ctx.settings
    env: dict[str, Any] = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff",
        "GDAL_HTTP_MAX_RETRY": "3",
        "GDAL_HTTP_RETRY_DELAY": "1",
        "VSI_CACHE": "TRUE",
    }
    if url.startswith("r2://") and s.r2_configured:
        env["session"] = AWSSession(
            aws_access_key_id=s.r2_access_key_id,
            aws_secret_access_key=s.r2_secret_access_key,
            region_name="auto",
            endpoint_url=f"{s.r2_account_id}.r2.cloudflarestorage.com",
        )
    elif url.startswith("s3://"):
        env["session"] = AWSSession(aws_unsigned=True, region_name="eu-central-1")
    ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if ca:
        env["CURL_CA_BUNDLE"] = ca
    return env


def tile_urls(template: str, step: int, bbox: list[float]) -> list[str]:
    """The tiles (named from their south-west corner) covering a bounding box."""
    x0, y0, x1, y1 = bbox
    out = []
    lat = math.floor(y0 / step) * step
    while lat < y1:
        lon = math.floor(x0 / step) * step
        while lon < x1:
            out.append(
                template.format(
                    NS="N" if lat >= 0 else "S",
                    lat=abs(int(lat)),
                    EW="E" if lon >= 0 else "W",
                    lon=abs(int(lon)),
                )
            )
            lon += step
        lat += step
    return out


@dataclass
class Acc:
    """What the blocks add up to."""

    total: float = 0.0
    cells: int = 0
    lo: float = math.inf
    hi: float = -math.inf
    counts: dict[int, float] | None = None


def _accumulate(acc: Acc, arr: Any, inside: Any, spec: dict[str, Any], layer: dict) -> None:
    import numpy as np

    stat = spec["stat"]
    if layer.get("shares"):  # bands of shares per class (a 1 km product)
        acc.counts = acc.counts or {}
        valid = inside & np.isfinite(arr[0]) & (arr.sum(axis=0) > 0)
        for b, k in enumerate(spec["classes"]):
            acc.counts[int(k)] = acc.counts.get(int(k), 0.0) + float(arr[b][valid].sum())
        acc.cells += int(valid.sum())
        return
    v = arr[0] if arr.ndim == 3 else arr
    if stat == "classes":
        acc.counts = acc.counts or {}
        sel = v[inside]
        if "nodata_is" in spec:
            sel = np.where(np.isnan(sel), spec["nodata_is"], sel) if sel.dtype.kind == "f" else sel
        vals, n = np.unique(
            sel[np.isfinite(sel)] if sel.dtype.kind == "f" else sel, return_counts=True
        )
        for k, c in zip(vals.tolist(), n.tolist(), strict=True):
            acc.counts[int(k)] = acc.counts.get(int(k), 0) + c
        acc.cells += int(sel.size)
        return
    sel = v[inside]
    sel = sel[np.isfinite(sel)] if sel.dtype.kind == "f" else sel
    if stat == "sum":
        sel = sel[sel > 0] if sel.dtype.kind == "f" else sel
    if sel.size:
        acc.total += float(sel.astype("float64").sum())
        acc.lo = min(acc.lo, float(sel.min()))
        acc.hi = max(acc.hi, float(sel.max()))
    acc.cells += int(sel.size)


def _slope_classes(dem: Any, transform: Any, breaks: list[float]) -> Any:
    """Slope in degrees from a lon/lat DEM (cell sizes in metres at each row), as classes 1..n."""
    import numpy as np

    rows = dem.shape[0]
    lat = transform.f + transform.e * (np.arange(rows) + 0.5)
    dy = abs(transform.e) * 111_320.0
    dx = abs(transform.a) * 111_320.0 * np.cos(np.radians(lat))[:, None]
    gy, gx = np.gradient(dem.astype("float64"))
    slope = np.degrees(np.arctan(np.hypot(gx / dx, gy / dy)))
    return np.digitize(slope, breaks) + 1


def zonal(ctx: ToolContext, area: Area, name: str, *, budget: int | None = None) -> dict[str, Any]:
    """One measure inside one area."""
    import numpy as np
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.warp import transform_geom
    from rasterio.windows import from_bounds

    spec = measures(str(ctx.settings.agent_dir)).get(name)
    if spec is None:
        raise StatsError(f"unknown measure {name}")
    budget = budget or ctx.settings.area_stats_max_cells
    t0 = time.perf_counter()
    errors: list[str] = []
    for layer in spec["layers"]:
        urls = (
            tile_urls(layer["tiles"], layer["tile_deg"], area.bbox)
            if "tiles" in layer
            else [layer["url"]]
        )
        if "tiles" in layer and len(urls) > ctx.settings.area_stats_max_tiles:
            errors.append(f"{len(urls)} tiles at {layer['cell']}: too many for one answer")
            continue
        acc = Acc()
        used_cell = layer["cell"]
        try:
            for url in urls:
                path = gdal_path(ctx, url)
                if path is None:
                    raise StatsError(f"{url} needs the lake's R2 keys")
                with ExitStack() as stack:
                    stack.enter_context(rasterio.Env(**gdal_env(ctx, url)))
                    try:
                        src = stack.enter_context(rasterio.open(path))
                    except rasterio.errors.RasterioIOError as e:
                        if "tiles" in layer:  # sea: no tile there
                            continue
                        raise StatsError(f"{url}: {str(e)[:160]}") from e
                    geom = area.geometry
                    if src.crs and src.crs.to_epsg() != 4326:
                        geom = transform_geom("EPSG:4326", src.crs, geom)
                    gx0, gy0, gx1, gy1 = _bounds(geom)
                    b = src.bounds
                    gx0, gy0 = max(gx0, b.left), max(gy0, b.bottom)
                    gx1, gy1 = min(gx1, b.right), min(gy1, b.top)
                    if gx0 >= gx1 or gy0 >= gy1:
                        continue
                    win = (
                        from_bounds(gx0, gy0, gx1, gy1, src.transform)
                        .round_offsets()
                        .round_lengths()
                    )
                    w, h = max(1, int(win.width)), max(1, int(win.height))
                    scale = 1
                    if w * h > budget:
                        if spec["stat"] == "sum" and layer is not spec["layers"][-1]:
                            raise _TooBig(f"{w * h:,} cells at {layer['cell']}")
                        if spec["stat"] == "sum":
                            raise StatsError(
                                f"{w * h:,} cells at {layer['cell']} exceed the budget; ask "
                                "per country (ghsl.population)"
                            )
                        scale = math.ceil(math.sqrt(w * h / budget))
                        used_cell = f"{layer['cell']} read at 1/{scale} (COG overview)"
                    for r0 in range(0, h, BLOCK * scale):
                        rh = min(BLOCK * scale, h - r0)
                        sub = rasterio.windows.Window(win.col_off, win.row_off + r0, w, rh)
                        out_shape = (max(1, rh // scale), max(1, w // scale))
                        bands = list(range(1, src.count + 1)) if layer.get("shares") else [1]
                        arr = src.read(
                            bands, window=sub, out_shape=(len(bands), *out_shape), masked=False
                        )
                        tr = src.window_transform(sub) @ rasterio.Affine.scale(
                            sub.width / out_shape[1], sub.height / out_shape[0]
                        )
                        if layer.get("derive") == "slope":
                            arr = _slope_classes(arr[0], tr, spec["breaks"])[None]
                        else:
                            nod = src.nodata
                            if nod is not None and arr.dtype.kind == "f":
                                arr = np.where(arr == nod, np.nan, arr)
                            elif nod is not None and spec["stat"] != "classes":
                                arr = np.where(arr == nod, 0, arr)
                        inside = geometry_mask(
                            [geom], out_shape=out_shape, transform=tr, invert=True
                        )
                        if not inside.any():
                            continue
                        _accumulate(acc, arr, inside, spec, layer)
        except _TooBig as e:
            errors.append(str(e))
            continue
        except StatsError as e:
            errors.append(str(e))
            continue
        ms = round((time.perf_counter() - t0) * 1000)
        return _figure(spec, layer, acc, used_cell, ms, urls)
    raise StatsError("; ".join(errors) or "no raster covers this area")


class _TooBig(Exception):
    pass


def _bounds(geom: dict[str, Any]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []

    def walk(c: Any) -> None:
        if isinstance(c[0], int | float):
            xs.append(c[0])
            ys.append(c[1])
        else:
            for x in c:
                walk(x)

    walk(geom["coordinates"])
    return min(xs), min(ys), max(xs), max(ys)


def _figure(
    spec: dict[str, Any], layer: dict, acc: Acc, cell: str, ms: int, urls: list[str]
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "title": spec["title"],
        "unit": spec["unit"],
        "how": f"{spec['how']}; cells of {cell}",
        "cells": acc.cells,
        "raster": urls[0] if len(urls) == 1 else f"{len(urls)} tiles of {layer['tiles']}",
        "licence": spec["licence"],
        "ms": ms,
    }
    if spec["stat"] == "sum":
        out["value"] = round(acc.total, 1)
    elif spec["stat"] == "mean":
        out["value"] = round(acc.total / acc.cells, 3) if acc.cells else None
        out["range"] = [round(acc.lo, 3), round(acc.hi, 3)] if acc.cells else None
    else:
        tot = sum((acc.counts or {}).values()) or 1
        names = spec.get("classes") or {}
        out["shares"] = {
            str(names.get(k, names.get(str(k), k))): round(v / tot, 4)
            for k, v in sorted((acc.counts or {}).items())
        }
    return out


def people_in(ctx: ToolContext, area: Area) -> dict[str, Any] | None:
    """The area's people (resolve_area's own figure); None when no raster is readable here."""
    spec = measures(str(ctx.settings.agent_dir)).get("people")
    if not spec or not any(gdal_path(ctx, x["url"]) for x in spec["layers"]):
        return {"value": None, "note": "population raster not readable here (lake keys)"}
    if area.level == "world":
        return None
    return zonal(ctx, area, "people")


def area_stats(ctx: ToolContext, area_id: str, measures: list[str]) -> dict[str, Any]:
    area = ctx.area_store.get(area_id)
    if area is None:
        return result({"error": f"unknown area {area_id}; resolve_area first"}, [])
    figures: dict[str, Any] = {}
    sources = []
    for m in dict.fromkeys(measures):
        try:
            f = zonal(ctx, area, m)
        except StatsError as e:
            figures[m] = {"value": None, "error": str(e)}
            continue
        except Exception as e:  # GDAL and network errors go back as data
            figures[m] = {"value": None, "error": f"{type(e).__name__}: {str(e)[:200]}"}
            continue
        figures[m] = f
        sources.append(
            {
                "dataset": f["title"],
                "table": f["raster"],
                "licence": f["licence"],
                "retrieved": f["how"][:200],
            }
        )
    ctx.emit("tool_detail", {"tool": "area_stats", "area": area_id})
    return result(
        {
            "area": {"area_id": area.area_id, "name": area.name, "area_km2": area.area_km2},
            "figures": figures,
        },
        sources,
    )
