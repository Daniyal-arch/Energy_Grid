"""Probe: Italy's A65 load from ENTSO-E. The country area returned ~7.7 GW at 06:30
local time against ~21 GW of generation; check every TimeSeries and the bidding zones.

    uv run python scripts/probe_entsoe_italy.py
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import entsoe
import httpx

now = datetime.now(UTC)
grid = entsoe.Grid(now - timedelta(hours=8), now)
c = httpx.Client(timeout=180)
for label, eic in [
    ("IT country", entsoe.AREA_EIC["IT"]),
    *[(z, entsoe.ZONE_EIC[z]) for z in entsoe.ZONE_EIC if z.startswith("IT-")],
]:
    root = entsoe.request(
        c,
        {
            "documentType": "A65",
            "processType": "A16",
            "outBiddingZone_Domain": eic,
            **grid.params(),
        },
    )
    found = entsoe.series_of(root, "quantity", grid)
    for meta, values in found:
        known = [v for v in values if v is not None]
        print(
            f"{label:16} {meta.get('outBiddingZone_Domain.mRID')} {meta.get('businessType')} n={len(known)} last={known[-1] if known else None}"
        )
    if not found:
        print(f"{label:16} none")
