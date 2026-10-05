"""Twelve months of day-ahead prices per bidding zone, for the Prices tab.

ENTSO-E (scripts/entsoe.py; ENTSOE_API_KEY), from the first day of the month twelve
months back until yesterday:
  A44  day-ahead price per zone (15 min since the market moved to 15-min products on
       1 October 2025; hourly zones fill the four quarters of each hour)
  A75  actual solar (B16) and wind (B18 offshore + B19 onshore) generation per zone,
       to weight prices for capture prices

Computed here (documented in docs/DATA_SOURCES.md), over the last twelve full calendar
months only:
  mean            average of the 15-min prices (time-weighted)
  negative_hours  15-min intervals with a price below zero, x 0.25 h; also per month
  min / max       lowest and highest price, with its interval
  solar_capture   sum(price x solar MW) / sum(solar MW): what a MWh of solar earned on
                  average; capture rate = solar_capture / mean. Same for wind.

Writes frontend/public/data/eu/:
  prices.json            {"source", "fetched", "period": [first, last], "months": [...],
                          "zones": {zone: {"country", "mean", "negative_hours",
                          "negative_by_month", "min", "max", "solar_capture",
                          "solar_capture_rate", "solar_twh", "wind_capture",
                          "wind_capture_rate", "wind_twh"}}}
  prices/<zone>.json     {"zone", "days": [YYYY-MM-DD], "values": [[96 x price x 10]]}
                         every 15 minutes of each local day (Europe/Berlin), rounded to
                         0.1 EUR/MWh; null where there is no price (and in the hour the
                         clocks skip)

    uv run python scripts/build_prices.py [--out DIR]
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


def window() -> tuple[date, date, date]:
    """First day (1st of the month 12 months back), last full-month day, yesterday."""
    today = datetime.now(TZ).date()
    first = date(today.year - 1, today.month, 1)
    month_start = date(today.year, today.month, 1)
    return first, month_start - timedelta(days=1), today - timedelta(days=1)


def capture(prices: list, gen: list | None, last: int) -> tuple[float | None, float | None]:
    """Generation-weighted average price and the energy (TWh) behind it."""
    if gen is None:
        return None, None
    num = den = 0.0
    for k in range(last):
        p, g = prices[k], gen[k]
        if p is None or g is None or g <= 0:
            continue
        num += p * g
        den += g
    if den <= 0:
        return None, None
    return num / den, den * STEP_H / 1e6


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out: Path = parser.parse_args().out
    first, last_full, yesterday = window()
    start, _ = day_window(first)
    end_start, end_slots = day_window(yesterday)
    grid = entsoe.Grid(start, end_start + timedelta(minutes=15 * end_slots))
    full_start, full_slots = day_window(last_full)
    stats_end = (int(full_start.timestamp()) + 900 * full_slots - grid.start) // 900
    print(
        f"{first} .. {yesterday} ({grid.slots} slots); statistics {first} .. {last_full}",
        flush=True,
    )

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
    months = sorted({d.strftime("%Y-%m") for d in local[:stats_end]})
    zones: dict[str, dict] = {}
    (out / "prices").mkdir(parents=True, exist_ok=True)
    for zone, iso in PRICE_ZONES.items():
        data = got.get(f"price:{zone}")
        if not isinstance(data, dict):
            print(f"{zone}: no prices")
            continue
        values: list = data["price"]
        known = [(k, v) for k, v in enumerate(values[:stats_end]) if v is not None]
        if not known:
            continue
        negative = {m: 0.0 for m in months}
        for k, v in known:
            if v < 0:
                negative[local[k].strftime("%Y-%m")] += STEP_H
        lo = min(known, key=lambda kv: kv[1])
        hi = max(known, key=lambda kv: kv[1])
        mean = sum(v for _, v in known) / len(known)
        solar = got.get(f"solar:{zone}")
        wind = got.get(f"wind:{zone}")
        s_cap, s_twh = capture(values, solar if isinstance(solar, list) else None, stats_end)
        w_cap, w_twh = capture(values, wind if isinstance(wind, list) else None, stats_end)

        def stamp(k: int) -> str:
            return datetime.fromtimestamp(seconds[k], tz=UTC).isoformat()

        zones[zone] = {
            "country": iso,
            "mean": round(mean, 2),
            "negative_hours": round(sum(negative.values()), 2),
            "negative_by_month": [round(negative[m], 2) for m in months],
            "min": [round(lo[1], 2), stamp(lo[0])],
            "max": [round(hi[1], 2), stamp(hi[0])],
            "coverage": round(len(known) / stats_end, 3),
            "solar_capture": round(s_cap, 2) if s_cap is not None else None,
            "solar_capture_rate": round(100 * s_cap / mean, 1)
            if s_cap is not None and mean > 0
            else None,
            "solar_twh": round(s_twh, 2) if s_twh is not None else None,
            "wind_capture": round(w_cap, 2) if w_cap is not None else None,
            "wind_capture_rate": round(100 * w_cap / mean, 1)
            if w_cap is not None and mean > 0
            else None,
            "wind_twh": round(w_twh, 2) if w_twh is not None else None,
        }
        # the carpet: one row per local day, 96 quarter-hours of local clock time
        days: dict[str, list] = {}
        for k, v in enumerate(values):
            d = local[k]
            row = days.setdefault(d.date().isoformat(), [None] * 96)
            q = d.hour * 4 + d.minute // 15
            if row[q] is None and v is not None:  # the repeated autumn hour: first one kept
                row[q] = round(v * 10)
        names = sorted(days)
        (out / "prices" / f"{zone}.json").write_text(
            json.dumps(
                {"zone": zone, "country": iso, "days": names, "values": [days[n] for n in names]},
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        z = zones[zone]
        print(
            f"{zone:16} mean {z['mean']:7.1f}  negative {z['negative_hours']:7.1f} h  "
            f"solar {z['solar_capture_rate']}%  wind {z['wind_capture_rate']}%",
            flush=True,
        )
    payload = {
        "source": "ENTSO-E Transparency Platform: A44 day-ahead prices, A75 solar and wind generation",
        "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
        "period": [first.isoformat(), last_full.isoformat()],
        "carpet_until": yesterday.isoformat(),
        "months": months,
        "zones": zones,
    }
    (out / "prices.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    size = sum(f.stat().st_size for f in (out / "prices").glob("*.json")) / 1e6
    print(f"prices.json: {len(zones)} zones; prices/: {size:.1f} MB")


if __name__ == "__main__":
    main()
