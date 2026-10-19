"""People: GHSL population 2025, 30 arc-seconds (brief 17, dataset 21).

JRC Global Human Settlement Layer, GHS-POP R2023A, epoch 2025, EPSG:4326 at 30 arc-seconds
(~1 km), CC BY 4.0: a 484 MB zip, downloaded and processed in GitHub Actions only.

Computed (zonal sums of the published cell values):
  - people per NUTS 3 region (GISCO NUTS 2024) and per admin-1 region (geoBoundaries CGAZ): the
    sum of the cells whose centre lies inside the region -> lake `ghsl/population`;
  - per country, the sum of its admin-1 regions, the land area of those regions (geodesic, km2)
    and people per km2 -> profiles/population.json (a "People" section in the country report);
  - a 0.1 degree grid of people per cell (the sum of its 12 x 12 source cells, whole people,
    int32, row-major from 90 N 180 W, 3600 x 1800 = 26 MB) -> the public bucket
    `grid/population-0.1deg.i32`, read by "Check a site" (cells whose centre lies within the
    site's radius, summed in the app).

    python scripts/build_population.py [--lake lake-out] [--upload]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import wave5_common as w

URL = (
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/"
    "GHS_POP_E2025_GLOBE_R2023A_4326_30ss/V1-0/GHS_POP_E2025_GLOBE_R2023A_4326_30ss_V1_0.zip"
)
NUTS_URL = (
    "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2024_4326.geojson"
)
CGAZ_URL = "https://github.com/wmgeolab/geoBoundaries/raw/main/releaseData/CGAZ/geoBoundariesCGAZ_ADM1.geojson"
TMP = Path("/tmp/wave5/ghsl")
CELL = 0.1
PER = 12  # 30 arc-seconds per 0.1 degree


def coarsen(block, per: int = PER):  # noqa: ANN001, ANN201 - numpy arrays
    """Sum of `per` x `per` cells (no-data and negative values count as 0)."""
    import numpy as np

    b = np.where(np.isfinite(block) & (block > 0), block, 0.0)
    h, wd = b.shape
    return b[: h - h % per, : wd - wd % per].reshape(h // per, per, wd // per, per).sum(axis=(1, 3))


def zonal(ds, geoms):  # noqa: ANN001, ANN201 - a rasterio dataset, shapely geometries
    """Sum of the cells whose centre lies inside each geometry (rasterio's default rule)."""
    import numpy as np
    from rasterio.mask import mask

    out = []
    for g in geoms:
        try:
            arr, _ = mask(ds, [g.__geo_interface__], crop=True, filled=True, nodata=0)
        except ValueError:  # outside the raster
            out.append(0.0)
            continue
        a = arr[0]
        out.append(float(np.where(np.isfinite(a) & (a > 0), a, 0).sum()))
    return out


def main() -> None:
    import numpy as np
    import rasterio
    from pyproj import Geod
    from shapely.geometry import shape

    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", type=Path, default=Path("lake-out"))
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    z = w.download(URL, TMP / "ghs_pop.zip")
    folder = w.unzip(z)
    tif = next(folder.rglob("*.tif"))
    with rasterio.open(tif) as ds:
        print(
            f"  {tif.name}: {ds.width} x {ds.height}, {ds.dtypes[0]}, nodata {ds.nodata}, bounds {ds.bounds}",
            flush=True,
        )
        # the 0.1 degree grid, 120 rows of source cells (= 10 grid rows) at a time
        left, top = ds.bounds.left, ds.bounds.top
        col0 = round((left + 180) / CELL)
        row0 = round((90 - top) / CELL)
        grid = np.zeros((round(180 / CELL), round(360 / CELL)), dtype=np.float64)
        step = PER * 10
        for r in range(0, ds.height - ds.height % PER, step):
            h = min(step, ds.height - ds.height % PER - r)
            block = ds.read(1, window=((r, r + h), (0, ds.width - ds.width % PER))).astype(
                np.float64
            )
            c = coarsen(block)
            grid[row0 + r // PER : row0 + r // PER + c.shape[0], col0 : col0 + c.shape[1]] = c
        total = grid.sum()
        print(
            f"  0.1 degree grid: {total:,.0f} people in all, {(grid > 0).sum():,} cells with people",
            flush=True,
        )
        out = TMP / "population-0.1deg.i32"
        np.rint(grid).astype("<i4").tofile(out)
        geod = Geod(ellps="WGS84")
        records = []
        nuts = json.loads(w.download(NUTS_URL, TMP / "nuts.geojson").read_text(encoding="utf-8"))[
            "features"
        ]
        n3 = [f for f in nuts if f["properties"]["LEVL_CODE"] == 3]
        for f, people in zip(n3, zonal(ds, [shape(f["geometry"]) for f in n3]), strict=True):
            p = f["properties"]
            records.append(
                {
                    "unit": "nuts3",
                    "id": p["NUTS_ID"],
                    "name": p["NAME_LATN"],
                    "iso2": {"EL": "GR"}.get(p["CNTR_CODE"], p["CNTR_CODE"]),
                    "iso3": p["ISO3_CODE"],
                    "people": round(people),
                    "area_km2": None,
                }
            )
        cgaz = json.loads(w.download(CGAZ_URL, TMP / "cgaz.geojson").read_text(encoding="utf-8"))[
            "features"
        ]
        shapes = [shape(f["geometry"]) for f in cgaz]
        for f, g, people in zip(cgaz, shapes, zonal(ds, shapes), strict=True):
            p = f["properties"]
            area = abs(geod.geometry_area_perimeter(g)[0]) / 1e6
            records.append(
                {
                    "unit": "admin1",
                    "id": p.get("shapeID"),
                    "name": p.get("shapeName"),
                    "iso2": None,
                    "iso3": p.get("shapeGroup"),
                    "people": round(people),
                    "area_km2": round(area, 1),
                }
            )
    by: dict[str, list[float]] = {}
    for r in records:
        if r["unit"] == "admin1" and r["iso3"]:
            s = by.setdefault(r["iso3"], [0.0, 0.0])
            s[0] += r["people"]
            s[1] += r["area_km2"] or 0
    rows = {
        iso3: [
            [
                "People",
                round(p),
                "people",
                "2025 (GHSL estimate); sum of the admin-1 regions (computed)",
            ],
            ["Land area", round(a), "km²", "geodesic area of the admin-1 regions (computed)"],
            ["People per km²", round(p / a, 1) if a else None, "per km²", "computed"],
        ]
        for iso3, (p, a) in by.items()
    }
    w.write_json(
        w.EU / "profiles" / "population.json",
        {
            "fetched": w.now(),
            "title": "People, 2025",
            "source": "GHSL GHS-POP R2023A, epoch 2025, 30 arc-seconds (JRC, CC BY 4.0); sums over geoBoundaries CGAZ admin-1 regions",
            "year": "2025",
            "rows": rows,
        },
    )
    print(f"  {len(records):,} regions summed; {len(rows)} countries", flush=True)
    if args.upload:
        w.upload_public(out, "grid/population-0.1deg.i32", "application/octet-stream")
    import duckdb

    tmp = TMP / "population.json"
    tmp.write_text(json.dumps(records), encoding="utf-8")
    con = duckdb.connect()
    import lake

    lake.iso_codes(con)
    lk = w.lake_for(
        "ghsl",
        args.lake,
        "JRC GHSL GHS-POP R2023A, epoch 2025, 30 arc-seconds",
        "CC BY 4.0",
        "scripts/build_population.py",
        "R2023A E2025",
    )
    lk.write(
        con,
        "population",
        f"""SELECT r.* EXCLUDE (iso2), coalesce(r.iso2, i.iso2) AS iso2, CASE WHEN r.unit = 'admin1' THEN r.id END AS admin1
            FROM read_json('{tmp}', maximum_object_size = 1000000000, sample_size = -1) r
            LEFT JOIN iso_codes i ON i.iso3 = r.iso3""",
        sort=["unit", "iso3", "id"],
    )
    w.lake_done(lk, args.upload)


if __name__ == "__main__":
    main()
