"""Country outlines without GISCO's non-commercial clause, behind a flag (brief 30 Track 1.8).

Eurostat GISCO's terms say its administrative units may not be used for commercial purposes.
This builds the same two app files from Natural Earth's admin-0 countries 1:10m (public
domain, https://www.naturalearthdata.com/about/terms-of-use/), with the same simplification as
`build_eu_grid.py`, into `frontend/public/data/eu/open/` (the app reads them with `?shapes=open`;
the default stays GISCO until the owner decides), and writes a side-by-side check of codes,
names and outlines against GISCO: `docs/research/gisco-replacement.md`.

Downloads: Natural Earth 10m countries GeoJSON (13.3 MB), GISCO CNTR_RG_20M (when missing).

    uv run python scripts/build_open_shapes.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_eu_grid as g  # noqa: E402

NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_admin_0_countries.geojson"
GISCO = "https://gisco-services.ec.europa.eu/distribution/v2/countries/geojson/CNTR_RG_20M_2024_4326.geojson"
CACHE = ROOT / "data" / "open"
OUT = ROOT / "frontend" / "public" / "data" / "eu" / "open"
REPORT = ROOT / "docs" / "research" / "gisco-replacement.md"
SOURCE = "Natural Earth admin-0 countries 1:10m, v5.1.2 (public domain)"


def get(url: str, path: Path) -> dict:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {url}", flush=True)
        with httpx.stream("GET", url, timeout=300, follow_redirects=True) as r:
            r.raise_for_status()
            with path.open("wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
                    print(f"  {f.tell() / 1e6:.1f} MB", end="\r", flush=True)
        print()
    return json.loads(path.read_text(encoding="utf-8"))


def as_gisco(ne: dict) -> dict:
    """Natural Earth features with GISCO's property names: CNTR_ID uses GISCO's EL and UK.
    Features sharing a code (a country and its dependencies, e.g. GB and the Sovereign Base
    Areas) are merged into one, as GISCO has one feature per code."""
    feats: list[dict] = []
    for f in ne["features"]:
        p = f["properties"]
        iso2 = p.get("ISO_A2_EH") or p.get("ISO_A2")
        if not iso2 or iso2 == "-99":
            continue
        feats.append(
            {
                "type": "Feature",
                "properties": {
                    "CNTR_ID": g.GISCO_ID.get(iso2, iso2),
                    "NAME_ENGL": p.get("NAME_EN") or p["NAME"],
                    "ISO3_CODE": p.get("ISO_A3_EH") if p.get("ISO_A3_EH") != "-99" else "",
                },
                "geometry": f["geometry"],
            }
        )
    merged: dict[str, dict] = {}
    for f in feats:
        k = f["properties"]["CNTR_ID"]
        if k in merged:
            m = merged[k]
            geom = unary_union([shape(m["geometry"]), shape(f["geometry"])])
            m["geometry"] = mapping(geom)
        else:
            merged[k] = f
    return {"type": "FeatureCollection", "features": list(merged.values())}


def check(gisco: dict, ne: dict) -> str:
    """Per atlas country: codes and names on both sides, areas (km², LAEA Europe) and the
    overlap (intersection over union) of the full-detail outlines, Europe only (as the app)."""
    laea = Transformer.from_crs("EPSG:4326", "EPSG:3035", always_xy=True).transform

    def by_id(fc: dict) -> dict[str, tuple[str, object]]:
        out: dict[str, list] = {}
        for f in fc["features"]:
            out.setdefault(f["properties"]["CNTR_ID"], []).append(f)
        res = {}
        for k, fs in out.items():
            geom = unary_union([shape(f["geometry"]) for f in fs])
            parts = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
            geom = unary_union(
                [p for p in parts if -25 <= p.centroid.x <= 45 and 34 <= p.centroid.y <= 72]
            )
            res[k] = (fs[0]["properties"]["NAME_ENGL"], transform(laea, geom))
        return res

    a, b = by_id(gisco), by_id(ne)
    rows = [
        "| Code | GISCO name | Natural Earth name | GISCO km² | NE km² | Overlap (IoU) |",
        "|---|---|---|---|---|---|",
    ]
    worst = []
    for iso in g.COUNTRIES:
        k = g.GISCO_ID.get(iso, iso)
        if k not in a or k not in b:
            rows.append(
                f"| {iso} | {a.get(k, ('missing',))[0]} | {b.get(k, ('missing',))[0]} | | | |"
            )
            worst.append((0.0, iso))
            continue
        (na, ga), (nb, gb) = a[k], b[k]
        iou = ga.intersection(gb).area / ga.union(gb).area
        worst.append((iou, iso))
        rows.append(
            f"| {iso} | {na} | {nb} | {ga.area / 1e6:,.0f} | {gb.area / 1e6:,.0f} | {iou:.3f} |"
        )
    worst.sort()
    lo = ", ".join(f"{i} {v:.3f}" for v, i in worst[:6])
    return "\n".join(rows) + f"\n\nLowest overlaps: {lo}.\n"


def main() -> None:
    ne_raw = get(NE, CACHE / "ne_10m_admin_0_countries.geojson")
    gisco = get(GISCO, g.SRC / "countries.geojson")
    ne = as_gisco(ne_raw)
    OUT.mkdir(parents=True, exist_ok=True)
    countries = g.build_countries(ne, SOURCE)
    world = g.build_world(ne)
    for name, payload in (("countries.json", countries), ("world.json", world)):
        path = OUT / name
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        print(f"open/{name}: {path.stat().st_size / 1e6:.2f} MB")
    have = {c["iso"] for c in countries["countries"]}
    missing = [c for c in g.COUNTRIES if c not in have]
    table = check(gisco, ne)
    REPORT.write_text(
        "# GISCO replacement: Natural Earth countries side by side (brief 30 Track 1.8)\n\n"
        "Generated by `scripts/build_open_shapes.py`. GISCO CNTR_RG_20M 2024 against Natural "
        "Earth admin-0 countries 1:10m v5.1.2 (public domain), both before the app's "
        "simplification, Europe only (parts outside 25 W-45 E, 34-72 N dropped, as the app "
        "does). Areas in ETRS89 LAEA (EPSG:3035). Overlap = area of the intersection / area "
        "of the union.\n\n"
        f"Countries in the app's list without a Natural Earth outline: {missing or 'none'}.\n\n"
        f"{table}\n"
        "Natural Earth draws de facto borders: northern Cyprus and Kosovo are their own "
        "features, and some coastlines are coarser at 1:10m than GISCO's 1:20M is at the "
        "same simplification; see the lowest overlaps above.\n",
        encoding="utf-8",
    )
    print(f"report: {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
