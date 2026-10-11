"""One full day of the US grid, hour by hour, for the "A day in the US" replay.

EIA-930 Hourly Electric Grid Monitor (EIA API v2, EIA_API_KEY; scripts/fetch_us.py), for a
local day in Eastern Time (midnight to midnight, the clock EIA's own grid monitor uses):
  region-data       demand (D) of the 13 EIA regions and the Lower 48 (US48)
  fuel-type-data    generation by fuel of the regions and the Lower 48
  interchange-data  flow between regions (and to Canada and Mexico), EIA's sign

Fuel-type data arrive about a day late and interchange about two, so the newest day
built is three days back. The file has the shape of the Europe day files
(scripts/build_eu_day.py), so the same towers, flows, clock and captions replay it:
"countries" are the 13 regions, "eu" holds the Lower 48, "borders" the region pairs.

Values are passthrough (MW, one per hour). Computed: the renewable share of generation
(solar + wind + hydro over every fuel's positive output in that hour), each region pair's
flow in one direction (the other side's report sign-flipped, as in fetch_us.py), and the
key moments (scripts/day_highlights.py).

Writes frontend/public/data/eu/usday/<YYYY-MM-DD>.json and usday/index.json.

    uv run python scripts/build_us_day.py 2026-10-07
    uv run python scripts/build_us_day.py --recent 30
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
from day_highlights import highlights  # noqa: E402
from fetch_us import FUEL_GROUP, NEIGHBOURS, REGIONS, num, rows  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu" / "usday"
TZ = ZoneInfo("America/New_York")
STEP = 3600
LAG_DAYS = 3
RENEWABLE = {"solar", "wind", "hydro"}
SOURCE = "EIA-930 Hourly Electric Grid Monitor (EIA API v2), public domain"


def day_window(day: date) -> tuple[datetime, int]:
    """UTC start of the Eastern-Time day and its number of hours (23/24/25 with DST)."""
    start = datetime(day.year, day.month, day.day, tzinfo=TZ).astimezone(UTC)
    nxt = day + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=TZ).astimezone(UTC)
    return start, int((end - start).total_seconds()) // STEP


def slot_of(period: str, start: datetime) -> int:
    t = datetime.strptime(period, "%Y-%m-%dT%H").replace(tzinfo=UTC)
    return int((t - start).total_seconds()) // STEP


def build(day: date, region: list[dict], fuel: list[dict], inter: list[dict]) -> dict:
    start, slots = day_window(day)
    names: dict[str, str] = {}
    load: dict[str, list[float | None]] = {}
    gen: dict[str, dict[str, list[float | None]]] = {}
    for r in region:
        v, k = num(r["value"]), slot_of(r["period"], start)
        if v is None or not 0 <= k < slots or r["type"] != "D":
            continue
        names[r["respondent"]] = r["respondent-name"]
        load.setdefault(r["respondent"], [None] * slots)[k] = round(v, 1)
    for r in fuel:
        v, k = num(r["value"]), slot_of(r["period"], start)
        if v is None or not 0 <= k < slots:
            continue
        group = FUEL_GROUP.get(r["fueltype"], "other")
        col = gen.setdefault(r["respondent"], {}).setdefault(group, [None] * slots)
        col[k] = round((col[k] or 0.0) + v, 1)

    def series(rid: str) -> dict:
        g = gen.get(rid, {})
        share: list[float | None] = []
        for k in range(slots):
            vals = {grp: col[k] for grp, col in g.items() if col[k] is not None}
            total = sum(v for v in vals.values() if v > 0)
            ren = sum(v for grp, v in vals.items() if grp in RENEWABLE and v > 0)
            share.append(round(100 * ren / total, 1) if total > 0 else None)
        return {
            "load": load.get(rid, [None] * slots),
            "renewable_share": share,
            "generation": dict(sorted(g.items())),
        }

    countries = {rid: series(rid) for rid in REGIONS if rid in load or rid in gen}
    # flows: one direction per pair (a < b, or to a neighbour), the other side sign-flipped
    pairs: dict[tuple[str, str], list[float | None]] = {}
    for r in inter:
        v, k = num(r["value"]), slot_of(r["period"], start)
        a, b = r["fromba"], r["toba"]
        if v is None or not 0 <= k < slots or b not in REGIONS + NEIGHBOURS:
            continue
        key = (a, b) if (a < b or b in NEIGHBOURS) else (b, a)
        if b not in NEIGHBOURS and key != (a, b):
            v = -v
        col = pairs.setdefault(key, [None] * slots)
        if col[k] is None:
            col[k] = round(v, 1)
    payload = {
        "source": SOURCE,
        "region": "us",
        "date": day.isoformat(),
        "timezone": "America/New_York",
        "start": start.isoformat(),
        "step_s": STEP,
        "slots": slots,
        "names": {rid: names.get(rid, rid) for rid in ["US48", *REGIONS]},
        "prices": {},
        "countries": countries,
        "eu": {"step_s": STEP, "sum_of": ["US48"], **series("US48")},
        "borders": [{"a": a, "b": b, "values": v} for (a, b), v in sorted(pairs.items())],
    }
    payload["highlights"] = [h for h in highlights(payload) if not h["kind"].startswith("price")]
    return payload


def write_index(out: Path) -> list[str]:
    days = sorted(f.stem for f in out.glob("????-??-??.json"))
    (out / "index.json").write_text(json.dumps({"days": days}), encoding="utf-8")
    return days


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("day", nargs="?", help="YYYY-MM-DD (Eastern Time)")
    parser.add_argument("--recent", type=int, help="keep the last N complete days")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    newest = datetime.now(TZ).date() - timedelta(days=LAG_DAYS)
    if args.day:
        days = [date.fromisoformat(args.day)]
    else:
        n = args.recent or 30
        have = {f.stem for f in args.out.glob("????-??-??.json")}
        wanted = [newest - timedelta(days=i) for i in range(n)]
        # build what is missing, and always the two newest (late corrections)
        days = sorted(d for i, d in enumerate(wanted) if i < 2 or d.isoformat() not in have)
    args.out.mkdir(parents=True, exist_ok=True)
    first_start, _ = day_window(days[0])
    last_start, last_slots = day_window(days[-1])
    end = last_start + timedelta(seconds=STEP * last_slots)
    span = {"start": first_start.strftime("%Y-%m-%dT%H"), "end": end.strftime("%Y-%m-%dT%H")}
    with httpx.Client(timeout=120, headers={"User-Agent": "Europe-InfraAtlas/0.3"}) as client:
        region = rows(
            client,
            "region-data",
            {"facets[respondent][]": ["US48", *REGIONS], "facets[type][]": ["D"], **span},
        )
        fuel = rows(client, "fuel-type-data", {"facets[respondent][]": ["US48", *REGIONS], **span})
        inter = rows(client, "interchange-data", {"facets[fromba][]": REGIONS, **span})
    print(f"rows: region {len(region)}, fuel {len(fuel)}, interchange {len(inter)}", flush=True)
    for day in days:
        payload = build(day, region, fuel, inter)
        path = args.out / f"{day.isoformat()}.json"
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        print(
            f"{day}: {len(payload['countries'])} regions, {len(payload['borders'])} flows, {path.stat().st_size / 1e3:.0f} kB",
            flush=True,
        )
    if args.recent:
        cutoff = (newest - timedelta(days=args.recent)).isoformat()
        for f in args.out.glob("????-??-??.json"):
            if f.stem <= cutoff:
                f.unlink()
    print(f"index: {len(write_index(args.out))} days", flush=True)


if __name__ == "__main__":
    main()
