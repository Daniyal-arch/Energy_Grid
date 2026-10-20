"""Great Britain in the Prices tab (brief 22, family 5): ENTSO-E has no GB prices since 2021.

    python scripts/build_gb_prices.py [--out DIR] [--force]

Elexon's Market Index Data (MID, provider APXMIDP, no key): the half-hourly market index price
(GBP/MWh) of GB's short-term wholesale market, the closest published series to a day-ahead price,
over the same twelve full months as prices.json (scripts/build_prices.py), each half hour on its
two 15-min slots. Converted to EUR/MWh with the ECB's euro reference rate of the day (the last
published rate on days without one), so GB ranks with the other zones; the GBP figures are kept
beside them. The zone's statistics are build_prices.zone_stats (mean, negative hours, extremes,
hour profiles; no capture prices: Elexon's generation is not joined here).

Merged into <out>/prices.json as zone "GB" (run after build_prices.py; skipped when GB already
covers the file's period, unless --force). Imbalance prices for GB: build_imbalance.py (Elexon
system prices, GBP).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_prices as bp  # noqa: E402
import entsoe  # noqa: E402
import wave7_common as w7  # noqa: E402
from build_eu_day import TZ, day_window  # noqa: E402

MID = "https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index"
ECB = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"


def ecb_gbp(raw: bytes) -> dict[str, float]:
    """{YYYY-MM-DD: GBP per EUR} from the ECB's history file."""
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text = z.read(z.namelist()[0]).decode()
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        v = (r.get("GBP") or "").strip()
        if v and v != "N/A":
            out[r["Date"]] = float(v)
    return out


def rate_on(rates: dict[str, float], day: date) -> float | None:
    """The day's rate, else the last one published before it (weekends, holidays)."""
    for back in range(10):
        d = (day - timedelta(days=back)).isoformat()
        if d in rates:
            return rates[d]
    return None


def mid_on_grid(rows: list[dict], grid: entsoe.Grid) -> list[float | None]:
    """Half-hourly prices on the 15-min grid (each half hour fills its two slots)."""
    out = grid.empty()
    for r in rows:
        if r.get("price") is None or r.get("dataProvider") != "APXMIDP":
            continue
        t = int(datetime.fromisoformat(r["startTime"].replace("Z", "+00:00")).timestamp())
        for half in (0, 900):
            k = (t + half - grid.start) // entsoe.STEP
            if 0 <= k < grid.slots:
                out[k] = r["price"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=bp.OUT)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    path = args.out / "prices.json"
    pf = json.loads(path.read_text(encoding="utf-8"))
    first, last = date.fromisoformat(pf["period"][0]), date.fromisoformat(pf["period"][1])
    if not args.force and pf["zones"].get("GB", {}).get("period") == pf["period"]:
        print("GB already covers", pf["period"])
        return
    start, _ = day_window(first)
    end_start, end_slots = day_window(last)
    grid = entsoe.Grid(start, end_start + timedelta(minutes=15 * end_slots))
    end = end_start + timedelta(minutes=15 * end_slots)
    rows: list[dict] = []
    t = start
    while t < end:  # Elexon answers at most 7 days per request
        t1 = min(t + timedelta(days=7), end)
        params = {
            "from": t.strftime("%Y-%m-%dT%H:%MZ"),
            "to": t1.strftime("%Y-%m-%dT%H:%MZ"),
            "dataProviders": "APXMIDP",
            "format": "json",
        }
        rows += w7.get(MID, params=params).json().get("data", [])
        t = t1
    gbp = mid_on_grid(rows, grid)
    rates = ecb_gbp(w7.get(ECB).content)
    seconds = grid.seconds()
    eur = [
        round(v / r, 2)
        if v is not None and (r := rate_on(rates, datetime.fromtimestamp(sec, tz=UTC).date()))
        else None
        for v, sec in zip(gbp, seconds, strict=True)
    ]
    local = [datetime.fromtimestamp(sec, tz=UTC).astimezone(TZ) for sec in seconds]
    month_of = [d.strftime("%Y-%m") for d in local]
    season_of = [bp.SEASON[d.month] for d in local]
    hour_of = [d.hour for d in local]
    z = bp.zone_stats(
        eur, "GB", seconds, pf["months"], month_of, season_of, hour_of, grid.slots, None, None
    )
    if z is None:
        raise SystemExit("Elexon MID: no prices")
    known = [v for v in gbp if v is not None]
    z |= {
        "period": pf["period"],
        "source": "Elexon Market Index Data (APXMIDP), converted at the ECB euro reference rate of the day",
        "currency_source": "GBP",
        "mean_gbp": round(sum(known) / len(known), 2),
    }
    pf["zones"]["GB"] = z
    path.write_text(json.dumps(pf, separators=(",", ":")), encoding="utf-8")
    print(
        f"GB: {len(rows)} half hours, mean {z['mean']} EUR/MWh ({z['mean_gbp']} GBP), negative {z['negative_hours']} h",
        flush=True,
    )


if __name__ == "__main__":
    main()
