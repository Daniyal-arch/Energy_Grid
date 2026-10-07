"""Probe Great Britain's open grid data and ENTSO-E plant outages.

1. Elexon Insights API (no key): generation by fuel (FUELINST, 5-min), demand,
   interconnector flows (interconnectors appear as fuel types INT*)
2. NESO / National Grid ESO carbon intensity API (no key): national intensity now
3. Elexon system prices (imbalance), as a GB price signal
4. ENTSO-E A80 (generation unavailability) and A77 (production unavailability) for one
   area, one day: document size, how many units, fields

  uv run python scripts/probe_gb_outages.py
"""

from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()
c = httpx.Client(timeout=120, headers={"User-Agent": "Europe-InfraAtlas/0.3 (probe)"})
now = datetime.now(UTC).replace(second=0, microsecond=0)

print("== 1. Elexon FUELINST (generation by fuel, 5-min)")
r = c.get(
    "https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELINST",
    params={
        "publishDateTimeFrom": (now - timedelta(hours=1)).isoformat(),
        "publishDateTimeTo": now.isoformat(),
        "format": "json",
    },
)
print("HTTP", r.status_code, len(r.content), "bytes")
rows = r.json().get("data", []) if r.status_code == 200 else []
print("rows", len(rows), "fuels", sorted({x.get("fuelType") for x in rows}))
if rows:
    newest = max(x["startTime"] for x in rows)
    print(
        "newest",
        newest,
        [(x["fuelType"], x["generation"]) for x in rows if x["startTime"] == newest],
    )

print("\n== 1b. Elexon demand outturn (INDO / ITSDO)")
r = c.get(
    "https://data.elexon.co.uk/bmrs/api/v1/demand/outturn/summary", params={"resolution": "minute"}
)
print("HTTP", r.status_code, r.text[:300].replace("\n", " "))

print("\n== 2. NESO carbon intensity, national")
r = c.get("https://api.carbonintensity.org.uk/intensity")
print("HTTP", r.status_code, r.text[:300])
r = c.get("https://api.carbonintensity.org.uk/generation")
print("generation mix HTTP", r.status_code, r.text[:400])

print("\n== 3. Elexon system prices (imbalance), today")
r = c.get(
    f"https://data.elexon.co.uk/bmrs/api/v1/balancing/settlement/system-prices/{now.date().isoformat()}"
)
print("HTTP", r.status_code, r.text[:300].replace("\n", " "))

print("\n== 4. ENTSO-E unavailability, DE, one day")
KEY = os.environ["ENTSOE_API_KEY"]
for doc, label in (("A80", "generation units"), ("A77", "production units")):
    t0 = time.monotonic()
    r = c.get(
        "https://web-api.tp.entsoe.eu/api",
        params={
            "securityToken": KEY,
            "documentType": doc,
            "biddingZone_Domain": "10Y1001A1001A82H",
            "periodStart": (now - timedelta(days=1)).strftime("%Y%m%d0000"),
            "periodEnd": (now + timedelta(days=1)).strftime("%Y%m%d0000"),
        },
        timeout=300,
    )
    ctype = r.headers.get("content-type", "")
    print(
        f"{doc} ({label}): HTTP {r.status_code}, {len(r.content) / 1e3:.0f} kB, {ctype}, {time.monotonic() - t0:.1f}s"
    )
    if r.status_code == 200 and "xml" in ctype:
        root = ET.fromstring(r.content)
        print("   root", root.tag.split("}")[1], r.text[:300].replace("\n", " "))
    elif r.status_code == 200:
        print("   (zip archive of documents)")
    else:
        print("  ", r.text[:300].replace("\n", " "))

print("\n== 5. Elexon FUELINST stream over 2 and 31 days; INDO demand")
for days in (2, 31):
    t0 = time.monotonic()
    r = c.get(
        "https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELINST/stream",
        params={
            "publishDateTimeFrom": (now - timedelta(days=days)).isoformat(),
            "publishDateTimeTo": now.isoformat(),
        },
    )
    rows = r.json() if r.status_code == 200 else []
    print(
        f"  {days} d: HTTP {r.status_code}, {len(r.content) / 1e6:.1f} MB, {len(rows)} rows, {time.monotonic() - t0:.1f}s",
        rows[0] if rows else r.text[:200],
    )
r = c.get(
    "https://data.elexon.co.uk/bmrs/api/v1/datasets/INDO/stream",
    params={
        "publishDateTimeFrom": (now - timedelta(days=2)).isoformat(),
        "publishDateTimeTo": now.isoformat(),
    },
)
rows = r.json() if r.status_code == 200 else []
print(
    f"  INDO: HTTP {r.status_code}, {len(rows)} rows, newest",
    max((x["startTime"] for x in rows), default=None),
    rows[:1],
)
