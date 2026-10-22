"""Undersea power cables worldwide from OpenStreetMap, for the cables layer.

Overpass (no key; OpenStreetMap contributors, ODbL; scripts/probe_cables.py): ways tagged
power=cable with location=underwater or submarine=yes, about 2,600 worldwide. Each is
put in one class (computed from its tags):
  hvdc   frequency=0 (direct current)
  hv     110 kV or more
  field  below 110 kV, mostly offshore wind farm export and inter-array cables
  other  no voltage tagged
OpenStreetMap splits a cable into many ways; ways of the same class that meet end to end
(a shared end node, no third way there) are joined into one line first (computed; its kV
the highest of its ways, its name the most common), so a cable draws whole. Some ways are
tagged underwater although they run mostly over land (tagging errors), so a joined cable is
kept, whole and with its landfall, only when at least half of its length lies outside the
land outlines (Eurostat GISCO 1:20M; computed). Cables in lakes and
narrow fjords fall inside those outlines and drop out with them. Geometry simplified to
about 500 m (shapely), coordinates to 3 decimals. OpenStreetMap is a
mapped subset: well mapped around Europe, sparse elsewhere.

Writes frontend/public/data/eu/cables.json:
  {"source", "fetched", "count", "cables": [[class, kV | null, name | null, [lon, lat, ...]]]}

    uv run python scripts/fetch_cables.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx
from shapely.geometry import LineString, shape
from shapely.ops import unary_union
from shapely.prepared import prep

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = (
    '[out:json][timeout:300];(way["power"="cable"]["location"="underwater"];'
    'way["power"="cable"]["submarine"="yes"];);out tags geom;'
)
TOLERANCE = 0.005  # degrees, about 500 m
MIN_SEA_SHARE = 0.5  # at least half the length at sea
GISCO = Path(__file__).resolve().parents[1] / "data" / "eu" / "countries.geojson"


def land():
    """All countries' outlines as one shape (Eurostat GISCO 1:20M)."""
    feats = json.loads(GISCO.read_text(encoding="utf-8"))["features"]
    return unary_union([shape(f["geometry"]).buffer(0) for f in feats])


def kilovolts(tag: str | None) -> int | None:
    """Highest voltage of a tag like '400000' or '150000;33000', in kV."""
    if not tag:
        return None
    values = []
    for part in tag.replace(",", ";").split(";"):
        try:
            values.append(int(float(part.strip())) // 1000)
        except ValueError:
            continue
    return max(values) if values else None


Way = tuple[str, int | None, str | None, list[tuple[float, float]]]


def join_ways(ways: list[Way]) -> list[Way]:
    """Ways of one class meeting end to end (exactly two ways at the shared end) become one line."""
    ends: dict[tuple[str, tuple[float, float]], list[int]] = defaultdict(list)
    for i, (cls, _, _, pts) in enumerate(ways):
        ends[(cls, pts[0])].append(i)
        ends[(cls, pts[-1])].append(i)
    used: set[int] = set()
    out: list[Way] = []

    def next_way(cls: str, at: tuple[float, float], came: int) -> int | None:
        here = ends[(cls, at)]
        if len(here) != 2:
            return None
        other = here[0] if here[1] == came else here[1]
        return None if other in used or other == came else other

    for i, (cls, _kv, _name, pts) in enumerate(ways):
        if i in used:
            continue
        used.add(i)
        line = list(pts)
        members = [i]
        for forward in (True, False):
            came = i
            while True:
                at = line[-1] if forward else line[0]
                j = next_way(cls, at, came)
                if j is None:
                    break
                used.add(j)
                members.append(j)
                seg = ways[j][3]
                # orient the next way so it continues from `at`
                if forward:
                    seg = seg if seg[0] == at else seg[::-1]
                    line.extend(seg[1:])
                else:
                    seg = seg if seg[-1] == at else seg[::-1]
                    line[:0] = seg[:-1]
                came = j
        kvs = [ways[m][1] for m in members if ways[m][1] is not None]
        names = Counter(ways[m][2] for m in members if ways[m][2])
        out.append(
            (cls, max(kvs) if kvs else None, names.most_common(1)[0][0] if names else None, line)
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out: Path = parser.parse_args().out
    with httpx.Client(timeout=400, headers={"User-Agent": "Europe-InfraAtlas/0.3"}) as client:
        for attempt in range(5):
            try:
                r = client.post(OVERPASS, data={"data": QUERY})
            except httpx.TransportError:
                time.sleep(30 * (attempt + 1))
                continue
            if r.status_code == 200 and r.content.lstrip().startswith(b"{"):
                break
            print(f"  Overpass HTTP {r.status_code}, waiting", flush=True)
            time.sleep(60 * (attempt + 1))
        else:
            raise RuntimeError("Overpass: no answer")
    ground = land()
    on_land = prep(ground)
    ways = []
    for e in r.json()["elements"]:
        pts = [(p["lon"], p["lat"]) for p in e.get("geometry", [])]
        if len(pts) < 2:
            continue
        tags = e.get("tags", {})
        kv = kilovolts(tags.get("voltage"))
        cls = (
            "hvdc"
            if tags.get("frequency") == "0"
            else "hv"
            if kv and kv >= 110
            else "field"
            if kv
            else "other"
        )
        ways.append((cls, kv, tags.get("name"), pts))
    joined = join_ways(ways)
    cables = []
    for cls, kv, name, pts in joined:
        line = LineString(pts)
        if line.length == 0:
            continue
        # mostly at sea: keep it whole, landfall included; mostly on land: a tagging error
        at_sea = line.difference(ground).length if on_land.intersects(line) else line.length
        if at_sea / line.length < MIN_SEA_SHARE:
            continue
        simple = line.simplify(TOLERANCE, preserve_topology=False)
        flat = [round(v, 3) for xy in simple.coords for v in xy]
        cables.append([cls, kv, name, flat])
    print(f"{len(ways)} ways joined into {len(joined)} lines", flush=True)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "cables.json"
    path.write_text(
        json.dumps(
            {
                "source": "OpenStreetMap contributors (ODbL), via Overpass: power=cable underwater",
                "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
                "count": len(cables),
                "cables": cables,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(
        f"cables.json: {len(cables)} cables, {path.stat().st_size / 1e3:.0f} kB, {dict(Counter(c[0] for c in cables))}"
    )


if __name__ == "__main__":
    main()
