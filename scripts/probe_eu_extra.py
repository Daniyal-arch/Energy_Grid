"""Probe extra Europe-view sources (small responses only).

1. Energy-Charts /price: which bidding-zone codes answer
2. ENTSO-E A72: hydro reservoir filling per country (weekly, MWh)
3. GIE AGSI+ gas storage (needs a free key; shows the unauthenticated answer)

  uv run python scripts/probe_eu_extra.py
"""

from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()
client = httpx.Client(timeout=90, follow_redirects=True)


def get(url: str, **params: str) -> httpx.Response | None:
    for _ in range(5):
        try:
            r = client.get(url, params=params)
        except httpx.TransportError:
            time.sleep(8)
            continue
        if r.status_code == 429:
            time.sleep(float(r.headers.get("retry-after") or 10) + 2)
            continue
        return r
    return None


print("== 1. Energy-Charts bidding zones")
ZONES = ["AT", "BE", "BG", "CH", "CZ", "DE-LU", "DK1", "DK2", "EE", "ES", "FI", "FR", "GR", "HR", "HU", "IE-SEM", "IT-North", "IT-Centre-North", "IT-Centre-South", "IT-South", "IT-Calabria", "IT-Sicily", "IT-Sardinia", "LT", "LV", "ME", "MK", "NL", "NO1", "NO2", "NO3", "NO4", "NO5", "PL", "PT", "RO", "RS", "SE1", "SE2", "SE3", "SE4", "SI", "SK", "BA", "AL", "XK", "UA", "MD"]
ok, bad = [], []
for z in ZONES:
    r = get("https://api.energy-charts.info/price", bzn=z)
    time.sleep(2.5)
    (ok if r is not None and r.status_code == 200 else bad).append(z)
print("answer:", " ".join(ok))
print("no data:", " ".join(bad))

print("\n== 2. ENTSO-E A72 reservoir filling")
KEY = os.environ.get("ENTSOE_API_KEY", "")
AREA = {"NO": "10YNO-0--------C", "SE": "10YSE-1--------K", "ES": "10YES-REE------0"}
end = datetime.now(UTC)
start = end - timedelta(days=21)
for iso, eic in AREA.items():
    r = get(
        "https://web-api.tp.entsoe.eu/api",
        securityToken=KEY,
        documentType="A72",
        processType="A16",
        in_Domain=eic,
        periodStart=start.strftime("%Y%m%d0000"),
        periodEnd=end.strftime("%Y%m%d0000"),
    )
    if r is None or r.status_code != 200:
        print(iso, "HTTP", None if r is None else r.status_code)
        continue
    root = ET.fromstring(r.content)
    ns = {"n": root.tag.split("}")[0][1:]}
    vals = [p.find("n:quantity", ns).text for p in root.findall(".//n:Point", ns)]
    print(iso, "points", len(vals), "last MWh", vals[-2:])

print("\n== 3. GIE AGSI+ gas storage")
r = get("https://agsi.gie.eu/api", country="DE", size="1")
print("HTTP", None if r is None else r.status_code, "" if r is None else r.text[:200])
