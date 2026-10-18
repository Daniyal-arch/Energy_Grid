"""Probe Energinet's Energi Data Service (api.energidataservice.dk, no key) for Denmark's live
5-minute data: the dataset names, their columns and units, how far behind the newest record is,
and the licence named on the terms page.

    uv run python scripts/probe_dk_live.py
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import httpx

API = "https://api.energidataservice.dk"
DATASETS = ["CO2Emis", "ElectricityProdex5MinRealtime", "PowerSystemRightNow"]


def main() -> None:
    now = datetime.now(UTC)
    with httpx.Client(timeout=30) as c:
        for name in DATASETS:
            meta = c.get(f"{API}/meta/dataset/{name}")
            if meta.status_code != 200:
                print(f"{name}: meta HTTP {meta.status_code}")
                continue
            m = meta.json()
            print(
                f"{name}: '{m['title']}', every {m.get('updateFrequency')}, resolution "
                f"{m.get('resolution')}, data from {m.get('dataFrom')}, filter column "
                f"{m.get('filterColumn')}, active {m.get('active')}"
            )
            for col in m["columns"]:
                print(f"    {col['dbColumn']} [{col.get('unit') or '-'}]")
            col = m.get("filterColumn")
            r = c.get(f"{API}/dataset/{name}", params={"start": "now-PT1H", "sort": f"{col} DESC"})
            recs = r.json().get("records", [])
            if recs:
                newest = datetime.fromisoformat(recs[0][col]).replace(tzinfo=UTC)
                lag = (now - newest).total_seconds() / 60
                print(
                    f"  last hour: {len(recs)} records, newest {recs[0][col]} ({lag:.0f} min ago)"
                )
                print(f"  newest record: {recs[0]}")
            day = c.get(f"{API}/dataset/{name}", params={"start": "now-P1D", "limit": "0"})
            print(f"  last 24 h: {day.json().get('total')} records, {len(day.content):,} bytes")
        terms = c.get("https://www.energidataservice.dk/terms-and-conditions").text
        print(
            "terms page:",
            sorted(set(re.findall(r"Creative Commons CC-BY [0-9.]+", terms))),
        )


if __name__ == "__main__":
    main()
