"""site_figures: the "Check a site" figures computed server-side.

The same files and rules as frontend/src/components/SiteCards.tsx: the place from the map's
outlines; substations of 220 kV and more within the radius (PyPSA-Eur, Europe); power plants
within the radius by status and type (operating: powerplantmatching in Europe, EIA-860M in the
US; building and planned: Global Energy Monitor; elsewhere GEM for all); the day-ahead prices
of the country's bidding zones (ENTSO-E, 12 months); the water risk of the river basin holding
the site (WRI Aqueduct 4.0). Each figure is [item, value, unit, note, source], as the panel's
CSV. Line distances (vector tiles) and the per-country connection files stay in the browser.
"""

from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from data.gazetteer import in_flat_polygons, km
from tools.context import ToolContext, result

SITE_RADII = (5, 10, 25, 50, 100)
EU_PLANTS = (
    "operating: powerplantmatching (units of 20 MW and more); building and planned: "
    "Global Energy Monitor's Integrated Power Tracker"
)
GEM = "Global Energy Monitor's Integrated Power Tracker (its own size thresholds per type)"


class SiteArgs(BaseModel):
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    radius_km: int = Field(default=50, description="5, 10, 25, 50 or 100 (the panel's choices)")


@lru_cache(maxsize=16)
def _file(path: str) -> Any:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _within(rows: list, at: Any, site: tuple[float, float], r: float) -> list[tuple[Any, float]]:
    import math

    dlat = r / 111
    dlon = r / (111 * max(0.05, math.cos(math.radians(site[1]))))
    out = []
    for row in rows:
        p = at(row)
        if abs(p[1] - site[1]) > dlat or abs(((p[0] - site[0] + 540) % 360) - 180) > dlon:
            continue
        d = km(site, p)
        if d <= r:
            out.append((row, d))
    return sorted(out, key=lambda x: x[1])


def site_figures(ctx: ToolContext, lon: float, lat: float, radius_km: int = 50) -> dict[str, Any]:
    r = radius_km if radius_km in SITE_RADII else 50
    site = (lon, lat)
    pub = ctx.settings.public_dir
    place = ctx.gazetteer.locate(lon, lat)
    iso2 = place["codes"].get("iso2")
    us = "state" in place["codes"]
    figures: list[list[Any]] = [
        [
            "Place",
            place["name"],
            "",
            "",
            "the map's outlines (countries.json, world.json, states.json)",
        ],
        ["Area radius", r, "km", "figures summed within this distance", ""],
    ]
    sources: list[dict[str, str]] = []

    def src(dataset: str, table: str, licence: str, retrieved: str) -> str:
        s = {"dataset": dataset, "table": table, "licence": licence, "retrieved": retrieved}
        if s not in sources:
            sources.append(s)
        return retrieved

    # ---- grid: substations (Europe)
    if place["europe"]:
        grid = _file(str(pub / "eu/grid.json"))
        if grid:
            s = src("grid", "eu/grid.json", "ODbL", grid["source"])
            near = _within(grid["substations"], lambda x: (x[1], x[2]), site, r)
            by_kv: dict[int, int] = defaultdict(int)
            for row, _ in near:
                by_kv[row[0]] += 1
            figures.append(
                [f"Substations within {r} km", len(near), "substations", "220 kV and more", s]
            )
            for kv in sorted(by_kv, reverse=True):
                figures.append([f"Substations, {kv} kV", by_kv[kv], "substations", "", s])
            if near:
                row, d = near[0]
                figures.append(["Nearest substation", round(d, 2), "km", f"{row[0]} kV", s])

    # ---- plants
    statuses: dict[str, list[tuple[str, float, float, str | None]]] = {
        "operating": [],
        "construction": [],
        "planned": [],
    }
    if us:
        f = _file(str(pub / "us/plants.json"))
        if f:
            source = src(
                "us_plants",
                "us/plants.json",
                "public domain (EIA)",
                f"EIA-860M ({f['release']}), units of 1 MW and more, net summer capacity",
            )
            for p, d in _within(f["points"], lambda x: (x[0], x[1]), site, r):
                st = f["statuses"][p[3]]
                if st in statuses:
                    name = f["plants"][p[6]][0] if len(p) > 6 and p[6] < len(f["plants"]) else None
                    statuses[st].append((f["types"][p[2]], p[4], d, name))
    else:
        gem = _file(str(pub / "eu/world_plants.json"))
        source = GEM
        if gem:
            for p, d in _within(gem["points"], lambda x: (x[0], x[1]), site, r):
                st = gem["statuses"][p[3]]
                if st in statuses and not (place["europe"] and st == "operating"):
                    statuses[st].append((gem["types"][p[2]], p[4], d, None))
        if place["europe"]:
            eu = _file(str(pub / "eu/plants.json"))
            source = EU_PLANTS
            if eu:
                for p, d in _within(eu["plants"], lambda x: (x[2], x[3]), site, r):
                    statuses["operating"].append((eu["groups"][p[0]], p[1], d, p[5]))
                src("plants", "eu/plants.json", "CC BY 4.0", eu["source"])
        src("world_plants", "eu/world_plants.json", "CC BY 4.0 (Global Energy Monitor)", GEM)
    label = {"operating": "Operating", "construction": "Under construction", "planned": "Planned"}
    for st, rows in statuses.items():
        figures.append(
            [
                f"{label[st]} within {r} km",
                round(sum(x[1] for x in rows), 1),
                "MW",
                f"{len(rows)} map points",
                source,
            ]
        )
        by_type: dict[str, float] = defaultdict(float)
        for t, mw, _, _ in rows:
            by_type[t] += mw
        for t, mw in sorted(by_type.items(), key=lambda x: -x[1]):
            figures.append([f"{label[st]}, {t}", round(mw, 1), "MW", "", source])
    for t, mw, d, name in sorted(statuses["operating"], key=lambda x: (-x[1], x[2]))[:5]:
        figures.append([name or t, round(mw, 1), "MW", f"{t}; {round(d, 2)} km; operating", source])

    # ---- prices (Europe)
    if place["europe"] and iso2:
        prices = _file(str(pub / "eu/prices.json"))
        if prices:
            period = f"{prices['period'][0]} to {prices['period'][1]}"
            s = src(
                "prices",
                "eu/prices.json",
                "ENTSO-E Transparency Platform terms",
                "ENTSO-E day-ahead (prices.json)",
            )
            for z, v in prices["zones"].items():
                if v["country"] == iso2:
                    figures.append(
                        [f"Day-ahead {z}, 12-month average", v["mean"], "EUR/MWh", period, s]
                    )
                    figures.append(
                        [
                            f"Day-ahead {z}, hours below zero",
                            v["negative_hours"],
                            "hours",
                            period,
                            s,
                        ]
                    )

    # ---- water risk
    water = _file(str(pub / "eu/water.json"))
    if water:
        basin = next((b for b in water["basins"] if in_flat_polygons(site, b["polygons"])), None)
        if basin:
            s = src("water", "eu/water.json", "CC BY 4.0 (WRI)", "WRI Aqueduct 4.0, baseline")
            for i, ind in enumerate(water["order"]):
                info = water["indicators"].get(ind, {})
                c = basin["c"][i] if i < len(basin["c"]) else -9999
                figures.append(
                    [
                        info.get("name", ind),
                        info.get("labels", {}).get(str(c), "No Data"),
                        "WRI category",
                        f"category {c}; HydroBASINS {basin['id']}",
                        s,
                    ]
                )

    ctx.emit("site", {"lon": lon, "lat": lat, "radius_km": r})
    return result(
        {
            "site": {"lon": lon, "lat": lat},
            "place": place,
            "radius_km": r,
            "columns": ["item", "value", "unit", "note", "source"],
            "figures": figures,
        },
        sources,
    )
