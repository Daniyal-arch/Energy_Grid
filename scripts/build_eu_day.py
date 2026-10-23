"""One full day of European electricity, every 15 minutes, for the time-lapse (?europe&day=).

Asks ENTSO-E Transparency (scripts/entsoe.py; ENTSOE_API_KEY) for whole local days
(Central European time, midnight to midnight), one request per series for the window:
  A44  day-ahead price per bidding zone
  A65  load per country
  A75  generation per production type per country
  A11  physical flows per border, both directions

Values are passthrough, aligned to the day's 15-min slots (null where a source has no
value); generation is grouped by fuel like the snapshot (e.g. wind onshore + offshore).
Computed (scripts/entsoe.py): renewable share of generation, each border's net flow,
and the EU totals (sum over the member states with data, named in "eu.sum_of").

Writes frontend/public/data/eu/day/<YYYY-MM-DD>.json and updates day/index.json:
  {"date", "timezone", "start", "step_s", "slots",
   "prices": {zone: {"country", "values": [EUR/MWh]}},
   "countries": {ISO: {"load": [MW], "renewable_share": [%], "generation": {group: [MW]}}},
   "eu": {"step_s": 900, "sum_of": [ISO], "load": [...], "renewable_share": [...],
          "generation": {...}},
   "borders": [{"a", "b", "values": [MW, a -> b positive],
                "capacity_ab", "capacity_ba", "capacity_doc"  (where published,
                scripts/fetch_eu_capacity.py)}],
   countries[ISO]["forecast"]: {"solar", "wind"}  (day-ahead, A69),
   "highlights": [...]}  (key moments, scripts/day_highlights.py)

    uv run python scripts/build_eu_day.py 2026-10-02      # one day
    uv run python scripts/build_eu_day.py --recent 30    # rolling 30-day archive
    uv run python scripts/build_eu_day.py --weeks-only   # week/<ISO>.json from built days
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entsoe  # noqa: E402
import gb  # noqa: E402
from day_highlights import highlights  # noqa: E402
from fetch_eu_capacity import country_capacity  # noqa: E402
from fetch_eu_snapshot import COUNTRIES, FUEL_GROUP, PRICE_ZONES, SOURCE, USER_AGENT  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu" / "day"
TZ = ZoneInfo("Europe/Berlin")  # CET/CEST, the market's own clock
STEP = 900


def day_window(day: date) -> tuple[datetime, int]:
    """UTC start of the local day and its number of 15-min slots (92/96/100 with DST)."""
    start = datetime(day.year, day.month, day.day, tzinfo=TZ).astimezone(UTC)
    nxt = day + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=TZ).astimezone(UTC)
    return start, int((end - start).total_seconds()) // STEP


def align(
    seconds: list[int], values: list, start: int, slots: int, scale: float = 1.0, digits: int = 1
) -> list:
    """Values on the day's 15-min grid; coarser series (hourly) fill each slot they cover.
    MW keep one decimal; prices keep the source's two (digits=2)."""
    out: list[float | None] = [None] * slots
    step = (seconds[1] - seconds[0]) if len(seconds) > 1 else STEP
    for sec, v in zip(seconds, values, strict=False):
        if v is None:
            continue
        first = (int(sec) - start) // STEP
        for k in range(first, first + max(1, step // STEP)):
            if 0 <= k < slots:
                out[k] = round(float(v) * scale, digits)
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
    """Every source for the local days first..last in one pass (one request per series),
    so a 30-day backfill costs about as much as a single day (~270 requests)."""
    start_dt, _ = day_window(first)
    end_start, end_slots = day_window(last)
    grid = entsoe.Grid(start_dt, end_start + timedelta(seconds=STEP * end_slots))
    with httpx.Client(timeout=300, headers=USER_AGENT) as client:
        got = entsoe.run(
            [(f"price:{z}", lambda z=z: entsoe.price(client, z, grid)) for z in PRICE_ZONES]
            + [(f"power:{c}", lambda c=c: entsoe.power(client, c, grid)) for c in COUNTRIES]
            + [(f"fc:{c}", lambda c=c: entsoe.forecast(client, c, grid)) for c in COUNTRIES]
        )
        flows = entsoe.flows(client, entsoe.BORDERS, grid)
        capacity = country_capacity(client, grid)
        # Great Britain from Elexon, as in the snapshot
        gb_power: dict | None = None
        try:
            readings = gb.fuelinst(client, grid)
            gb_power = gb.power(client, grid, readings)
            flows.update(gb.flows(client, grid, readings))
        except RuntimeError as err:
            print(f"Great Britain skipped: {err}", flush=True)
    power = {c: got[f"power:{c}"] for c in COUNTRIES if got.get(f"power:{c}")}
    if gb_power:
        power["GB"] = gb_power
    print(
        f"prices: {sum(1 for z in PRICE_ZONES if got.get(f'price:{z}'))} zones, "
        f"power: {len(power)} countries, flows: {len(flows)} borders",
        flush=True,
    )
    return {
        "prices": {z: got.get(f"price:{z}") for z in PRICE_ZONES},
        "forecast": {
            c: {"unix_seconds": grid.seconds(), **got[f"fc:{c}"]}
            for c in COUNTRIES
            if got.get(f"fc:{c}")
        },
        "capacity": {f"{c['a']}>{c['b']}": {"unix_seconds": grid.seconds(), **c} for c in capacity},
        "power": power,
        "flows": {
            f"{a}>{b}": {"unix_seconds": grid.seconds(), "values": v} for (a, b), v in flows.items()
        },
    }


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
                "values": align(data["unix_seconds"], data["price"], start, slots, digits=2),
            }
    countries = {}
    for iso, data in raw["power"].items():
        series = power_series(data, start, slots) if data else None
        values = (series or {}).get("load", []) + [
            v for col in (series or {}).get("generation", {}).values() for v in col
        ]
        if series and any(v is not None for v in values):
            countries[iso] = series
            fc = raw.get("forecast", {}).get(iso)
            if fc:
                series["forecast"] = {
                    g: align(fc["unix_seconds"], fc[g], start, slots)
                    for g in ("solar", "wind")
                    if g in fc
                }
    # EU: the members with data on this day, summed per slot (scripts/entsoe.py)
    seconds = next(iter(raw["power"].values()), {}).get("unix_seconds", [])
    first = (start - seconds[0]) // STEP if seconds else 0
    eu = entsoe.eu_sum(raw["power"], range(max(0, first), min(len(seconds), first + slots)))
    borders = []
    for key, data in raw["flows"].items():
        a, b = key.split(">")
        values = align(data["unix_seconds"], data["values"], start, slots)
        if any(v is not None for v in values):
            row = {"a": a, "b": b, "values": values}  # a -> b positive
            cap = raw.get("capacity", {}).get(key)
            if cap:
                row["capacity_ab"] = align(cap["unix_seconds"], cap["ab"], start, slots)
                row["capacity_ba"] = align(cap["unix_seconds"], cap["ba"], start, slots)
                row["capacity_doc"] = cap["doc"]
            borders.append(row)
    payload = {
        "source": SOURCE,
        "date": day.isoformat(),
        "timezone": "Europe/Berlin",
        "start": start_dt.isoformat(),
        "step_s": STEP,
        "slots": slots,
        "prices": prices,
        "countries": countries,
        "eu": (
            {"step_s": STEP, "sum_of": eu["sum_of"], **power_series(eu, start, slots)}
            if eu
            else None
        ),
        "borders": borders,
    }
    payload["highlights"] = highlights(payload)
    return payload


def write_weeks(day_dir: Path, days: int = 7) -> int:
    """Per-country files of the newest `days` built days, back to back, for the
    country cards: week/<ISO>.json and week/EU.json next to the day folder.

    Values are the day files' own, unchanged; slots of the days are concatenated."""
    files = sorted(day_dir.glob("20*.json"))[-days:]
    if not files:
        return 0
    loaded = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    out = day_dir.parent / "week"
    out.mkdir(parents=True, exist_ok=True)
    isos = sorted({iso for d in loaded for iso in d["countries"]})

    def join(pick) -> dict:
        series: dict = {"load": [], "renewable_share": [], "generation": {}}
        for d in loaded:
            c = pick(d)
            n = d["slots"]
            series["load"] += (c or {}).get("load") or [None] * n
            series["renewable_share"] += (c or {}).get("renewable_share") or [None] * n
            for g in {g for x in loaded for g in ((pick(x) or {}).get("generation") or {})}:
                series["generation"].setdefault(g, [])
            for g, col_all in series["generation"].items():
                col_all += ((c or {}).get("generation") or {}).get(g) or [None] * n
            # day-ahead wind and solar forecast (days built before it have none)
            for g in ("solar", "wind"):
                fc = ((c or {}).get("forecast") or {}).get(g)
                series.setdefault("forecast", {"solar": [], "wind": []})[g] += fc or [None] * n
        if not any(v is not None for col in series.get("forecast", {}).values() for v in col):
            series.pop("forecast", None)
        return series

    meta = {
        "source": loaded[-1]["source"],
        "days": [d["date"] for d in loaded],
        "start": loaded[0]["start"],
        "step_s": STEP,
    }
    for iso in isos:
        prices = {}
        for d in loaded:
            for zone, z in d["prices"].items():
                if z["country"] == iso:
                    prices.setdefault(zone, [])
        for zone in prices:
            for d in loaded:
                z = d["prices"].get(zone)
                prices[zone] += z["values"] if z else [None] * d["slots"]
        payload = {
            **meta,
            "country": iso,
            **join(lambda d, i=iso: d["countries"].get(i)),
            "prices": prices,
        }
        (out / f"{iso}.json").write_text(
            json.dumps(payload, separators=(",", ":")), encoding="utf-8"
        )
    eu = {**meta, "country": "EU", **join(lambda d: d.get("eu")), "prices": {}}
    (out / "EU.json").write_text(json.dumps(eu, separators=(",", ":")), encoding="utf-8")
    return len(isos) + 1


# a day with fewer ENTSO-E countries is a failed fetch, not a day (2026-10-21 was written with
# Great Britain alone, from Elexon, and became the replay's newest day)
MIN_COUNTRIES = 20


def entsoe_countries(payload: dict) -> int:
    return sum(1 for c in payload.get("countries", {}) if c != "GB")


def is_complete(path: Path) -> bool:
    try:
        return entsoe_countries(json.loads(path.read_text(encoding="utf-8"))) >= MIN_COUNTRIES
    except (OSError, ValueError):
        return False


def write_index(out: Path) -> list[str]:
    days = sorted(p.stem for p in out.glob("20*.json") if is_complete(p))
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
    parser.add_argument("--weeks-only", action="store_true", help="only rebuild week/ files")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    if args.weeks_only:
        print(f"week/: {write_weeks(args.out)} files")
        return
    if args.recent:
        yesterday = datetime.now(TZ).date() - timedelta(days=1)
        wanted = [yesterday - timedelta(days=i) for i in range(args.recent)]
        # an incomplete file counts as missing: it is built again
        have = {p.stem for p in args.out.glob("20*.json") if is_complete(p)}
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
            if entsoe_countries(payload) < MIN_COUNTRIES:
                # a failed fetch must not replace a good day already in the archive
                print(
                    f"{day}: {entsoe_countries(payload)} countries from ENTSO-E, keeping the existing file",
                    flush=True,
                )
                continue
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
    print(f"week/: {write_weeks(args.out)} files from the newest {min(7, len(days))} days")
    print(f"index: {len(days)} days, {days[0] if days else '-'} .. {days[-1] if days else '-'}")


if __name__ == "__main__":
    main()
