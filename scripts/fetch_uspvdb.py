"""Every large solar array in the US (USPVDB, USGS and LBNL), for the map's "US solar farms".

The U.S. Large-Scale Solar Photovoltaic Database (public domain, USGS) maps every ground-mounted
PV facility of 1 MW (DC) and more as polygons digitised from aerial imagery, with its
capacity, year, tracking and more (scripts/probe_uspvdb.py; release v4.0, 2026-04-14: 6,611
facilities). The GeoJSON zip (~10 MB) comes from energy.usgs.gov/uspvdb/data/; nothing is
downloaded when the release named on that page is already in the file (--force rebuilds).

Passed through per facility: name, state, county, year, AC and DC capacity (MW), tracking
axis, system type, site type, battery, agrivoltaic, image date, EIA plant id, the published
centre point. Computed: outlines simplified (shapely, 0.0003 degrees, about 30 m; 4 decimals).

Writes frontend/public/data/us/solar.json (the facilities) and solar_outlines.json (their
outlines, same order; the map loads them only when zoomed in). In GitHub Actions it sets the step output
`changed=solar` when it wrote a new release.

    uv run python scripts/fetch_uspvdb.py [--force]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "us" / "solar.json"
OUTLINES = OUT.with_name("solar_outlines.json")
PAGE = "https://energy.usgs.gov/uspvdb/data/"
ZIP = "https://energy.usgs.gov/uspvdb/assets/data/uspvdbGeoJSON.zip"
TOLERANCE = 0.0003
# categorical fields: the values as published, the rows hold their index
CATS = ["p_axis", "p_sys_type", "p_type", "p_agrivolt", "p_tech_pri"]


def release_of(html: str) -> str:
    m = re.search(r"uspvdb_v(\d+)_(\d+)_(\d{8})\.xml", html)
    if not m:
        raise SystemExit("USPVDB: no release file named on the data page")
    d = m.group(3)
    return f"v{m.group(1)}.{m.group(2)} ({d[:4]}-{d[4:6]}-{d[6:]})"


def flat_rings(geom) -> list[list[list[float]]]:  # noqa: ANN001 - a shapely geometry
    polys = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
    out = []
    for p in polys:
        if p.geom_type != "Polygon" or p.is_empty:
            continue
        out.append(
            [[round(c, 4) for xy in r.coords for c in xy[:2]] for r in [p.exterior, *p.interiors]]
        )
    return out


def num(v: object) -> float | None:
    try:
        x = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if x != x else x


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    with httpx.Client(timeout=300, follow_redirects=True) as c:
        release = release_of(c.get(PAGE).text)
        if (
            OUT.exists()
            and not args.force
            and json.loads(OUT.read_text(encoding="utf-8")).get("release") == release
        ):
            print(f"USPVDB {release}: already in {OUT.name}")
            return
        print(f"USPVDB {release}: downloading the GeoJSON zip (~10 MB)", flush=True)
        z = zipfile.ZipFile(io.BytesIO(c.get(ZIP).raise_for_status().content))
    name = next(n for n in z.namelist() if n.lower().endswith(".geojson"))
    feats = json.loads(z.read(name))["features"]
    cats: dict[str, list[str]] = {k: [] for k in CATS}

    def cat(k: str, v: object) -> int | None:
        if v is None:
            return None
        s = str(v)
        if s not in cats[k]:
            cats[k].append(s)
        return cats[k].index(s)

    sites, polygons = [], []
    for f in feats:
        p = f["properties"]
        g = shape(f["geometry"]) if f.get("geometry") else None
        if g is not None and not g.is_valid:
            g = g.buffer(0)
        sites.append(
            [
                num(p.get("xlong")),
                num(p.get("ylat")),
                num(p.get("p_cap_ac")),
                num(p.get("p_cap_dc")),
                int(y) if (y := num(p.get("p_year"))) is not None else None,
                p.get("p_name"),
                p.get("p_state"),
                p.get("p_county"),
                *[cat(k, p.get(k)) for k in CATS],
                p.get("p_battery"),
                int(i) if (i := num(p.get("eia_id"))) is not None else None,
                p.get("p_img_date"),
            ]
        )
        polygons.append(
            flat_rings(g.simplify(TOLERANCE, preserve_topology=True)) if g is not None else []
        )
    payload = {
        "source": "U.S. Large-Scale Solar Photovoltaic Database (USPVDB), USGS and LBNL, public domain",
        "release": release,
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "fields": [
            "lon",
            "lat",
            "mw_ac",
            "mw_dc",
            "year",
            "name",
            "state",
            "county",
            *CATS,
            "p_battery",
            "eia_id",
            "p_img_date",
        ],
        "categories": cats,
        "sites": sites,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    OUTLINES.write_text(
        json.dumps({"release": release, "polygons": polygons}, separators=(",", ":")),
        encoding="utf-8",
    )
    mw = sum(s[2] or 0 for s in sites)
    print(
        f"{len(sites)} facilities, {mw / 1000:.1f} GW AC, {OUT.stat().st_size / 1e6:.1f} + {OUTLINES.stat().st_size / 1e6:.1f} MB; categories {cats}"
    )
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write("changed=solar\n")


if __name__ == "__main__":
    main()
