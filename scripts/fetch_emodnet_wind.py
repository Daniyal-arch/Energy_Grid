"""Offshore wind farms in European seas (EMODnet Human Activities), for the map's layer.

EMODnet Human Activities (data originator CETMAR, updated yearly; CC BY 4.0 per the EMODnet
catalogue record 8201070b-4b0b-4d54-8910-abcea5dce57f) publishes wind farms as areas
(`emodnet:windfarmspoly`) and as points (`emodnet:windfarms`) over WFS, no key
(scripts/probe_emodnet.py). Passed through per farm: name, country, status, MW, turbines, year,
distance to the coast. Computed: areas simplified (shapely, 0.002 degrees, 4 decimals); a label
point inside each area; a point is kept only when no area lies within 0.01 degrees (about 1 km)
of it, so a farm published both ways counts once (as its area); the country's ISO alpha-3 code
(pycountry) for the panel's country filter.

Writes frontend/public/data/eu/offshore_wind.json.

    uv run python scripts/fetch_emodnet_wind.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pycountry
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu" / "offshore_wind.json"
WFS = "https://ows.emodnet-humanactivities.eu/wfs"
STATUSES = ["Production", "Construction", "Approved", "Planned", "Test site", "Dismantled"]
TOLERANCE = 0.002
SAME_FARM_DEG = 0.01


def features(layer: str) -> list[dict]:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": layer,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
    }
    r = httpx.get(WFS, params=params, timeout=300)
    r.raise_for_status()
    return r.json()["features"]


def num(v: object) -> float | None:
    try:
        x = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if x != x else x


def iso3_of(name: object) -> str | None:
    try:
        return pycountry.countries.lookup(str(name)).alpha_3
    except LookupError:
        return None


def flat_rings(geom) -> list[list[list[float]]]:  # noqa: ANN001 - a shapely geometry
    polys = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
    out = []
    for p in polys:
        if p.geom_type != "Polygon" or p.is_empty:
            continue
        rings = [p.exterior, *p.interiors]
        out.append([[round(c, 4) for xy in r.coords for c in xy[:2]] for r in rings])
    return out


def farm(p: dict, at: tuple[float, float], polygons: list | None) -> dict:
    status = str(p.get("status") or "")
    year = num(p.get("year"))
    coast = num(p.get("dist_coast"))
    return {
        "name": p.get("name"),
        "country": p.get("country"),
        "iso3": iso3_of(p.get("country")),
        "status": STATUSES.index(status) if status in STATUSES else None,
        "mw": num(p.get("power_mw")),
        "turbines": int(t) if (t := num(p.get("n_turbines"))) is not None else None,
        "year": int(year) if year is not None else None,
        # metres in the source; km here, rounded to 0.1
        "coast_km": round(coast / 1000, 1) if coast is not None else None,
        "at": [round(at[0], 4), round(at[1], 4)],
        "polygons": polygons,
    }


def main() -> None:
    areas = features("emodnet:windfarmspoly")
    points = features("emodnet:windfarms")
    farms = []
    shapes = []
    for f in areas:
        if not f.get("geometry"):
            continue
        g = shape(f["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        simple = g.simplify(TOLERANCE, preserve_topology=True)
        rp = g.representative_point()
        farms.append(farm(f["properties"], (rp.x, rp.y), flat_rings(simple)))
        shapes.append(g)
    tree = STRtree(shapes)
    extra = 0
    for f in points:
        if not f.get("geometry"):
            continue
        x, y = f["geometry"]["coordinates"][:2]
        if len(tree.query(Point(x, y), predicate="dwithin", distance=SAME_FARM_DEG)):
            continue
        farms.append(farm(f["properties"], (x, y), None))
        extra += 1
    unknown = sorted({str(f["properties"].get("status")) for f in areas + points} - set(STATUSES))
    payload = {
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "EMODnet Human Activities, offshore wind farms (CETMAR), WFS emodnet:windfarmspoly and emodnet:windfarms",
        "licence": "CC BY 4.0",
        "statuses": STATUSES,
        "farms": farms,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(
        f"{len(areas)} areas, {len(points)} points ({extra} without an area kept), "
        f"statuses not in the list: {unknown}; {OUT.stat().st_size / 1e6:.2f} MB"
    )


if __name__ == "__main__":
    main()
