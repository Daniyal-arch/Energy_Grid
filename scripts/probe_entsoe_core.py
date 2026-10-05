"""Probe ENTSO-E as a stand-in for Energy-Charts (down since late September 2026).

Times one request of each kind the app needs and prints the newest value:
  A44 day-ahead prices    one bidding zone, a whole year (for negative hours / capture prices)
  A65 actual total load   one country, one day
  A75 generation per type one country, one day
  A11 physical flow       one border direction, one day

    uv run python scripts/probe_entsoe_core.py
"""

from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ["ENTSOE_API_KEY"]
BASE = "https://web-api.tp.entsoe.eu/api"
DE_LU = "10Y1001A1001A82H"
DE = "10Y1001A1001A83F"
FR = "10YFR-RTE------C"


def stamp(t: datetime) -> str:
    return t.strftime("%Y%m%d%H%M")


def ask(label: str, params: dict[str, str]) -> None:
    t0 = time.monotonic()
    r = httpx.get(BASE, params={"securityToken": KEY, **params}, timeout=300)
    dt = time.monotonic() - t0
    if r.status_code != 200:
        print(f"{label}: HTTP {r.status_code} in {dt:.1f}s {r.text[:200]}")
        return
    root = ET.fromstring(r.content)
    ns = {"n": root.tag.split("}")[0].strip("{")}
    series = root.findall("n:TimeSeries", ns)
    points = root.findall(".//n:Point", ns)
    res = {e.text for e in root.findall(".//n:resolution", ns)}
    psr = sorted({e.text or "" for e in root.findall(".//n:psrType", ns)})
    last = points[-1] if points else None
    val = None
    if last is not None:
        for tag in ("price.amount", "quantity"):
            e = last.find(f"n:{tag}", ns)
            if e is not None:
                val = e.text
    print(
        f"{label}: {dt:.1f}s, {len(r.content) / 1e3:.0f} kB, series {len(series)}, points {len(points)},"
        f" resolution {sorted(res)}, last {val}" + (f", psr {psr}" if psr else "")
    )


now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
day0 = now - timedelta(days=2)
day1 = now - timedelta(days=1)
ask(
    "A44 DE-LU 365 d",
    {
        "documentType": "A44",
        "in_Domain": DE_LU,
        "out_Domain": DE_LU,
        "periodStart": stamp(now - timedelta(days=365)),
        "periodEnd": stamp(now),
    },
)
ask(
    "A65 DE 1 d",
    {
        "documentType": "A65",
        "processType": "A16",
        "outBiddingZone_Domain": DE,
        "periodStart": stamp(day0),
        "periodEnd": stamp(day1),
    },
)
ask(
    "A75 DE 1 d",
    {
        "documentType": "A75",
        "processType": "A16",
        "in_Domain": DE,
        "periodStart": stamp(day0),
        "periodEnd": stamp(day1),
    },
)
ask(
    "A11 DE>FR 1 d",
    {
        "documentType": "A11",
        "in_Domain": FR,
        "out_Domain": DE,
        "periodStart": stamp(day0),
        "periodEnd": stamp(day1),
    },
)
