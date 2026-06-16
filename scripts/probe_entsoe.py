"""Probe the ENTSO-E Transparency API with the configured key.

Shows three things relevant to gridwatch:
  1. key works + actual generation per production type (DE-LU)   [A75]
  2. installed capacity PER GENERATION UNIT — the cross-ref gold [A71]
  3. actual generation per unit for a sample big plant           [A73]
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ["ENTSOE_API_KEY"]
BASE = "https://web-api.tp.entsoe.eu/api"
DE_LU = "10Y1001A1001A82H"  # Germany-Luxembourg bidding zone

PSR = {
    "B01": "Biomass", "B02": "Lignite", "B03": "Coal gas", "B04": "Gas", "B05": "Hard coal",
    "B06": "Oil", "B09": "Geothermal", "B10": "Pumped hydro", "B11": "Run-of-river hydro",
    "B12": "Reservoir hydro", "B14": "Nuclear", "B15": "Other renewable", "B16": "Solar",
    "B17": "Waste", "B18": "Wind offshore", "B19": "Wind onshore", "B20": "Other",
}


def fmt(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M")


def call(**params) -> httpx.Response:
    return httpx.get(BASE, params={"securityToken": KEY, **params}, timeout=90)


def strip(tag: str) -> str:
    return tag.split("}")[-1]


def main() -> None:
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    # 1) Actual generation per production type — confirms the key + national mix
    r = call(documentType="A75", processType="A16", in_Domain=DE_LU,
             periodStart=fmt(now - timedelta(days=1)), periodEnd=fmt(now))
    print(f"[A75 generation/type] HTTP {r.status_code}, {len(r.text)} bytes")
    if r.status_code != 200:
        print("  ->", r.text[:400])
        return
    root = ET.fromstring(r.text)
    latest: dict[str, float] = {}
    for ts in root.iter():
        if strip(ts.tag) != "TimeSeries":
            continue
        psr = next((strip(e.tag) == "psrType" and e.text for e in ts.iter() if strip(e.tag) == "psrType"), None)
        pts = [float(p.text) for p in ts.iter() if strip(p.tag) == "quantity"]
        if psr and pts:
            latest[PSR.get(psr, psr)] = pts[-1]
    print("  latest generation (MW):")
    for k, v in sorted(latest.items(), key=lambda x: -x[1])[:8]:
        print(f"    {k:18} {v:>9,.0f}")

    # 2) Installed capacity PER UNIT — the per-plant registry to join with MaStR
    yr = now.year
    r = call(documentType="A71", processType="A33", in_Domain=DE_LU,
             periodStart=f"{yr}01010000", periodEnd=f"{yr}12312300")
    print(f"\n[A71 installed capacity/unit] HTTP {r.status_code}, {len(r.text)} bytes")
    if r.status_code == 200:
        root = ET.fromstring(r.text)
        units = []
        for ts in root.iter():
            if strip(ts.tag) != "TimeSeries":
                continue
            name = cap = psr = eic = None
            for e in ts.iter():
                t = strip(e.tag)
                if t == "name" and name is None:
                    name = e.text
                elif t == "nominalP":
                    cap = e.text
                elif t == "psrType":
                    psr = e.text
                elif t == "mRID" and eic is None:
                    eic = e.text
            if name:
                units.append((name, cap, PSR.get(psr, psr), eic))
        print(f"  {len(units)} generation units published. sample:")
        for n, c, p, e in units[:12]:
            print(f"    {str(n)[:34]:34} {str(c):>7} MW  {str(p):16} {e}")
    else:
        print("  ->", r.text[:300])


if __name__ == "__main__":
    main()
