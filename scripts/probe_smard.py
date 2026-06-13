"""Probe the SMARD (smard.de) chart-data JSON API before implementing the adapter.

SMARD publishes German electricity generation by technology and region — free, no key.
The API is two-step: an index of available file timestamps, then a data file per
timestamp holding a [unix_ms, value] series. This probe confirms that shape, the
units, and how current the data is.

Run: uv run python scripts/probe_smard.py
"""

from __future__ import annotations

from datetime import datetime

import httpx

BASE = "https://www.smard.de/app/chart_data"
# generation filters: 4068 = Photovoltaik, 4067 = Wind Onshore, 4066 = Biomasse
PV = "4068"
REGION = "DE"
RES = "day"
UA = {"User-Agent": "Mozilla/5.0"}


def main() -> None:
    with httpx.Client(timeout=30, headers=UA) as c:
        idx = c.get(f"{BASE}/{PV}/{REGION}/index_{RES}.json")
        print(f"index: HTTP {idx.status_code}")
        timestamps = idx.json()["timestamps"]
        print(f"  {len(timestamps)} file timestamps; last 3:")
        for ts in timestamps[-3:]:
            print(f"    {ts}  =  {datetime.utcfromtimestamp(ts / 1000).date()}")

        latest_ts = timestamps[-1]
        data = c.get(f"{BASE}/{PV}/{REGION}/{PV}_{REGION}_{RES}_{latest_ts}.json")
        print(f"\ndata file ({latest_ts}): HTTP {data.status_code}")
        series = data.json()["series"]
        print(f"  {len(series)} points in this file. Last 5 (date, value):")
        for point in series[-5:]:
            ms, val = point
            d = datetime.utcfromtimestamp(ms / 1000).date()
            print(f"    {d}  {val}")
        print("\n(values are MWh per day for German PV generation; null = not yet published)")


if __name__ == "__main__":
    main()
