"""Open world-wide figures for the World tab (no keys).

  access       World Bank WDI EG.ELC.ACCS.ZS, access to electricity (% of population),
               every country and the world, 2000 onwards, as published
  datacentres  OpenStreetMap via Overpass: features tagged telecom=data_center or
               building=data_center, one point each (ways and relations at their centre).
               OpenStreetMap is incomplete here: a mapped subset, not a census

               Each point is placed in a country with Eurostat GISCO outlines (computed)

Writes frontend/public/data/eu/:
  world_stats.json  {"source", "fetched", "years", "access": {ISO3: [% or null per year]}}
  datacentres.json  {"source", "fetched", "count", "by_country": {ISO3: n},
                     "clusters": [[lon, lat, sites]] (per 1-degree cell, computed),
                     "points": [[lon, lat, name, operator]]}

    uv run python scripts/fetch_world.py [--out DIR] [--skip-osm]
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu"
GISCO = ROOT / "data" / "eu" / "countries.geojson"  # scripts/fetch_eu_energy.py
WB = "https://api.worldbank.org/v2"
OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = '[out:json][timeout:300];(nwr["telecom"="data_center"];nwr["building"="data_center"];);out center tags;'


def call(client: httpx.Client, method: str, url: str, **kwargs: object) -> httpx.Response:
    """One request, retried when the connection drops or the server is busy."""
    for attempt in range(6):
        try:
            r = client.request(method, url, **kwargs)  # type: ignore[arg-type]
        except httpx.TransportError as err:
            print(f"  {err.__class__.__name__}, retry", flush=True)
            time.sleep(20 * (attempt + 1))
            continue
        if r.status_code == 200 and r.content.lstrip()[:1] in (b"{", b"["):
            return r
        print(f"  HTTP {r.status_code}, waiting", flush=True)
        time.sleep(60 * (attempt + 1))
    raise RuntimeError(f"{url}: no answer")


def access(client: httpx.Client) -> dict:
    countries = call(
        client, "GET", f"{WB}/country", params={"format": "json", "per_page": "400"}
    ).json()[1]
    # aggregates (regions, income groups) are not countries; the world stays as WLD
    keep = {c["id"] for c in countries if c["region"]["value"] != "Aggregates"} | {"WLD"}
    r = call(
        client,
        "GET",
        f"{WB}/country/all/indicator/EG.ELC.ACCS.ZS",
        params={"format": "json", "per_page": "20000", "date": "2000:2030"},
    )
    rows = r.json()[1]
    years = sorted({int(x["date"]) for x in rows if x["value"] is not None})
    at = {y: i for i, y in enumerate(years)}
    out: dict[str, list] = {}
    for x in rows:
        code = x["countryiso3code"]
        if code not in keep or x["value"] is None:
            continue
        out.setdefault(code, [None] * len(years))[at[int(x["date"])]] = round(x["value"], 1)
    return {"years": [str(y) for y in years], "access": dict(sorted(out.items()))}


def datacentres(client: httpx.Client) -> list[list]:
    r = call(client, "POST", OVERPASS, data={"data": QUERY})
    points: dict[tuple[float, float], list] = {}
    for e in r.json()["elements"]:
        c = e.get("center") or e
        if "lat" not in c:
            continue
        tags = e.get("tags", {})
        key = (round(c["lon"], 3), round(c["lat"], 3))
        # a site mapped as both a building and its telecom node counts once
        points.setdefault(key, [key[0], key[1], tags.get("name"), tags.get("operator")])
    return sorted(points.values())


def by_country(points: list[list]) -> dict[str, int]:
    """Number of points inside each country's outline (GISCO 1:20M)."""
    if not GISCO.exists():
        return {}
    feats = json.loads(GISCO.read_text(encoding="utf-8"))["features"]
    geoms = [shape(f["geometry"]) for f in feats]
    codes = [f["properties"].get("ISO3_CODE") or "" for f in feats]
    tree = STRtree(geoms)
    counts: dict[str, int] = {}
    for lon, lat, *_ in points:
        pt = Point(lon, lat)
        for i in tree.query(pt):
            if geoms[i].covers(pt) and codes[i]:
                counts[codes[i]] = counts.get(codes[i], 0) + 1
                break
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def clusters(points: list[list], step: float = 1.0) -> list[list]:
    """Sites per 1-degree cell: [lon, lat, count], at the mean position of the cell's sites."""
    cells: dict[tuple[int, int], list] = {}
    for lon, lat, *_ in points:
        c = cells.setdefault((int(lon // step), int(lat // step)), [0.0, 0.0, 0])
        c[0] += lon
        c[1] += lat
        c[2] += 1
    return sorted(
        ([round(x / n, 3), round(y / n, 3), n] for x, y, n in cells.values()), key=lambda c: -c[2]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--skip-osm", action="store_true")
    args = parser.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    fetched = datetime.now(UTC).isoformat(timespec="seconds")
    with httpx.Client(
        timeout=400, headers={"User-Agent": "Europe-InfraAtlas/0.3"}, follow_redirects=True
    ) as client:
        stats = access(client)
        (out / "world_stats.json").write_text(
            json.dumps(
                {
                    "source": "World Bank WDI EG.ELC.ACCS.ZS (CC BY 4.0)",
                    "fetched": fetched,
                    **stats,
                },
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        print(
            f"world_stats.json: access for {len(stats['access'])} countries, {stats['years'][0]}-{stats['years'][-1]}"
        )
        if not args.skip_osm:
            pts = datacentres(client)
            (out / "datacentres.json").write_text(
                json.dumps(
                    {
                        "source": "OpenStreetMap contributors (ODbL), via Overpass: telecom=data_center or building=data_center",
                        "fetched": fetched,
                        "count": len(pts),
                        "by_country": by_country(pts),
                        "clusters": clusters(pts),
                        "points": pts,
                    },
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            print(f"datacentres.json: {len(pts)} mapped sites")


if __name__ == "__main__":
    main()
