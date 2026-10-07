"""Undersea power cables worldwide from OpenStreetMap, for the cables layer.

Overpass (no key; OpenStreetMap contributors, ODbL; scripts/probe_cables.py): ways tagged
power=cable with location=underwater or submarine=yes, about 2,600 worldwide. Each is
put in one class (computed from its tags):
  hvdc   frequency=0 (direct current)
  hv     110 kV or more
  field  below 110 kV, mostly offshore wind farm export and inter-array cables
  other  no voltage tagged
Geometry simplified to about 500 m (shapely), coordinates to 3 decimals. OpenStreetMap
is a mapped subset: well mapped around Europe, sparse elsewhere.

Writes frontend/public/data/eu/cables.json:
  {"source", "fetched", "count", "cables": [[class, kV | null, name | null, [lon, lat, ...]]]}

    uv run python scripts/fetch_cables.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx
from shapely.geometry import LineString

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = (
    '[out:json][timeout:300];(way["power"="cable"]["location"="underwater"];'
    'way["power"="cable"]["submarine"="yes"];);out tags geom;'
)
TOLERANCE = 0.005  # degrees, about 500 m


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
    cables = []
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
        line = LineString(pts).simplify(TOLERANCE, preserve_topology=False)
        flat = [round(v, 3) for xy in line.coords for v in xy]
        cables.append([cls, kv, tags.get("name"), flat])
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
