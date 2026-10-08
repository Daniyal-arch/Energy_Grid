"""Wind at 100 m and sunshine over the whole world, every 3 hours (ECMWF open data).

ECMWF publishes its IFS forecast at 0.25° four times a day (no key; scripts/probe_ecmwf.py).
Only three fields per step are fetched, with HTTP range requests from each step's .index:
100u and 100v (wind at 100 m, m/s) and ssrd (surface solar radiation downwards,
accumulated J/m² since the run started).

The file is the newest run whose first 27 hours are published, on a 2° grid from 80° S
to 80° N: the 0.25° grid points that fall on it, as published (no averaging).
Computed per point and step, documented in docs/DATA_SOURCES.md:
  speed  = sqrt(u² + v²), 0.1 m/s
  dir    = where the wind blows from, degrees (meteorological convention)
  ghi    = (ssrd[step] - ssrd[step - 3 h]) / 10800 s: the average W/m² of the 3 hours
           before the step
Steps 3 to 27 h (9 times, every 3 h). Same shape as wind.json (lib/windParticles.ts).

Writes frontend/public/data/eu/wind_world.json:
  {"source", "fetched", "run", "grid": {"lon0", "lat0", "step", "nx", "ny"}, "start",
   "step_s": 10800, "speed": [[...]], "dir": [[...]], "ghi": [[...]]}

    uv run python scripts/fetch_ecmwf.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import eccodes
import httpx

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
BASE = "https://data.ecmwf.int/forecasts"
SOURCE = "ECMWF open data, IFS 0.25° (CC BY 4.0): wind at 100 m, surface solar radiation"
STEPS = list(range(3, 28, 3))
COARSE = 2.0  # degrees between the points kept
LAT_MAX = 80.0
FINE = 0.25


def runs(client: httpx.Client) -> list[tuple[str, str]]:
    days = sorted(set(re.findall(r'href="/forecasts/(\d{8})/"', client.get(f"{BASE}/").text)))
    return [(d, r) for d in reversed(days) for r in ("18", "12", "06", "00")]


def stem(day: str, run: str, step: int) -> str:
    return f"{BASE}/{day}/{run}z/ifs/0p25/oper/{day}{run}0000-{step}h-oper-fc"


def newest_complete(client: httpx.Client) -> tuple[str, str]:
    for day, run in runs(client):
        if client.head(f"{stem(day, run, STEPS[-1])}.index").status_code == 200:
            return day, run
    raise SystemExit("no complete ECMWF run found")


def field(client: httpx.Client, day: str, run: str, step: int, param: str) -> list[float]:
    """One 0.25° field (north to south, west to east from 180°) as published."""
    index = [
        json.loads(x)
        for x in client.get(f"{stem(day, run, step)}.index").text.splitlines()
        if x.strip()
    ]
    hit = next(x for x in index if x["param"] == param)
    lo, n = hit["_offset"], hit["_length"]
    r = client.get(f"{stem(day, run, step)}.grib2", headers={"Range": f"bytes={lo}-{lo + n - 1}"})
    r.raise_for_status()
    gid = eccodes.codes_new_from_message(r.content)
    try:
        assert eccodes.codes_get(gid, "Ni") == 1440 and eccodes.codes_get(gid, "Nj") == 721
        return list(eccodes.codes_get_values(gid))
    finally:
        eccodes.codes_release(gid)


def coarse_points() -> tuple[dict, list[int]]:
    """The 2° grid (south-west first, row by row) and each point's index in the 0.25° field.
    The last column repeats the first (180° = -180°) so the field wraps around."""
    nx = int(360 / COARSE) + 1
    ny = int(2 * LAT_MAX / COARSE) + 1
    idx = []
    for r in range(ny):
        lat = -LAT_MAX + r * COARSE
        j = round((90.0 - lat) / FINE)
        for c in range(nx):
            lon = -180.0 + c * COARSE
            i = round((lon + 180.0) / FINE) % 1440  # the field starts at 180° = -180°
            idx.append(j * 1440 + i)
    return {"lon0": -180.0, "lat0": -LAT_MAX, "step": COARSE, "nx": nx, "ny": ny}, idx


def build(client: httpx.Client) -> dict:
    day, run = newest_complete(client)
    grid, idx = coarse_points()
    speed, direction, ghi = [], [], []
    prev = [0.0] * len(idx)  # the accumulation starts at 0 when the run starts
    for step in STEPS:
        u = field(client, day, run, step, "100u")
        v = field(client, day, run, step, "100v")
        acc = field(client, day, run, step, "ssrd")
        now = [acc[k] for k in idx]
        speed.append([round(10 * math.hypot(u[k], v[k])) for k in idx])
        direction.append([round(math.degrees(math.atan2(-u[k], -v[k]))) % 360 for k in idx])
        ghi.append([max(0, round((a - b) / 10800)) for a, b in zip(now, prev, strict=True)])
        prev = now
        print(f"  {day} {run}z +{step} h", flush=True)
    start = datetime.strptime(f"{day}{run}", "%Y%m%d%H").replace(tzinfo=UTC) + timedelta(
        hours=STEPS[0]
    )
    return {
        "source": SOURCE,
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "run": f"{day}T{run}:00Z",
        "grid": grid,
        "start": start.strftime("%Y-%m-%dT%H:%M:00Z"),
        "step_s": 10800,
        "speed": speed,
        "dir": direction,
        "ghi": ghi,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out: Path = parser.parse_args().out
    path = out / "wind_world.json"
    with httpx.Client(timeout=120, headers={"User-Agent": "Europe-InfraAtlas/0.3"}) as client:
        day, run = newest_complete(client)
        if (
            path.exists()
            and json.loads(path.read_text(encoding="utf-8")).get("run") == f"{day}T{run}:00Z"
        ):
            print(f"{path.name}: run {day} {run}z already built", flush=True)
            return
        data = build(client)
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(
        f"{path.name}: {path.stat().st_size / 1e6:.2f} MB, run {data['run']}, {len(data['speed'])} steps from {data['start']}"
    )


if __name__ == "__main__":
    main()
