"""Wind at 100 m (wind-turbine hub height), sunshine and clouds over Europe, hourly, for
the wind and sun layers.

Open-Meteo forecast API (no key; data CC BY 4.0; free for non-commercial use): hourly
`wind_speed_100m` and `wind_direction_100m` from its best-match weather models, on a
2-degree grid over lon -25..45, lat 34..72 (36 x 20 = 720 points). Open-Meteo counts one
call per location and allows 600 a minute, so the grid goes in two batches a minute
apart (scripts/probe_open_meteo_wind.py). These are model values, not measurements.

  --live            the last 6 hours and the next 24 -> wind.json (the live map)
  --recent N        the last N complete local days (Europe/Berlin), one pass over the
                    window -> wind/<YYYY-MM-DD>.json next to the day archive

Values are passthrough, one list per hour, points row by row from the south-west corner:
  speed  wind speed at 100 m, 0.1 m/s (integers)
  dir    wind direction at 100 m, degrees (where the wind blows from)
  ghi    shortwave (global horizontal) radiation, W/m2, average of the preceding hour
  cloud  total cloud cover, %
  {"source", "fetched", "grid": {"lon0", "lat0", "step", "nx", "ny"}, "start", "step_s",
   "speed": [[...]], "dir": [[...]], "ghi": [[...]], "cloud": [[...]]}

    uv run python scripts/fetch_wind.py --live [--out DIR]
    uv run python scripts/fetch_wind.py --recent 30 --out DIR/wind
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_eu_day import TZ, day_window  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
URL = "https://api.open-meteo.com/v1/forecast"
SOURCE = "Open-Meteo forecast API (best-match models): wind at 100 m, radiation, clouds; CC BY 4.0"
GRID = {"lon0": -25.0, "lat0": 34.0, "step": 2.0, "nx": 36, "ny": 20}
BATCH = 360  # points per request: two batches a minute apart stay under 600 calls/min
# Open-Meteo variable -> key in the file, scale to integers
VARIABLES = {
    "wind_speed_100m": ("speed", 10),
    "wind_direction_100m": ("dir", 1),
    "shortwave_radiation": ("ghi", 1),
    "cloud_cover": ("cloud", 1),
}


def points() -> tuple[list[float], list[float]]:
    lats, lons = [], []
    for j in range(GRID["ny"]):
        for i in range(GRID["nx"]):
            lats.append(GRID["lat0"] + j * GRID["step"])
            lons.append(GRID["lon0"] + i * GRID["step"])
    return lats, lons


def fetch(client: httpx.Client, params: dict[str, str]) -> tuple[list[str], dict[str, list[list]]]:
    """Hourly times (UTC) and, per variable, one list per point."""
    lats, lons = points()
    values: dict[str, list[list]] = {v: [] for v in VARIABLES}
    times: list[str] = []
    for n, k in enumerate(range(0, len(lats), BATCH)):
        if n:
            time.sleep(62)  # the per-minute allowance
        query = {
            "latitude": ",".join(f"{v:g}" for v in lats[k : k + BATCH]),
            "longitude": ",".join(f"{v:g}" for v in lons[k : k + BATCH]),
            "hourly": ",".join(VARIABLES),
            "wind_speed_unit": "ms",
            "timezone": "GMT",
            **params,
        }
        for attempt in range(5):
            r = client.get(URL, params=query)
            if r.status_code == 429 or r.status_code >= 500:
                print(f"  HTTP {r.status_code}, waiting", flush=True)
                time.sleep(65 * (attempt + 1))
                continue
            r.raise_for_status()
            break
        else:
            raise RuntimeError("Open-Meteo: no answer")
        rows = r.json()
        rows = rows if isinstance(rows, list) else [rows]
        for row in rows:
            h = row["hourly"]
            times = h["time"]
            for v in VARIABLES:
                values[v].append(h[v])
        print(f"  {len(values['wind_speed_100m'])} of {len(lats)} points", flush=True)
    return times, values


def payload(times: list[str], values: dict[str, list[list]], first: int, hours: int) -> dict:
    """Hours first..first+hours as one list per hour (points in grid order)."""

    def col(rows: list[list], h: int, scale: float) -> list[int | None]:
        return [None if r[h] is None else round(r[h] * scale) for r in rows]

    return {
        "source": SOURCE,
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "grid": GRID,
        "start": f"{times[first]}:00Z",
        "step_s": 3600,
        **{
            key: [col(values[v], h, scale) for h in range(first, first + hours)]
            for v, (key, scale) in VARIABLES.items()
        },
    }


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(
        f"{path.name}: {path.stat().st_size / 1e3:.0f} kB, {len(data['speed'])} hours from {data['start']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--recent", type=int, default=0)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    with httpx.Client(timeout=180, headers={"User-Agent": "Europe-InfraAtlas/0.3"}) as client:
        if args.live:
            now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
            times, values = fetch(client, {"past_days": "1", "forecast_days": "2"})
            first = times.index((now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M"))
            write((args.out or OUT) / "wind.json", payload(times, values, first, 30))
        if args.recent:
            out: Path = args.out or OUT / "wind"
            yesterday = datetime.now(TZ).date() - timedelta(days=1)
            wanted = [yesterday - timedelta(days=i) for i in range(args.recent)]
            # a day file from before the sun layer counts as missing
            have = {
                p.stem
                for p in out.glob("20*.json")
                if '"ghi"' in p.read_text(encoding="utf-8")[:200000]
            }
            # rebuild the newest two days (model runs settle), fetch missing ones
            todo = sorted(d for i, d in enumerate(wanted) if i < 2 or d.isoformat() not in have)
            for stale in {p.stem for p in out.glob("20*.json")} - {d.isoformat() for d in wanted}:
                (out / f"{stale}.json").unlink()
            if not todo:
                return
            first_utc, _ = day_window(todo[0])
            last_start, last_slots = day_window(todo[-1])
            last_utc = last_start + timedelta(minutes=15 * last_slots)
            times, values = fetch(
                client,
                {
                    "start_date": first_utc.date().isoformat(),
                    "end_date": last_utc.date().isoformat(),
                },
            )
            index = {t: k for k, t in enumerate(times)}
            for day in todo:
                start, slots = day_window(day)
                k = index.get(start.strftime("%Y-%m-%dT%H:%M"))
                if k is None or k + slots // 4 > len(times):
                    print(f"{day}: not covered")
                    continue
                write(out / f"{day.isoformat()}.json", payload(times, values, k, slots // 4))


if __name__ == "__main__":
    main()
