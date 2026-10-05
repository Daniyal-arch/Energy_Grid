"""Probe before the Prices tab and LNG send-out.

1. ENTSO-E A75 per bidding zone with a psrType filter (solar B16, wind B18/B19), one
   week: which zones answer (for solar and wind capture prices), and how long.
2. GIE ALSI: which countries report, units of sendOut / inventory / dtrs, and a
   terminal-level listing.

  uv run python scripts/probe_prices_lng.py
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import entsoe
import httpx
from dotenv import load_dotenv

load_dotenv()
now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
grid = entsoe.Grid(now - timedelta(days=7), now)
client = httpx.Client(timeout=300)


def zone(z: str) -> str:
    out = []
    for psr in ("B16", "B18", "B19"):
        t0 = time.monotonic()
        root = entsoe.request(
            client,
            {
                "documentType": "A75",
                "processType": "A16",
                "in_Domain": entsoe.ZONE_EIC[z],
                "psrType": psr,
                **grid.params(),
            },
        )
        found = [
            v
            for m, v in entsoe.series_of(root, "quantity", grid)
            if "outBiddingZone_Domain.mRID" not in m
        ]
        n = sum(x is not None for v in found for x in v)
        out.append(f"{psr}:{n}({time.monotonic() - t0:.0f}s)")
    return f"{z:16} " + " ".join(out)


print("== 1. A75 per bidding zone, one week (filled 15-min slots of 672)")
with ThreadPoolExecutor(4) as pool:
    for line in pool.map(zone, list(entsoe.ZONE_EIC)):
        print("  ", line)

print("\n== 2. GIE ALSI")
key = os.environ["AGSI_API_KEY"]
r = client.get("https://alsi.gie.eu/api/about", params={"show": "listing"}, headers={"x-key": key})
print("about/listing HTTP", r.status_code, r.text[:600].replace("\n", " "))
for c in ("DE", "FR", "IT", "NL", "BE", "PL", "GB", "FI", "LT", "GR", "HR", "PT", "SE", "MT", "CY"):
    r = client.get(
        "https://alsi.gie.eu/api", params={"country": c, "size": "1"}, headers={"x-key": key}
    )
    d = r.json() if r.status_code == 200 else {}
    row = (d.get("data") or [{}])[0]
    print(
        f"  {c}: HTTP {r.status_code} {row.get('name')} {row.get('gasDayStart')} sendOut={row.get('sendOut')} "
        f"dtrs={row.get('dtrs')} inventory={row.get('inventory')} children={len(row.get('children') or [])}"
    )
r = client.get(
    "https://alsi.gie.eu/api", params={"country": "DE", "size": "1"}, headers={"x-key": key}
)
print("DE row keys:", list((r.json().get("data") or [{}])[0].keys()))
