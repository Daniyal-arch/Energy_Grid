"""Probe ENTSO-E physical cross-border flows [A11] for every European border pair.

Country-level EIC areas (not bidding zones), both directions, last 6 hours. Prints
which borders return data, the resolution and the newest value, so the Europe
flow endpoint only asks for borders that answer.

    uv run python scripts/probe_entsoe_borders.py
"""

from __future__ import annotations

import asyncio
import os
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ["ENTSOE_API_KEY"]
BASE = "https://web-api.tp.entsoe.eu/api"

AREA = {
    "AL": "10YAL-KESH-----5",
    "AT": "10YAT-APG------L",
    "BA": "10YBA-JPCC-----D",
    "BE": "10YBE----------2",
    "BG": "10YCA-BULGARIA-R",
    "CH": "10YCH-SWISSGRIDZ",
    "CZ": "10YCZ-CEPS-----N",
    "DE": "10Y1001A1001A83F",
    "DK": "10Y1001A1001A65H",
    "EE": "10Y1001A1001A39I",
    "ES": "10YES-REE------0",
    "FI": "10YFI-1--------U",
    "FR": "10YFR-RTE------C",
    "GB": "10YGB----------A",
    "GR": "10YGR-HTSO-----Y",
    "HR": "10YHR-HEP------M",
    "HU": "10YHU-MAVIR----U",
    "IE": "10YIE-1001A00010",
    "IT": "10YIT-GRTN-----B",
    "LT": "10YLT-1001A0008Q",
    "LU": "10YLU-CEGEDEL-NQ",
    "LV": "10YLV-1001A00074",
    "ME": "10YCS-CG-TSO---S",
    "MK": "10YMK-MEPSO----8",
    "NL": "10YNL----------L",
    "NO": "10YNO-0--------C",
    "PL": "10YPL-AREA-----S",
    "PT": "10YPT-REN------W",
    "RO": "10YRO-TEL------P",
    "RS": "10YCS-SERBIATSOV",
    "SE": "10YSE-1--------K",
    "SI": "10YSI-ELES-----O",
    "SK": "10YSK-SEPS-----K",
    "UA": "10Y1001C--00003F",
    "MD": "10Y1001A1001A990",
    "XK": "10Y1001C--00100H",
}

BORDERS = [
    ("AL", "GR"),
    ("AL", "ME"),
    ("AL", "XK"),
    ("AL", "MK"),
    ("AT", "CH"),
    ("AT", "CZ"),
    ("AT", "DE"),
    ("AT", "HU"),
    ("AT", "IT"),
    ("AT", "SI"),
    ("BA", "HR"),
    ("BA", "ME"),
    ("BA", "RS"),
    ("BE", "DE"),
    ("BE", "FR"),
    ("BE", "GB"),
    ("BE", "LU"),
    ("BE", "NL"),
    ("BG", "GR"),
    ("BG", "MK"),
    ("BG", "RO"),
    ("BG", "RS"),
    ("CH", "DE"),
    ("CH", "FR"),
    ("CH", "IT"),
    ("CZ", "DE"),
    ("CZ", "PL"),
    ("CZ", "SK"),
    ("DE", "DK"),
    ("DE", "FR"),
    ("DE", "LU"),
    ("DE", "NL"),
    ("DE", "NO"),
    ("DE", "PL"),
    ("DE", "SE"),
    ("DK", "GB"),
    ("DK", "NL"),
    ("DK", "NO"),
    ("DK", "SE"),
    ("EE", "FI"),
    ("EE", "LV"),
    ("ES", "FR"),
    ("ES", "PT"),
    ("FI", "NO"),
    ("FI", "SE"),
    ("FR", "GB"),
    ("FR", "IT"),
    ("GB", "IE"),
    ("GB", "NL"),
    ("GB", "NO"),
    ("GR", "IT"),
    ("GR", "MK"),
    ("HR", "HU"),
    ("HR", "RS"),
    ("HR", "SI"),
    ("HU", "RO"),
    ("HU", "RS"),
    ("HU", "SK"),
    ("HU", "UA"),
    ("IT", "ME"),
    ("IT", "SI"),
    ("LT", "LV"),
    ("LT", "PL"),
    ("LT", "SE"),
    ("MD", "RO"),
    ("MD", "UA"),
    ("ME", "RS"),
    ("ME", "XK"),
    ("MK", "RS"),
    ("MK", "XK"),
    ("NL", "NO"),
    ("NO", "SE"),
    ("PL", "SE"),
    ("PL", "SK"),
    ("PL", "UA"),
    ("RO", "RS"),
    ("RO", "UA"),
    ("RS", "XK"),
    ("SK", "UA"),
]


def parse(text: str) -> tuple[str | None, float | None]:
    root = ET.fromstring(text)
    ns = {"n": root.tag.split("}")[0][1:]}
    res = root.find(".//n:resolution", ns)
    pts = root.findall(".//n:Point", ns)
    if not pts:
        return (res.text if res is not None else None), None
    return (res.text if res is not None else None), float(pts[-1].find("n:quantity", ns).text)


async def flow(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, a: str, b: str, start: str, end: str
):
    params = {
        "securityToken": KEY,
        "documentType": "A11",
        "out_Domain": AREA[a],
        "in_Domain": AREA[b],
        "periodStart": start,
        "periodEnd": end,
    }
    r = None
    for attempt in range(3):
        try:
            async with sem:
                r = await client.get(BASE, params=params)
            break
        except httpx.TimeoutException:
            await asyncio.sleep(5 * (attempt + 1))
    if r is None:
        return a, b, 0, None, None
    if r.status_code != 200 or "<Point>" not in r.text:
        return a, b, r.status_code, None, None
    res, val = parse(r.text)
    return a, b, r.status_code, res, val


async def main() -> None:
    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=6)
    s, e = start.strftime("%Y%m%d%H%M"), end.strftime("%Y%m%d%H%M")
    sem = asyncio.Semaphore(3)
    async with httpx.AsyncClient(timeout=60) as client:
        jobs = [flow(client, sem, a, b, s, e) for a, b in BORDERS] + [
            flow(client, sem, b, a, s, e) for a, b in BORDERS
        ]
        t0 = asyncio.get_running_loop().time()
        results = await asyncio.gather(*jobs)
        took = asyncio.get_running_loop().time() - t0
    ok = {(a, b): (res, val) for a, b, _, res, val in results if val is not None}
    print(f"{len(results)} requests in {took:.0f} s, {len(ok)} with data")
    for a, b in BORDERS:
        fw, bw = ok.get((a, b)), ok.get((b, a))
        mark = "ok " if fw or bw else "-- "
        print(f"{mark}{a}-{b}: {a}->{b} {fw}  {b}->{a} {bw}")


asyncio.run(main())
