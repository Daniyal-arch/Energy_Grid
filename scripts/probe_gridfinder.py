"""Probe Gridfinder's grid.gpkg (Zenodo 3628142, CC BY 4.0, 725 MB) without downloading it.

GDAL reads the GeoPackage over HTTP range requests (/vsicurl/), so only the schema and a
few features travel: layer names, fields, geometry type, feature count, sample rows.

    uv run --with pyogrio python scripts/probe_gridfinder.py
"""

from __future__ import annotations

import pyogrio

URL = "/vsicurl/https://zenodo.org/records/3628142/files/grid.gpkg"
for name, geom in pyogrio.list_layers(URL):
    print("layer", name, geom)
    info = pyogrio.read_info(URL, layer=name)
    print(
        "  features",
        info["features"],
        "crs",
        info["crs"],
        "fields",
        list(info["fields"]),
        "dtypes",
        list(info["dtypes"]),
    )
    sample = pyogrio.raw.read(URL, layer=name, max_features=5)
    print("  sample fields:", [list(col[:5]) for col in sample[3]])
