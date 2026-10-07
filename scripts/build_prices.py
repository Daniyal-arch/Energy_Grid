"""Twelve months of day-ahead prices per bidding zone, for the Prices tab.

ENTSO-E (scripts/entsoe.py; ENTSOE_API_KEY), over the last twelve full calendar months:
  A44  day-ahead price per zone (15 min since the market moved to 15-min products on
       1 October 2025; hourly zones fill the four quarters of each hour)
  A75  actual solar (B16) and wind (B18 offshore + B19 onshore) generation per zone,
       to weight prices for capture prices

Computed here (documented in docs/DATA_SOURCES.md):
  mean            average of the 15-min prices (time-weighted)
  negative_hours  15-min intervals with a price below zero, x 0.25 h; also per month
  min / max       lowest and highest price, with its interval
  solar_capture   sum(price x solar MW) / sum(solar MW): what a MWh of solar earned on
                  average; capture rate = solar_capture / mean. Same for wind.
  by_month_hour   average price per local hour of the day (CET/CEST), per month
  by_season_hour  the same per season (winter Dec-Feb, spring Mar-May, summer Jun-Aug,
                  autumn Sep-Nov)

Writes frontend/public/data/eu/prices.json:
  {"source", "fetched", "period": [first, last], "months": [...], "seasons": {...},
   "zones": {zone: {"country", "mean", "negative_hours", "negative_by_month", "min",
   "max", "coverage", "solar_capture", "solar_capture_rate", "solar_twh",
   "wind_capture", "wind_capture_rate", "wind_twh", "by_month_hour": [[24]],
   "by_season_hour": {season: [24]}}}}
Skips the work when prices.json already covers the newest twelve full months
(--force rebuilds).

    uv run python scripts/build_prices.py [--out DIR] [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entsoe  # noqa: E402
from build_eu_day import TZ, day_window  # noqa: E402
from fetch_eu_snapshot import PRICE_ZONES, USER_AGENT  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
STEP_H = 0.25
SEASON = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
          6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}  # fmt: skip


def window() -> tuple[date, date]:
    """The last twelve full calendar months (local days)."""
    today = datetime.now(TZ).date()
    first = date(today.year - 1, today.month, 1)
    return first, date(today.year, today.month, 1) - timedelta(days=1)


def capture(prices: list, gen: list | None) -> tuple[float | None, float | None]:
    """Generation-weighted average price and the energy (TWh) behind it."""
    if gen is None:
        return None, None
    num = den = 0.0
    for p, g in zip(prices, gen, strict=False):
        if p is None or g is None or g <= 0:
            continue
        num += p * g
        den += g
    if den <= 0:
        return None, None
    return num / den, den * STEP_H / 1e6


def profile(values: list, keys: list[str], hours: list[int]) -> dict[str, list]:
    """Average price per key (month or season) and local hour of the day."""
    sums: dict[str, list[float]] = {}
    counts: dict[str, list[int]] = {}
    for v, key, h in zip(values, keys, hours, strict=False):
        if v is None:
            continue
        sums.setdefault(key, [0.0] * 24)[h] += v
        counts.setdefault(key, [0] * 24)[h] += 1
    return {
        key: [
            round(sums[key][h] / counts[key][h], 1) if counts[key][h] else None for h in range(24)
        ]
        for key in sums
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    out: Path = args.out
    first, last = window()
    done = out / "prices.json"
    if not args.force and done.exists():
        period = json.loads(done.read_text(encoding="utf-8")).get("period")
        if period == [first.isoformat(), last.isoformat()]:
            print(f"prices.json already covers {first} .. {last}")
            return
    start, _ = day_window(first)
    end_start, end_slots = day_window(last)
    grid = entsoe.Grid(start, end_start + timedelta(minutes=15 * end_slots))
    print(f"{first} .. {last} ({grid.slots} slots)", flush=True)

    with httpx.Client(timeout=600, headers=USER_AGENT) as client:
        got = entsoe.run(
            [(f"price:{z}", lambda z=z: entsoe.price(client, z, grid)) for z in PRICE_ZONES]
            + [
                (f"solar:{z}", lambda z=z: entsoe.zone_generation(client, z, ["B16"], grid))
                for z in PRICE_ZONES
            ]
            + [
                (f"wind:{z}", lambda z=z: entsoe.zone_generation(client, z, ["B18", "B19"], grid))
                for z in PRICE_ZONES
            ]
        )

    seconds = grid.seconds()
    local = [datetime.fromtimestamp(sec, tz=UTC).astimezone(TZ) for sec in seconds]
    months = sorted({d.strftime("%Y-%m") for d in local})
    month_of = [d.strftime("%Y-%m") for d in local]
    season_of = [SEASON[d.month] for d in local]
    hour_of = [d.hour for d in local]
    seasons = {
        name: [m for m in months if SEASON[int(m[5:])] == name]
        for name in ("winter", "spring", "summer", "autumn")
    }
    zones: dict[str, dict] = {}
    for zone, iso in PRICE_ZONES.items():
        data = got.get(f"price:{zone}")
        if not isinstance(data, dict):
            print(f"{zone}: no prices")
            continue
        values: list = data["price"]
        known = [(k, v) for k, v in enumerate(values) if v is not None]
        if not known:
            continue
        negative = {m: 0.0 for m in months}
        for k, v in known:
            if v < 0:
                negative[month_of[k]] += STEP_H
        lo = min(known, key=lambda kv: kv[1])
        hi = max(known, key=lambda kv: kv[1])
        mean = sum(v for _, v in known) / len(known)
        solar = got.get(f"solar:{zone}")
        wind = got.get(f"wind:{zone}")
        s_cap, s_twh = capture(values, solar if isinstance(solar, list) else None)
        w_cap, w_twh = capture(values, wind if isinstance(wind, list) else None)

        def stamp(k: int) -> str:
            return datetime.fromtimestamp(seconds[k], tz=UTC).isoformat()

        def rate(cap: float | None) -> float | None:
            return round(100 * cap / mean, 1) if cap is not None and mean > 0 else None

        by_month = profile(values, month_of, hour_of)
        zones[zone] = {
            "country": iso,
            "mean": round(mean, 2),
            "negative_hours": round(sum(negative.values()), 2),
            "negative_by_month": [round(negative[m], 2) for m in months],
            "min": [round(lo[1], 2), stamp(lo[0])],
            "max": [round(hi[1], 2), stamp(hi[0])],
            "coverage": round(len(known) / grid.slots, 3),
            "solar_capture": round(s_cap, 2) if s_cap is not None else None,
            "solar_capture_rate": rate(s_cap),
            "solar_twh": round(s_twh, 2) if s_twh is not None else None,
            "wind_capture": round(w_cap, 2) if w_cap is not None else None,
            "wind_capture_rate": rate(w_cap),
            "wind_twh": round(w_twh, 2) if w_twh is not None else None,
            "by_month_hour": [by_month.get(m, [None] * 24) for m in months],
            "by_season_hour": profile(values, season_of, hour_of),
        }
        z = zones[zone]
        print(
            f"{zone:16} mean {z['mean']:7.1f}  negative {z['negative_hours']:7.1f} h  "
            f"solar {z['solar_capture_rate']}%  wind {z['wind_capture_rate']}%",
            flush=True,
        )
    payload = {
        "source": "ENTSO-E Transparency Platform: A44 day-ahead prices, A75 solar and wind generation",
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "period": [first.isoformat(), last.isoformat()],
        "months": months,
        "seasons": seasons,
        "zones": zones,
    }
    out.mkdir(parents=True, exist_ok=True)
    done.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"prices.json: {len(zones)} zones, {done.stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
