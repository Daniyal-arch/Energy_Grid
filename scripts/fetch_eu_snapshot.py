"""Snapshot of European power-system figures for the live map.

Asks ENTSO-E Transparency (scripts/entsoe.py; ENTSOE_API_KEY) for the last ~26 hours:
  A44  day-ahead price per bidding zone
  A65  load per country
  A75  generation per production type per country
  A11  physical flows per border, both directions

Values are passthrough from the newest interval every series of a country has
reported (the newest ones arrive late from some TSOs). Generation is grouped by fuel
(e.g. wind onshore + offshore). Computed (scripts/entsoe.py): the renewable share of
generation, each border's net flow (one direction minus the other), and the EU totals
(sum of the member states with data, listed in "sum_of").

Writes frontend/public/data/eu/:
  flows.json  {"source", "fetched", "series_start", "series_step_s",
               "borders": [{"a", "b", "mw", "ts", "series": [MW | null]}]}
              mw > 0 means power flows from a to b
  stats.json  {"source", "fetched", "eu": Power + {"sum_of"}, "countries": {ISO: Power},
               "day_ahead_prices": {zone: {"country", "ts", "eur_mwh"}}}
              Power = {"ts", "load_mw", "renewable_share_of_generation", "generation_mw"}

    uv run python scripts/fetch_eu_snapshot.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entsoe  # noqa: E402
import gb  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
SOURCE = "ENTSO-E Transparency Platform"
USER_AGENT = {"User-Agent": "Europe-InfraAtlas/0.3"}

# production type -> group shown in the view
FUEL_GROUP = {
    "Solar": "solar",
    "Wind onshore": "wind",
    "Wind offshore": "wind",
    "Nuclear": "nuclear",
    "Fossil gas": "gas",
    "Fossil coal-derived gas": "gas",
    "Fossil brown coal / lignite": "coal",
    "Fossil hard coal": "coal",
    "Fossil peat": "coal",
    "Fossil oil shale": "coal",
    "Fossil oil": "oil",
    "Hydro Run-of-River": "hydro",
    "Hydro water reservoir": "hydro",
    "Hydro pumped storage": "hydro",
    "Biomass": "bio",
    "Waste": "bio",
    "Geothermal": "other",
    "Marine": "other",
    "Other renewables": "other",
    "Others": "other",
    "Battery": "other",
    "Wind": "wind",
}

# countries asked for load and generation (ENTSO-E has none for GB, UA, MD and XK)
COUNTRIES = [iso for iso in entsoe.AREA_EIC if iso not in ("GB", "UA", "MD", "XK")]

# day-ahead price zones -> country; several per country for DK, IT, NO and SE, one
# shared by DE and LU
PRICE_ZONES = {
    "AL": "AL", "AT": "AT", "BE": "BE", "BG": "BG", "CH": "CH", "CZ": "CZ", "DE-LU": "DE",
    "DK1": "DK", "DK2": "DK", "EE": "EE", "ES": "ES", "FI": "FI", "FR": "FR", "GR": "GR",
    "HR": "HR", "HU": "HU", "IT-North": "IT", "IT-Centre-North": "IT", "IT-Centre-South": "IT",
    "IT-South": "IT", "IT-Calabria": "IT", "IT-Sicily": "IT", "IT-Sardinia": "IT", "LT": "LT",
    "LV": "LV", "ME": "ME", "MK": "MK", "NL": "NL", "NO1": "NO", "NO2": "NO", "NO3": "NO",
    "NO4": "NO", "NO5": "NO", "PL": "PL", "PT": "PT", "RO": "RO", "RS": "RS", "SE1": "SE",
    "SE2": "SE", "SE3": "SE", "SE4": "SE", "SI": "SI", "SK": "SK", "UA-IPS": "UA",
}  # fmt: skip
STEP = 900  # 15-min flow series for the 24 h replay
# a production type that has reported nothing for 4 hours is not reporting now (Italy,
# for example, sends no coal values while its coal units are off)
STALE_SLOTS = 16
# a newest interval whose load or total generation is below 60 % of the highest value
# of the 2 hours before is still arriving in parts (Italy publishes zone by zone)
PARTIAL = 0.6
PARTIAL_LOOKBACK = 8


def newest_complete_index(columns: list[list[float | None]]) -> int | None:
    """Index of the newest interval that every series has fully reported.

    A missing value shows up as None, or (in some feeds) as an exact 0 that replaces a
    non-zero value and is filled in later. Such intervals are skipped. A zero that
    follows a zero (an idle unit) is a real reading and is kept.
    """
    length = max((len(col) for col in columns), default=0)
    for i in range(length - 1, -1, -1):
        complete = True
        for col in columns:
            value = col[i] if i < len(col) else None
            previous = col[i - 1] if 0 < i <= len(col) else None
            if value is None or (value == 0 and previous not in (None, 0)):
                complete = False
                break
        if complete:
            return i
    return None


def _last(col: list[float | None]) -> int:
    return max((k for k, v in enumerate(col) if v is not None), default=-1)


def interval(data: dict, at: int | None = None) -> dict | None:
    """Load, grouped generation and renewable share of one interval: the newest
    complete one, or `at`. Types silent for STALE_SLOTS are left out."""
    series = {s["name"]: s.get("data", []) for s in data.get("production_types", [])}
    load = series.get("Load")
    gen = {name: col for name, col in series.items() if name in FUEL_GROUP and _last(col) >= 0}
    if not gen or not load:
        return None
    newest = max([_last(c) for c in gen.values()] + [_last(load)])
    gen = {name: col for name, col in gen.items() if _last(col) >= newest - STALE_SLOTS}
    if at is None:
        found = newest_complete_index(list(gen.values()) + [load])
        if found is None:
            return None
        i = found
        # some TSOs publish an interval in parts, so a newest value far below the
        # hours before is still arriving: step back past it
        cols = list(gen.values())
        totals = [sum(c[k] or 0.0 for c in cols) for k in range(len(load))]

        def partial(k: int) -> bool:
            if any(c[k] is None for c in cols) or load[k] is None:
                return True
            window = range(max(0, k - PARTIAL_LOOKBACK), k)
            load_before = max((load[j] or 0.0 for j in window), default=0.0)
            gen_before = max((totals[j] for j in window), default=0.0)
            return (load[k] or 0.0) < PARTIAL * load_before or totals[k] < PARTIAL * gen_before

        while i > 0 and partial(i):
            i -= 1
    elif at < len(load) and load[at] is not None and any(c[at] is not None for c in gen.values()):
        i = at
    else:
        return None
    grouped: dict[str, float] = {}
    green = total = 0.0
    for name, col in gen.items():
        value = col[i]
        if value is None:
            continue
        grouped[FUEL_GROUP[name]] = grouped.get(FUEL_GROUP[name], 0.0) + float(value)
        total += float(value)
        green += float(value) if name in entsoe.RENEWABLE else 0.0
    return {
        "index": i,
        "ts": datetime.fromtimestamp(int(data["unix_seconds"][i]), tz=UTC).isoformat(),
        "load_mw": round(float(load[i] or 0.0), 1),
        "renewable_share_of_generation": round(100.0 * green / total, 1) if total > 0 else None,
        "generation_mw": {k: round(v, 1) for k, v in sorted(grouped.items())},
        "renewable_mw": green,
        "total_mw": total,
    }


def power(data: dict) -> dict | None:
    """Load, renewable share and grouped generation at the newest complete interval."""
    row = interval(data)
    if not row:
        return None
    return {k: v for k, v in row.items() if k not in ("index", "renewable_mw", "total_mw")}


def eu_now(raw: dict[str, dict]) -> dict | None:
    """EU totals at the newest interval where every member with data is complete:
    the sum of the members' own values (computed; members named in "sum_of")."""
    newest = {m: row for m in entsoe.EU_MEMBERS if raw.get(m) and (row := interval(raw[m]))}
    if not newest:
        return None
    members = list(newest)
    start = min(row["index"] for row in newest.values())
    for i in range(start, max(-1, start - 8), -1):
        rows = [interval(raw[m], at=i) for m in members]
        if any(r is None for r in rows):
            continue
        ok = [r for r in rows if r]
        grouped: dict[str, float] = {}
        for r in ok:
            for g, mw in r["generation_mw"].items():
                grouped[g] = grouped.get(g, 0.0) + mw
        green = sum(r["renewable_mw"] for r in ok)
        total = sum(r["total_mw"] for r in ok)
        return {
            "ts": ok[0]["ts"],
            "load_mw": round(sum(r["load_mw"] for r in ok), 1),
            "renewable_share_of_generation": round(100.0 * green / total, 1) if total > 0 else None,
            "generation_mw": {k: round(v, 1) for k, v in sorted(grouped.items())},
            "sum_of": members,
        }
    return None


def price_now(data: dict, now: float) -> tuple[str, float] | None:
    """Day-ahead price of the interval that contains `now`."""
    rows = [
        (t, p)
        for t, p in zip(data.get("unix_seconds", []), data.get("price", []), strict=False)
        if p is not None and t <= now
    ]
    if not rows:
        return None
    t, p = rows[-1]
    return datetime.fromtimestamp(int(t), tz=UTC).isoformat(), round(float(p), 2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT, help="output directory")
    out: Path = parser.parse_args().out
    now = datetime.now(UTC)
    grid = entsoe.Grid(now - timedelta(hours=26), now + timedelta(minutes=15))
    with httpx.Client(timeout=180, headers=USER_AGENT) as client:
        got = entsoe.run(
            [(f"price:{z}", lambda z=z: entsoe.price(client, z, grid)) for z in PRICE_ZONES]
            + [(f"power:{c}", lambda c=c: entsoe.power(client, c, grid)) for c in COUNTRIES]
        )
        print(
            f"prices and power: {sum(v is not None for v in got.values())} of {len(got)} answered",
            flush=True,
        )
        border_series = entsoe.flows(client, entsoe.BORDERS, grid)
        # Great Britain from Elexon (ENTSO-E has none since Brexit); its border flows
        # replace ENTSO-E's for all GB links, which also adds GB-DK
        gb_power: dict | None = None
        try:
            readings = gb.fuelinst(client, grid)
            gb_power = gb.power(client, grid, readings)
            border_series.update(gb.flows(client, grid, readings))
        except RuntimeError as err:
            print(f"Great Britain skipped: {err}", flush=True)
        print(f"flows: {len(border_series)} of {len(entsoe.BORDERS)} borders", flush=True)

    raw_power = {c: got[f"power:{c}"] for c in COUNTRIES if got.get(f"power:{c}")}
    if gb_power:
        raw_power["GB"] = gb_power
    stats = {c: row for c, data in raw_power.items() if (row := power(data))}
    eu = eu_now(raw_power)
    prices: dict[str, dict] = {}
    for zone, iso in PRICE_ZONES.items():
        data = got.get(f"price:{zone}")
        if isinstance(data, dict) and (row := price_now(data, now.timestamp())):
            prices[zone] = {"country": iso, "ts": row[0], "eur_mwh": row[1]}

    # flows: each border's newest measured value; 24 h of 15-min values for the replay
    seconds = grid.seconds()
    series_start = int((now - timedelta(hours=24)).timestamp()) // STEP * STEP
    first = (series_start - grid.start) // STEP
    rows = []
    for (a, b), values in border_series.items():
        known = [k for k, v in enumerate(values) if v is not None]
        if not known:
            continue
        i = known[-1]
        rows.append(
            {
                "a": a,
                "b": b,
                "mw": values[i],
                "ts": datetime.fromtimestamp(seconds[i], tz=UTC).isoformat(),
                "series": [values[k] if k <= i else None for k in range(first, grid.slots)],
            }
        )
    rows.sort(key=lambda r: -abs(r["mw"]))

    fetched = now.isoformat(timespec="seconds")
    out.mkdir(parents=True, exist_ok=True)
    flows = {
        "source": SOURCE + ", physical flows (A11), net of both directions",
        "fetched": fetched,
        # series[k] is the 15-min interval starting at series_start + k * 900 s
        "series_start": datetime.fromtimestamp(series_start, tz=UTC).isoformat(),
        "series_step_s": STEP,
        "borders": rows,
    }
    (out / "flows.json").write_text(json.dumps(flows, separators=(",", ":")), encoding="utf-8")
    summary = {
        "source": SOURCE,
        "fetched": fetched,
        "eu": eu,
        "countries": stats,
        "day_ahead_prices": prices,
    }
    (out / "stats.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    # what this run got, for the app's freshness note and for debugging the workflow
    health = {
        "fetched": fetched,
        "entsoe_requests": dict(entsoe.OUTCOMES),
        "countries": len(stats),
        "borders": len(rows),
        "price_zones": len(prices),
    }
    (out / "health.json").write_text(json.dumps(health, indent=1), encoding="utf-8")
    print(
        f"{len(rows)} borders, {len(stats)} countries with power data, {len(prices)} price zones, "
        f"EU: {eu['ts'] + ' over ' + str(len(eu['sum_of'])) + ' members' if eu else 'none'}"
    )
    late = sorted(set(COUNTRIES) - set(stats))
    if late:
        print("no complete interval in the window:", ", ".join(late))


if __name__ == "__main__":
    main()
    # an empty run must not replace the last good snapshot: fail, so nothing is published
    if not entsoe.OUTCOMES.get("200"):
        print("no ENTSO-E request succeeded:", dict(entsoe.OUTCOMES), file=sys.stderr)
        sys.exit(1)
