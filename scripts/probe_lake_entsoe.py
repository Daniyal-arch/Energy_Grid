"""Probe what the ENTSO-E history backfill (scripts/build_lake_entsoe.py) can ask per request.

Runs in GitHub Actions (ENTSOE_API_KEY is a repo secret): .github/workflows/lake-entsoe.yml,
job `probe`. Prints, for each question, the answer's size, the series and points found and
the time it took:

  1. A44 prices, DE-LU, a whole year in one request (2019), and DE-AT-LU before Oct 2018
  2. A75 generation, DE, one year in one request vs a quarter
  3. A73 output per unit, TenneT DE: 1 day, 7 days, 31 days in one request
  4. A80 unavailability, DE-LU, one month: zip pages of 200 documents (offset)
  5. A71 installed capacity per unit, DE TenneT, one year
  6. the request rate: 120 small requests with 4 and with 8 at a time (429s counted)
"""

from __future__ import annotations

import io
import os
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

import entsoe
import httpx


def timed(client: httpx.Client, label: str, params: dict[str, str], tag: str = "quantity") -> None:
    t = time.time()
    root = entsoe.request(client, params)
    found = entsoe.points_of(root, tag)
    pts = sum(len(p) for _, p in found)
    first = min((p[0][0] for _, p in found if p), default=None)
    last = max((p[-1][0] for _, p in found if p), default=None)
    res = sorted({p[0][1] for _, p in found if p}, key=str)
    print(
        f"{label}: {len(found)} series, {pts:,} points, {first} .. {last}, resolution {res}, {time.time() - t:.1f} s",
        flush=True,
    )


def main() -> None:
    client = httpx.Client(timeout=300)
    if os.environ.get("PROBE_FROM", "1") == "1":
        first(client)
    rest(client)


def first(client: httpx.Client) -> None:
    de_lu = entsoe.ZONE_EIC["DE-LU"]
    timed(
        client,
        "A44 DE-LU 2019",
        {
            "documentType": "A44",
            "in_Domain": de_lu,
            "out_Domain": de_lu,
            "periodStart": "201901010000",
            "periodEnd": "202001010000",
        },
        "price.amount",
    )
    old = "10Y1001A1001A63L"
    timed(
        client,
        "A44 DE-AT-LU 2017",
        {
            "documentType": "A44",
            "in_Domain": old,
            "out_Domain": old,
            "periodStart": "201701010000",
            "periodEnd": "201801010000",
        },
        "price.amount",
    )
    de = entsoe.AREA_EIC["DE"]
    timed(
        client,
        "A75 DE 2023 (year)",
        {
            "documentType": "A75",
            "processType": "A16",
            "in_Domain": de,
            "periodStart": "202301010000",
            "periodEnd": "202401010000",
        },
    )
    timed(
        client,
        "A75 DE 2023 Q1",
        {
            "documentType": "A75",
            "processType": "A16",
            "in_Domain": de,
            "periodStart": "202301010000",
            "periodEnd": "202304010000",
        },
    )
    tennet = "10YDE-EON------1"
    for days, end in ((1, "202309020000"), (7, "202309080000"), (31, "202310020000")):
        timed(
            client,
            f"A73 TenneT DE {days} d",
            {
                "documentType": "A73",
                "processType": "A16",
                "in_Domain": tennet,
                "periodStart": "202309010000",
                "periodEnd": end,
            },
        )


def rest(client: httpx.Client) -> None:
    tennet = "10YDE-EON------1"
    de_lu = entsoe.ZONE_EIC["DE-LU"]
    root = entsoe.request(
        client,
        {
            "documentType": "A71",
            "processType": "A33",
            "in_Domain": tennet,
            "periodStart": "202301010000",
            "periodEnd": "202301020000",
        },
    )
    if root is not None:
        print(
            "A71 document head:",
            entsoe.ET.tostring(root)[:1500].decode(errors="replace"),
            flush=True,
        )
    timed(
        client,
        "A71 TenneT DE 2023",
        {
            "documentType": "A71",
            "processType": "A33",
            "in_Domain": tennet,
            "periodStart": "202301010000",
            "periodEnd": "202401010000",
        },
    )
    # A80: zip pages
    key = os.environ["ENTSOE_API_KEY"].strip()
    total = 0
    for offset in range(0, 5000, 200):
        t = time.time()
        r = client.get(
            entsoe.BASE,
            params={
                "securityToken": key,
                "documentType": "A80",
                "biddingZone_Domain": de_lu,
                "periodStart": "202301010000",
                "periodEnd": "202302010000",
                "offset": str(offset),
            },
        )
        n = (
            len(zipfile.ZipFile(io.BytesIO(r.content)).namelist())
            if r.content.startswith(b"PK")
            else 0
        )
        total += n
        print(
            f"A80 DE-LU Jan 2023 offset {offset}: HTTP {r.status_code}, {n} documents, {time.time() - t:.1f} s",
            flush=True,
        )
        if n < 200:
            break
    print(f"A80 DE-LU Jan 2023: {total} documents", flush=True)
    # the rate
    for workers in (4, 8):
        entsoe.OUTCOMES.clear()
        params = [
            {
                "documentType": "A65",
                "processType": "A16",
                "outBiddingZone_Domain": eic,
                "periodStart": "202301010000",
                "periodEnd": "202301020000",
            }
            for eic in list(entsoe.AREA_EIC.values()) * 4
        ][:120]
        t = time.time()
        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(lambda p: entsoe.request(client, p), params))
        dt = time.time() - t
        print(
            f"rate with {workers} at a time: {len(params)} requests in {dt:.1f} s = {60 * len(params) / dt:.0f}/min; outcomes {dict(entsoe.OUTCOMES)}",
            flush=True,
        )


if __name__ == "__main__":
    main()
