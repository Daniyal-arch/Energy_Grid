"""Probe for area_stats (brief 27 A4): GHSL population of Berlin by area_stats against an
independent sum (every cell's centre tested with DuckDB spatial's ST_Contains).

    uv run python probes/probe_area_stats.py <ghsl_pop_3ss.tif> <nuts_level1.geojson> [--lake]

With --lake, area_stats reads the lake's tiles on R2 (R2 keys in the environment) instead of
the local file; the independent sum always reads the local tile.

The raster: a GHSL E2025 3 arc-second tile covering Berlin (R4_C20, 151 MB zip) or the lake's
mosaic; the outline: GISCO NUTS 2024 1:1M level 1 (DE3 = Berlin).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import duckdb
import numpy as np
import rasterio
from rasterio.windows import from_bounds

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def independent(tif: str, geom: dict) -> tuple[float, int]:
    con = duckdb.connect()
    con.load_extension("spatial")
    con.execute("SET geometry_always_xy = true")
    con.execute("CREATE TABLE g AS SELECT ST_GeomFromGeoJSON(?) AS g", [json.dumps(geom)])
    x0, y0, x1, y1 = con.execute(
        "SELECT ST_XMin(g), ST_YMin(g), ST_XMax(g), ST_YMax(g) FROM g"
    ).fetchone()
    with rasterio.open(tif) as src:
        win = from_bounds(x0, y0, x1, y1, src.transform).round_offsets().round_lengths()
        a = src.read(1, window=win)
        tr = src.window_transform(win)
    rows, cols = np.nonzero(a > 0)
    xs = tr.c + (cols + 0.5) * tr.a
    ys = tr.f + (rows + 0.5) * tr.e
    vals = a[rows, cols]
    con.execute(
        "CREATE TABLE c AS SELECT * FROM (SELECT unnest(?) x, unnest(?) y, unnest(?) v)",
        [xs.tolist(), ys.tolist(), vals.tolist()],
    )
    s, n = con.execute(
        "SELECT sum(v), count(*) FROM c, g WHERE ST_Contains(g.g, ST_Point(x, y))"
    ).fetchone()
    return float(s), int(n)


def main() -> None:
    tif, nuts = sys.argv[1], sys.argv[2]
    feat = next(
        f
        for f in json.loads(Path(nuts).read_text())["features"]
        if f["properties"]["NUTS_ID"] == "DE3"
    )
    geom = feat["geometry"]
    t0 = time.perf_counter()
    ref, n = independent(tif, geom)
    print(f"independent: {ref:,.1f} people in {n:,} cells ({time.perf_counter() - t0:.1f} s)")

    tmp = Path(tempfile.mkdtemp())
    os.environ.update(
        {
            "AGENT_MODEL": "fake",
            "LAKE_DB": "",
            "RESULTS_DIR": str(tmp),
            "LOCAL_STORE_DIR": str(tmp / "s"),
            "RASTERS_DIR": str(Path(tif).parent),
        }
    )
    from app.settings import Settings
    from tools.area_stats import area_stats
    from tools.context import ToolContext

    ctx = ToolContext(Settings())
    area = ctx.areas.make(
        json.dumps(geom),
        name="Berlin",
        level="nuts1",
        iso3=["DEU"],
        parents=["Germany"],
        source={"dataset": "GISCO NUTS 2024 1:1M", "licence": "© EuroGeographics"},
        how="probe",
    )
    t0 = time.perf_counter()
    r = area_stats(ctx, area.area_id, ["people"])
    f = r["data"]["figures"]["people"]
    if f.get("value") is None:
        sys.exit(f"area_stats failed: {f}")
    print(
        f"area_stats:  {f['value']:,.1f} people in {f['cells']:,} cells ({time.perf_counter() - t0:.1f} s); {f['how']}"
    )
    print(f"difference:  {f['value'] - ref:+.1f} people ({(f['value'] - ref) / ref * 100:+.4f} %)")


if __name__ == "__main__":
    main()
