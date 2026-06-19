"""Simplify the grid GeoJSON layer assets (fewer vertices → lighter render + load).
Display tolerance ~80 m; keeps shape, drops redundant points. Attributes untouched."""

from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import mapping, shape

TOL = 0.0008  # degrees (~80 m) — plenty for map display


def nverts(g: dict) -> int:
    t = g["type"]
    c = g["coordinates"]
    if t == "LineString":
        return len(c)
    if t == "MultiLineString":
        return sum(len(line) for line in c)
    return 0


def simplify_file(path: str) -> None:
    p = Path(path)
    fc = json.loads(p.read_text(encoding="utf-8"))
    before_kb = p.stat().st_size / 1024
    vb = va = 0
    for f in fc["features"]:
        g = f.get("geometry")
        if not g or g["type"] not in ("LineString", "MultiLineString"):
            continue
        vb += nverts(g)
        simp = shape(g).simplify(TOL, preserve_topology=False)
        if simp.is_empty:
            continue
        f["geometry"] = mapping(simp)
        va += nverts(f["geometry"])
    p.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
    after_kb = p.stat().st_size / 1024
    print(f"{path}: {before_kb:.0f} KB -> {after_kb:.0f} KB   verts {vb} -> {va} ({va * 100 // max(vb, 1)}%)")


if __name__ == "__main__":
    simplify_file("frontend/public/grid_transmission.geojson")
    simplify_file("frontend/public/grid_planned.geojson")
