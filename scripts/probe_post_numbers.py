"""Check the numbers of a published post against ENTSO-E itself: reads the raw API
documents (own small parser, not the build scripts' code) for the instants the post names
and prints them beside the archived day file's values.

    uv run python scripts/probe_post_numbers.py path/to/day-2026-10-07.json

Needs ENTSOE_API_KEY. About 140 requests, four at a time (~1-2 min)."""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from entsoe import AREA_EIC, ZONE_EIC  # noqa: E402  (EIC codes only)

load_dotenv()
BASE = "https://web-api.tp.entsoe.eu/api"
DAY = "2026-10-07"
START = datetime(2026, 10, 6, 22, 0, tzinfo=UTC)  # 00:00 CEST
END = START + timedelta(days=1)
STEPS = {"PT15M": 15, "PT30M": 30, "PT60M": 60}
GAS = ["B04", "B03"]


def slot_of(cest: str) -> int:
    h, m = map(int, cest.split(":"))
    return (h * 60 + m) // 15


def fetch(params: dict[str, str]) -> ET.Element | None:
    query = {
        "securityToken": os.environ["ENTSOE_API_KEY"].strip(),
        "periodStart": START.strftime("%Y%m%d%H%M"),
        "periodEnd": END.strftime("%Y%m%d%H%M"),
        **params,
    }
    for attempt in range(5):
        try:
            r = httpx.get(BASE, params=query, timeout=60)
        except httpx.TransportError:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            return None if root.tag.endswith("Acknowledgement_MarketDocument") else root
        if r.status_code not in (429, 503):
            return None
    return None


def values_at(root: ET.Element | None, tag: str, slot: int, keep=lambda ts: True) -> list[float]:
    """The value each TimeSeries holds in a 15-min slot (A03 curves: a point holds until
    the next one)."""
    if root is None:
        return []
    ns = {"n": root.tag.split("}")[0].strip("{")}
    at = START + timedelta(minutes=15 * slot)
    out = []
    for ts in root.findall("n:TimeSeries", ns):
        if not keep(ts, ns):
            continue
        for period in ts.findall("n:Period", ns):
            step = STEPS.get(period.findtext("n:resolution", default="", namespaces=ns) or "")
            t0 = datetime.strptime(
                period.findtext("n:timeInterval/n:start", namespaces=ns) or "", "%Y-%m-%dT%H:%MZ"
            ).replace(tzinfo=UTC)
            t1 = datetime.strptime(
                period.findtext("n:timeInterval/n:end", namespaces=ns) or "", "%Y-%m-%dT%H:%MZ"
            ).replace(tzinfo=UTC)
            if not step or not t0 <= at < t1:
                continue
            want = int((at - t0).total_seconds() // (step * 60)) + 1
            points = sorted(
                (
                    int(p.findtext("n:position", namespaces=ns) or 0),
                    float(p.findtext(f"n:{tag}", namespaces=ns) or 0),
                )
                for p in period.findall("n:Point", ns)
            )
            held = [v for pos, v in points if pos <= want]
            if held:
                out.append(held[-1])
    return out


def coupled(ts: ET.Element, ns: dict[str, str]) -> bool:
    """The coupled day-ahead auction: no classification sequence, or sequence 1; EUR."""
    if ts.findtext("n:currency_Unit.name", namespaces=ns) != "EUR":
        return False
    seq = ts.findtext("n:classificationSequence_AttributeInstanceComponent.position", namespaces=ns)
    return seq in (None, "1")


def generated(ts: ET.Element, ns: dict[str, str]) -> bool:
    return ts.find("n:outBiddingZone_Domain.mRID", ns) is None


def main() -> None:
    with open(sys.argv[1], encoding="utf-8") as f:
        day = json.load(f)
    zones = sorted(day["prices"])
    members = day["eu"]["sum_of"]
    jobs: dict[str, dict[str, str]] = {
        f"price:{z}": {"documentType": "A44", "in_Domain": ZONE_EIC[z], "out_Domain": ZONE_EIC[z]}
        for z in zones
    }
    for iso in members:
        eic = AREA_EIC[iso]
        jobs[f"load:{iso}"] = {
            "documentType": "A65",
            "processType": "A16",
            "outBiddingZone_Domain": eic,
        }
        for psr in ["B16", *GAS]:
            jobs[f"gen:{iso}:{psr}"] = {
                "documentType": "A75",
                "processType": "A16",
                "in_Domain": eic,
                "psrType": psr,
            }
    with ThreadPoolExecutor(4) as pool:
        docs = dict(zip(jobs, pool.map(fetch, jobs.values()), strict=True))
    print(f"{len(docs)} documents, {sum(d is not None for d in docs.values())} with data\n")

    def price(z: str, t: str) -> float | None:
        v = values_at(docs[f"price:{z}"], "price.amount", slot_of(t), coupled)
        return v[0] if v else None

    def eu(kind: str, t: str) -> tuple[float, int]:
        total, n = 0.0, 0
        for iso in members:
            keys = (
                [f"load:{iso}"]
                if kind == "load"
                else [f"gen:{iso}:{p}" for p in (["B16"] if kind == "solar" else GAS)]
            )
            got = [
                v
                for k in keys
                for v in values_at(
                    docs[k],
                    "quantity",
                    slot_of(t),
                    (lambda ts, ns: True) if kind == "load" else generated,
                )
            ]
            if got:
                total += sum(got)
                n += 1
        return total / 1000, n

    file_p = lambda z, t: day["prices"][z]["values"][slot_of(t)]  # noqa: E731
    print("PRICES (EUR/MWh)              ENTSO-E    day file")
    checks = [
        ("DE-LU", "08:00"),
        ("DE-LU", "13:00"),
        ("DE-LU", "18:45"),
        ("FR", "18:45"),
        ("PL", "18:45"),
        ("NL", "18:45"),
        ("HU", "18:45"),
        ("RO", "18:45"),
        ("GR", "13:00"),
        ("GR", "18:45"),
        ("NO4", "18:45"),
        ("ES", "16:00"),
        ("SE1", "18:45"),
        ("ME", "18:45"),
        ("AL", "18:45"),
    ]
    for z, t in checks:
        print(f"  {z:<7} {t}   {price(z, t)!s:>12}   {file_p(z, t)!s:>9}")
    for t in ["08:00", "13:00", "18:45"]:
        api = [p for z in zones if (p := price(z, t)) is not None]
        fil = [v for z in zones if (v := file_p(z, t)) is not None]
        print(
            f"  median of zones {t}: ENTSO-E {statistics.median(api)} ({len(api)} zones)   day file {statistics.median(fil)} ({len(fil)} zones)"
        )
    hi = max(
        range(96),
        key=lambda k: statistics.median(
            [v for z in zones if (v := day["prices"][z]["values"][k]) is not None]
        ),
    )
    print(f"  day file: highest median at {hi * 15 // 60:02d}:{hi * 15 % 60:02d}")

    print("\nGENERATION AND LOAD (GW)        ENTSO-E (members with data)   day file")
    g, eu_file = day["countries"]["DE"]["generation"], day["eu"]
    de_api = sum(values_at(docs["gen:DE:B16"], "quantity", slot_of("13:00"), generated)) / 1000
    print(
        f"  DE solar 13:00              {de_api:8.1f}                      {g['solar'][slot_of('13:00')] / 1000:6.1f}"
    )
    for kind, col, t in [
        ("solar", "solar", "13:00"),
        ("gas", "gas", "07:15"),
        ("gas", "gas", "13:00"),
        ("gas", "gas", "18:45"),
        ("solar", "solar", "18:45"),
        ("load", "load", "19:15"),
        ("load", "load", "07:45"),
        ("load", "load", "09:00"),
    ]:
        v, n = eu(kind, t)
        f = (eu_file["load"] if col == "load" else eu_file["generation"][col])[slot_of(t)]
        print(
            f"  EU {kind:<5} {t}              {v:8.1f} ({n:2d} members)          {'-' if f is None else f'{f / 1000:6.1f}'}"
        )


if __name__ == "__main__":
    main()
