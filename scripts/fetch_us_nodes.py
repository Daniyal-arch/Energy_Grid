"""US day-ahead prices at every node, hour by hour, for "A day in the US" (docs/tasks/10).

Six markets publish their day-ahead prices at every node without a key, read with the
open-source `gridstatus` library (MIT; scripts/probe_us_nodes.py): CAISO (all nodes, incl. the
Western utilities in its markets), ERCOT (settlement point prices), MISO, SPP, NYISO
(generator nodes) and ISO-NE. PJM needs PJM_API_KEY and is skipped while it is missing. Runs
in GitHub Actions (ERCOT blocks many non-US addresses).

Positions: only CAISO publishes its nodes' coordinates (its price contour map,
wwwmobile.caiso.com PriceContourMap1: node name, latitude, longitude, balancing area). A node
is placed when its name equals a map node's name exactly (probe 2026-10-17: 6,442 of 9,731);
every other node, and every node of the other markets, is counted, not placed.

Hours: the day is an Eastern-Time day (the clock of the US replay, scripts/build_us_day.py);
each market's own interval starts (gridstatus gives them with their time zone) are put on that
day's UTC hours, so the western markets' first hours come from their previous market day.

Values are passed through as the markets publish them (USD/MWh). Computed: per market and
hour the minimum, 10th percentile, median, 90th percentile and maximum over its priced
locations; the colour range of the placed nodes (2nd to 98th percentile of the day).

Writes frontend/public/data/eu/us_nodes/<date>.json (+ index.json, the newest 30 days) and,
with --lake, every price to the lake (lake/us_lmp/day_ahead, partitions market, year, month).

    python scripts/fetch_us_nodes.py 2026-10-15 [--out DIR] [--lake lake-out --upload]
    python scripts/fetch_us_nodes.py --recent 30 --max 8   (the missing days, newest first)
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "data" / "eu" / "us_nodes"
ET = ZoneInfo("America/New_York")
KEEP = 30
CAISO_MAP = "https://wwwmobile.caiso.com/Web.Service.Chart/api/v3/ChartService/PriceContourMap1"
SOURCE = "Day-ahead prices at every node of CAISO, ERCOT, MISO, SPP, NYISO, ISO-NE (the markets' public files, via gridstatus)"
MARKETS = ["CAISO", "ERCOT", "MISO", "SPP", "NYISO", "ISO-NE"]


def fetch_market(gs, market: str, d: str):  # noqa: ANN001, ANN201 - gridstatus module, pandas frame
    """One market day of day-ahead prices as the market publishes them."""
    if market == "CAISO":
        return gs.CAISO().get_lmp(d, market="DAY_AHEAD_HOURLY", locations="ALL")
    if market == "ERCOT":
        df = gs.Ercot().get_spp(d, market="DAY_AHEAD_HOURLY")
        return df.rename(columns={"SPP": "LMP"})
    if market == "MISO":
        return gs.MISO().get_lmp(d, market="DAY_AHEAD_HOURLY", locations="ALL")
    if market == "SPP":
        return gs.SPP().get_lmp_day_ahead_hourly(d)
    if market == "NYISO":
        return gs.NYISO().get_lmp(
            d, market="DAY_AHEAD_HOURLY", locations="ALL", location_type="generator"
        )
    if market == "ISO-NE":
        return gs.ISONE().get_lmp(d, market="DAY_AHEAD_HOURLY", locations="ALL")
    raise ValueError(market)


def day_window(day: date) -> tuple[datetime, int]:
    """UTC start of the Eastern-Time day and its number of hours (23/24/25 with DST)."""
    start = datetime(day.year, day.month, day.day, tzinfo=ET).astimezone(UTC)
    nxt = day + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=ET).astimezone(UTC)
    return start, int((end - start).total_seconds() // 3600)


def percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return math.nan
    k = (len(sorted_vals) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def caiso_positions() -> dict[str, tuple[float, float, str]]:
    m = httpx.get(CAISO_MAP, timeout=180).json()["l"][2]["m"]
    return {
        x["n"]: (round(x["c"][1], 5), round(x["c"][0], 5), x.get("a") or "")
        for x in m
        if x.get("c")
    }


def rows_of(df, start: datetime, slots: int) -> list[tuple]:  # noqa: ANN001 - a pandas frame
    """(slot, node, node_type, lmp, energy, congestion, loss, ts) inside the ET day."""
    import pandas as pd

    ts = pd.to_datetime(df["Interval Start"], utc=True)
    k = ((ts - pd.Timestamp(start)).dt.total_seconds() // 3600).astype("int64")
    keep = (k >= 0) & (k < slots) & df["LMP"].notna()
    sub = df[keep]

    def col(c: str) -> list:
        return sub[c].tolist() if c in sub.columns else [None] * len(sub)

    return list(
        zip(
            k[keep].tolist(),
            sub["Location"].astype(str).tolist(),
            col("Location Type"),
            sub["LMP"].astype(float).tolist(),
            col("Energy"),
            col("Congestion"),
            col("Loss"),
            ts[keep].dt.to_pydatetime().tolist(),
            strict=True,
        )
    )


def build(day: date, by_market: dict[str, list[tuple]], positions: dict, fetched: str) -> dict:
    start, slots = day_window(day)
    markets: dict[str, dict] = {}
    for m, rows in by_market.items():
        per_slot: list[list[float]] = [[] for _ in range(slots)]
        nodes = set()
        for k, node, *_rest in rows:
            per_slot[k].append(_rest[1])
            nodes.add(node)
        hours = []
        for vals in per_slot:
            v = sorted(vals)
            hours.append([round(percentile(v, q), 2) for q in (0, 0.1, 0.5, 0.9, 1)] if v else None)
        placed = sum(1 for n in nodes if m == "CAISO" and n in positions)
        markets[m] = {"nodes": len(nodes), "placed": placed, "hours": hours}
    caiso = by_market.get("CAISO", [])
    series: dict[str, list] = {}
    for k, node, _t, lmp, *_ in caiso:
        if node in positions:
            series.setdefault(node, [None] * slots)[k] = lmp
    names = sorted(series)
    all_vals = sorted(v for n in names for v in series[n] if v is not None)
    return {
        "fetched": fetched,
        "source": SOURCE,
        "date": day.isoformat(),
        "timezone": "America/New_York",
        "start": start.isoformat(),
        "slots": slots,
        "step_s": 3600,
        "markets": markets,
        "range": [round(percentile(all_vals, 0.02), 2), round(percentile(all_vals, 0.98), 2)]
        if all_vals
        else None,
        "nodes": [[positions[n][0], positions[n][1], n, positions[n][2]] for n in names],
        "prices": [series[n] for n in names],
    }


def write_lake(by_market: dict[str, list[tuple]], day: date, root: Path, upload: bool) -> None:
    import duckdb
    from lake import Lake

    lake = Lake(
        "us_lmp",
        root,
        source=SOURCE,
        licence="each market's terms (public data)",
        script="scripts/fetch_us_nodes.py",
        source_version=day.isoformat(),
    )
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    for m, rows in by_market.items():
        if not rows:
            continue
        con.execute(
            "CREATE OR REPLACE TEMP TABLE r (ts TIMESTAMPTZ, node VARCHAR, node_type VARCHAR, lmp DOUBLE, energy DOUBLE, congestion DOUBLE, loss DOUBLE)"
        )
        con.executemany(
            "INSERT INTO r VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(t, n, typ, lmp, _f(e), _f(c), _f(lo)) for _k, n, typ, lmp, e, c, lo, t in rows],
        )
        lake.write(
            con,
            "day_ahead",
            f"SELECT ts, '{m}' AS market, node, node_type, lmp, energy, congestion, loss, 3600 AS resolution_s, 'US' AS iso2, 'USA' AS iso3 FROM r",
            sort=["node", "ts"],
            bloom=["node"],
            partition={
                "market": m.lower().replace("-", ""),
                "year": str(day.year),
                "month": f"{day.month:02d}",
            },
            stem=day.isoformat(),
        )
    if upload:
        lake.pull_catalog()
    lake.finish()
    if upload:
        lake.upload()


def _f(v: object) -> float | None:
    try:
        x = float(v)  # type: ignore[arg-type]
        return None if x != x else x
    except (TypeError, ValueError):
        return None


def main() -> None:
    import gridstatus

    parser = argparse.ArgumentParser()
    parser.add_argument("days", nargs="*", help="YYYY-MM-DD (Eastern Time days)")
    parser.add_argument(
        "--recent", type=int, help="the last N days up to yesterday, those not built yet"
    )
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--lake", type=Path)
    parser.add_argument("--upload", action="store_true")
    parser.add_argument(
        "--max", type=int, default=8, help="at most this many days per run, newest first"
    )
    args = parser.parse_args()
    today = datetime.now(ET).date()
    days = [date.fromisoformat(d) for d in args.days]
    if args.recent:
        days += [
            today - timedelta(days=i)
            for i in range(args.recent, 0, -1)
            if not (args.out / f"{today - timedelta(days=i)}.json").exists()
        ]
    # newest first, a few per run: a daily run fills the window over several days
    days = sorted(set(days), reverse=True)[: args.max]
    positions = caiso_positions()
    fetched = datetime.now(UTC).isoformat(timespec="seconds")
    args.out.mkdir(parents=True, exist_ok=True)
    for day in days:
        start, slots = day_window(day)
        by_market: dict[str, list[tuple]] = {}
        for m in MARKETS:
            rows: list[tuple] = []
            for d in (day - timedelta(days=1), day):
                try:
                    rows += rows_of(fetch_market(gridstatus, m, d.isoformat()), start, slots)
                except Exception as e:  # noqa: BLE001 - one market down must not stop the others
                    print(
                        f"  {day} {m} {d}: failed ({type(e).__name__}: {str(e)[:160]})", flush=True
                    )
            by_market[m] = rows
        payload = build(day, by_market, positions, fetched)
        path = args.out / f"{day}.json"
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        counts = {m: v["nodes"] for m, v in payload["markets"].items()}
        print(
            f"{day}: {counts}, {len(payload['nodes'])} placed, {path.stat().st_size / 1e6:.1f} MB",
            flush=True,
        )
        if args.lake:
            write_lake(by_market, day, args.lake, args.upload)
    kept = sorted(p.stem for p in args.out.glob("????-??-??.json"))
    for old in kept[:-KEEP]:
        (args.out / f"{old}.json").unlink()
    (args.out / "index.json").write_text(json.dumps({"days": kept[-KEEP:]}), encoding="utf-8")


if __name__ == "__main__":
    main()
