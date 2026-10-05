"""Probe ENTSO-E coverage before replacing Energy-Charts with it.

  1. A44 DE-LU, one day: why two TimeSeries per day? (prints each series' metadata)
  2. A44 every candidate bidding zone, one day: which answer, at what resolution
  3. A65 + A75 every mapped country, one day: which answer, resolutions, psr types,
     and whether A75 carries consumption series (outBiddingZone) next to generation
  4. A11 both directions of every border in the bundled flows.json, one day

Sequential with 4 workers, ~250 small requests.

    uv run python scripts/probe_entsoe_coverage.py
"""

from __future__ import annotations

import json
import os
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ["ENTSOE_API_KEY"]
BASE = "https://web-api.tp.entsoe.eu/api"
ROOT = Path(__file__).resolve().parents[1]

ZONES = {
    "DE-LU": "10Y1001A1001A82H", "AT": "10YAT-APG------L", "BE": "10YBE----------2",
    "BG": "10YCA-BULGARIA-R", "CH": "10YCH-SWISSGRIDZ", "CZ": "10YCZ-CEPS-----N",
    "DK1": "10YDK-1--------W", "DK2": "10YDK-2--------M", "EE": "10Y1001A1001A39I",
    "ES": "10YES-REE------0", "FI": "10YFI-1--------U", "FR": "10YFR-RTE------C",
    "GR": "10YGR-HTSO-----Y", "HR": "10YHR-HEP------M", "HU": "10YHU-MAVIR----U",
    "IT-North": "10Y1001A1001A73I", "IT-Centre-North": "10Y1001A1001A70O",
    "IT-Centre-South": "10Y1001A1001A71M", "IT-South": "10Y1001A1001A788",
    "IT-Calabria": "10Y1001C--00096J", "IT-Sicily": "10Y1001A1001A75E",
    "IT-Sardinia": "10Y1001A1001A74G", "LT": "10YLT-1001A0008Q", "LV": "10YLV-1001A00074",
    "ME": "10YCS-CG-TSO---S", "NL": "10YNL----------L", "NO1": "10YNO-1--------2",
    "NO2": "10YNO-2--------T", "NO3": "10YNO-3--------J", "NO4": "10YNO-4--------9",
    "NO5": "10Y1001A1001A48H", "PL": "10YPL-AREA-----S", "PT": "10YPT-REN------W",
    "RO": "10YRO-TEL------P", "RS": "10YCS-SERBIATSOV", "SE1": "10Y1001A1001A44P",
    "SE2": "10Y1001A1001A45N", "SE3": "10Y1001A1001A46L", "SE4": "10Y1001A1001A47J",
    "SI": "10YSI-ELES-----O", "SK": "10YSK-SEPS-----K",
    # candidates Energy-Charts did not price
    "IE-SEM": "10Y1001A1001A59C", "MK": "10YMK-MEPSO----8", "BA": "10YBA-JPCC-----D",
    "AL": "10YAL-KESH-----5", "UA-IPS": "10Y1001C--000182", "MD": "10Y1001A1001A990",
}  # fmt: skip
AREA = {
    "AL": "10YAL-KESH-----5", "AT": "10YAT-APG------L", "BA": "10YBA-JPCC-----D",
    "BE": "10YBE----------2", "BG": "10YCA-BULGARIA-R", "CH": "10YCH-SWISSGRIDZ",
    "CZ": "10YCZ-CEPS-----N", "DE": "10Y1001A1001A83F", "DK": "10Y1001A1001A65H",
    "EE": "10Y1001A1001A39I", "ES": "10YES-REE------0", "FI": "10YFI-1--------U",
    "FR": "10YFR-RTE------C", "GB": "10YGB----------A", "GR": "10YGR-HTSO-----Y",
    "HR": "10YHR-HEP------M", "HU": "10YHU-MAVIR----U", "IE": "10YIE-1001A00010",
    "IT": "10YIT-GRTN-----B", "LT": "10YLT-1001A0008Q", "LU": "10YLU-CEGEDEL-NQ",
    "LV": "10YLV-1001A00074", "ME": "10YCS-CG-TSO---S", "MK": "10YMK-MEPSO----8",
    "NL": "10YNL----------L", "NO": "10YNO-0--------C", "PL": "10YPL-AREA-----S",
    "PT": "10YPT-REN------W", "RO": "10YRO-TEL------P", "RS": "10YCS-SERBIATSOV",
    "SE": "10YSE-1--------K", "SI": "10YSI-ELES-----O", "SK": "10YSK-SEPS-----K",
    "UA": "10Y1001C--00003F", "MD": "10Y1001A1001A990", "XK": "10Y1001C--00100H",
}  # fmt: skip

now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
P0 = (now - timedelta(days=2)).strftime("%Y%m%d0000")
P1 = (now - timedelta(days=1)).strftime("%Y%m%d0000")
client = httpx.Client(timeout=180)


def ask(params: dict[str, str]) -> tuple[int, ET.Element | None, float]:
    t0 = time.monotonic()
    for attempt in range(3):
        try:
            r = client.get(
                BASE, params={"securityToken": KEY, "periodStart": P0, "periodEnd": P1, **params}
            )
        except httpx.TransportError:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(10 * (attempt + 1))
            continue
        root = ET.fromstring(r.content) if r.status_code == 200 else None
        return r.status_code, root, time.monotonic() - t0
    return 0, None, time.monotonic() - t0


def series_meta(root: ET.Element) -> list[dict]:
    ns = {"n": root.tag.split("}")[0].strip("{")}
    out = []
    for ts in root.findall("n:TimeSeries", ns):
        meta = {}
        for child in ts:
            tag = child.tag.split("}")[1]
            if child.text and child.text.strip() and tag not in ("Period",):
                meta[tag] = child.text.strip()
        psr = ts.find(".//n:psrType", ns)
        if psr is not None:
            meta["psrType"] = psr.text
        periods = ts.findall("n:Period", ns)
        meta["resolution"] = sorted({p.findtext("n:resolution", namespaces=ns) for p in periods})
        meta["points"] = sum(len(p.findall("n:Point", ns)) for p in periods)
        meta["start"] = (
            periods[0].findtext("n:timeInterval/n:start", namespaces=ns) if periods else None
        )
        out.append(meta)
    return out


print("== 1. A44 DE-LU, one day: every TimeSeries")
code, root, dt = ask(
    {"documentType": "A44", "in_Domain": ZONES["DE-LU"], "out_Domain": ZONES["DE-LU"]}
)
for m in series_meta(root) if root is not None else []:
    print("  ", m)


def price(zone: str) -> str:
    code, root, dt = ask(
        {"documentType": "A44", "in_Domain": ZONES[zone], "out_Domain": ZONES[zone]}
    )
    if root is None or code != 200:
        return f"{zone}: HTTP {code}"
    metas = series_meta(root)
    if not metas:
        return f"{zone}: no TimeSeries ({root.tag.split('}')[1]})"
    seq = sorted(
        {m.get("classificationSequence_AttributeInstanceComponent.position", "-") for m in metas}
    )
    return f"{zone}: {len(metas)} series, res {sorted({r for m in metas for r in m['resolution']})}, seq {seq}, {dt:.1f}s"


print("\n== 2. A44 every zone, one day")
with ThreadPoolExecutor(4) as pool:
    for line in pool.map(price, list(ZONES)):
        print("  ", line)


def country(iso: str) -> str:
    c1, r1, _ = ask(
        {"documentType": "A65", "processType": "A16", "outBiddingZone_Domain": AREA[iso]}
    )
    c2, r2, dt = ask({"documentType": "A75", "processType": "A16", "in_Domain": AREA[iso]})
    load = series_meta(r1) if r1 is not None and c1 == 200 else []
    gen = series_meta(r2) if r2 is not None and c2 == 200 else []
    cons = [m for m in gen if "outBiddingZone_Domain.mRID" in m]
    return (
        f"{iso}: load {len(load)} series {sorted({r for m in load for r in m['resolution']})};"
        f" gen {len(gen)} series ({len(cons)} consumption) {sorted({r for m in gen for r in m['resolution']})}"
        f" psr {sorted({m.get('psrType') for m in gen if 'inBiddingZone_Domain.mRID' in m})}; {dt:.1f}s"
    )


print("\n== 3. A65 + A75 every country, one day")
with ThreadPoolExecutor(4) as pool:
    for line in pool.map(country, list(AREA)):
        print("  ", line)

flows = json.loads((ROOT / "frontend/public/data/eu/flows.json").read_text(encoding="utf-8"))
pairs = [(b["a"], b["b"]) for b in flows["borders"]]


def border(pair: tuple[str, str]) -> str:
    a, b = pair
    res = []
    for src, dst in ((a, b), (b, a)):
        if src not in AREA or dst not in AREA:
            res.append(f"{src}>{dst}: no area")
            continue
        code, root, _ = ask(
            {"documentType": "A11", "out_Domain": AREA[src], "in_Domain": AREA[dst]}
        )
        metas = series_meta(root) if root is not None and code == 200 else []
        res.append(f"{src}>{dst}: {metas[0]['resolution'] if metas else 'none'}")
    return " | ".join(res)


print(f"\n== 4. A11 both directions, {len(pairs)} borders")
t0 = time.monotonic()
with ThreadPoolExecutor(4) as pool:
    lines = list(pool.map(border, pairs))
missing = [ln for ln in lines if "none" in ln or "no area" in ln]
print(
    f"   {len(pairs)} borders in {time.monotonic() - t0:.0f}s; {len(missing)} with a missing direction:"
)
for ln in missing:
    print("  ", ln)
