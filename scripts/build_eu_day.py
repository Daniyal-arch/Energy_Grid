"""One full day of European electricity, every 15 minutes, for the time-lapse (?europe&day=).

Asks Energy-Charts (Fraunhofer ISE; ENTSO-E data) for a whole local day (Central European
time, midnight to midnight), one request at a time because the API answers 429 to bursts:
  /price?bzn=zone         day-ahead price per bidding zone
  /public_power?country   load, generation by source group, published renewable share
  /public_power?country=eu  the EU aggregate (hourly)
  /cbpf?country           physical cross-border flows per neighbour

Values are passthrough, aligned to the day's 15-min slots (null where a source has no
value); generation is grouped by fuel like the snapshot (e.g. wind onshore + offshore).
Each border is taken from the first country that reports it (sign flipped as needed).

Writes frontend/public/data/eu/day/<YYYY-MM-DD>.json and updates day/index.json:
  {"date", "timezone", "start", "step_s", "slots",
   "prices": {zone: {"country", "values": [EUR/MWh]}},
   "countries": {ISO: {"load": [MW], "renewable_share": [%], "generation": {group: [MW]}}},
   "eu": {"step_s": 3600, "load": [...], "renewable_share": [...], "generation": {...}},
   "borders": [{"a", "b", "values": [MW, a -> b positive]}],
   "highlights": [...]}  (key moments, scripts/day_highlights.py)

    uv run python scripts/build_eu_day.py 2026-10-02      # one day
    uv run python scripts/build_eu_day.py --recent 30    # rolling 30-day archive
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from day_highlights import highlights  # noqa: E402
from fetch_eu_snapshot import (  # noqa: E402
    CODES,
    FUEL_GROUP,
    NAME_TO_ISO,
    PRICE_ZONES,
    SOURCE,
    get,
)

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu" / "day"
TZ = ZoneInfo("Europe/Berlin")  # CET/CEST, the market's own clock
STEP = 900


def day_window(day: date) -> tuple[datetime, int]:
    """UTC start of the local day and its number of 15-min slots (92/96/100 with DST)."""
    start = datetime(day.year, day.month, day.day, tzinfo=TZ).astimezone(UTC)
    nxt = day + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=TZ).astimezone(UTC)
    return start, int((end - start).total_seconds()) // STEP


def align(seconds: list[int], values: list, start: int, slots: int, scale: float = 1.0) -> list:
    """Values on the day's 15-min grid; coarser series (hourly) fill each slot they cover."""
    out: list[float | None] = [None] * slots
    step = (seconds[1] - seconds[0]) if len(seconds) > 1 else STEP
    for sec, v in zip(seconds, values, strict=False):
        if v is None:
            continue
        first = (int(sec) - start) // STEP
        for k in range(first, first + max(1, step // STEP)):
            if 0 <= k < slots:
                out[k] = round(float(v) * scale, 1)
    return out


def power_series(data: dict, start: int, slots: int) -> dict:
    seconds = data.get("unix_seconds", [])
    series = {s["name"]: s.get("data", []) for s in data.get("production_types", [])}
    generation: dict[str, list] = {}
    for name, col in series.items():
        group = FUEL_GROUP.get(name)
        if not group or not any(v is not None for v in col):
            continue
        aligned = align(seconds, col, start, slots)
        if group in generation:
            generation[group] = [
                None if a is None and b is None else round((a or 0) + (b or 0), 1)
                for a, b in zip(generation[group], aligned, strict=True)
            ]
        else:
            generation[group] = aligned
    return {
        "load": align(seconds, series.get("Load", []), start, slots),
        "renewable_share": align(
            seconds, series.get("Renewable share of generation", []), start, slots
        ),
        "generation": dict(sorted(generation.items())),
    }


def fetch_window(first: date, last: date) -> dict:
    """Every source for the local days first..last in one pass (one request per series).

    Asking once for the whole window keeps a 30-day backfill as cheap as a single day
    (~110 requests, paced for Energy-Charts' rate limit).
    """
    start_dt, _ = day_window(first)
    end_start, end_slots = day_window(last)
    end_dt = end_start + timedelta(seconds=STEP * end_slots - 60)
    window = {
        "start": start_dt.strftime("%Y-%m-%dT%H:%MZ"),
        "end": end_dt.strftime("%Y-%m-%dT%H:%MZ"),
    }
    raw: dict = {"eu": None, "prices": {}, "power": {}, "cbpf": {}}
    with httpx.Client(timeout=180, headers={"User-Agent": "Germany-InfraAtlas/0.1"}) as client:
        raw["eu"] = get(client, "/public_power", "eu", **window)
        time.sleep(3)
        for zone in PRICE_ZONES:
            raw["prices"][zone] = get(client, "/price", bzn=zone, **window)
            time.sleep(3)
        print(f"prices: {sum(1 for v in raw['prices'].values() if v)} zones", flush=True)
        for code in CODES:
            raw["power"][code] = get(client, "/public_power", code, **window)
            time.sleep(3)
            raw["cbpf"][code] = get(client, "/cbpf", code, **window)
            time.sleep(3)
            print(f"{code.upper()}: power {'ok' if raw['power'][code] else '-'}", flush=True)
    return raw


def day_payload(day: date, raw: dict) -> dict:
    """One local day cut from the fetched window, on its own 15-min grid."""
    start_dt, slots = day_window(day)
    start = int(start_dt.timestamp())
    prices: dict[str, dict] = {}
    for zone, iso in PRICE_ZONES.items():
        data = raw["prices"].get(zone)
        if data:
            prices[zone] = {
                "country": iso,
                "values": align(data["unix_seconds"], data["price"], start, slots),
            }
    countries = {
        code.upper(): power_series(data, start, slots)
        for code, data in raw["power"].items()
        if data
    }
    borders: dict[frozenset[str], dict] = {}
    for code, data in raw["cbpf"].items():
        if not data:
            continue
        home = code.upper()
        for s in data.get("countries", []):
            other = NAME_TO_ISO.get(s.get("name"))
            if not other or frozenset((home, other)) in borders:
                continue
            # Energy-Charts: positive = import into the asked country (other -> home)
            borders[frozenset((home, other))] = {
                "a": other,
                "b": home,
                "values": align(data["unix_seconds"], s["data"], start, slots, scale=1000.0),
            }
    payload = {
        "source": SOURCE,
        "date": day.isoformat(),
        "timezone": "Europe/Berlin",
        "start": start_dt.isoformat(),
        "step_s": STEP,
        "slots": slots,
        "prices": prices,
        "countries": countries,
        "eu": power_series(raw["eu"], start, slots) if raw["eu"] else None,
        "borders": list(borders.values()),
    }
    payload["highlights"] = highlights(payload)
    return payload


def write_index(out: Path) -> list[str]:
    days = sorted(p.stem for p in out.glob("20*.json"))
    (out / "index.json").write_text(json.dumps({"days": days}), encoding="utf-8")
    return days


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("day", nargs="?", help="one local day, YYYY-MM-DD (must be complete)")
    parser.add_argument(
        "--recent",
        type=int,
        default=0,
        help="keep the last N complete days: build missing ones, delete older ones",
    )
    parser.add_argument(
        "--refresh",
        type=int,
        default=2,
        help="with --recent: always rebuild the newest N days (late corrections)",
    )
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    if args.recent:
        yesterday = datetime.now(TZ).date() - timedelta(days=1)
        wanted = [yesterday - timedelta(days=i) for i in range(args.recent)]
        have = {p.stem for p in args.out.glob("20*.json")}
        todo = sorted(
            d for i, d in enumerate(wanted) if i < args.refresh or d.isoformat() not in have
        )
        for stale in have - {d.isoformat() for d in wanted}:
            (args.out / f"{stale}.json").unlink()
            print(f"removed {stale}")
    elif args.day:
        todo = [date.fromisoformat(args.day)]
    else:
        parser.error("give a day or --recent N")

    if todo:
        raw = fetch_window(todo[0], todo[-1])
        for day in todo:
            payload = day_payload(day, raw)
            path = args.out / f"{day.isoformat()}.json"
            path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            missing = sum(v is None for z in payload["prices"].values() for v in z["values"])
            print(
                f"{path.name} ({path.stat().st_size / 1e6:.2f} MB): {payload['slots']} slots, "
                f"{len(payload['prices'])} price zones ({missing} empty slots), "
                f"{len(payload['countries'])} countries, {len(payload['borders'])} borders",
                flush=True,
            )
    days = write_index(args.out)
    print(f"index: {len(days)} days, {days[0] if days else '-'} .. {days[-1] if days else '-'}")


if __name__ == "__main__":
    main()
