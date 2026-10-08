"""Probe Ontario's IESO public reports (no key): which hours are filled today, what the
intertie report holds (schedules and actual flows), and how the zonal price looks."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

import httpx

BASE = "https://reports-public.ieso.ca/public"
HEADERS = {"User-Agent": "Mozilla/5.0 (InfraAtlas probe)"}


def strip(root: ET.Element) -> ET.Element:
    """Drop XML namespaces so paths stay short."""
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def get(client: httpx.Client, path: str) -> ET.Element:
    r = client.get(f"{BASE}/{path}")
    print(f"== {path}: HTTP {r.status_code}, {len(r.content)} bytes")
    r.raise_for_status()
    return strip(ET.fromstring(r.content))


def main() -> None:
    with httpx.Client(timeout=60, headers=HEADERS) as client:
        gen = get(client, "GenOutputCapability/PUB_GenOutputCapability.xml")
        print("date:", gen.findtext(".//Date"), "created:", gen.findtext(".//CreatedAt"))
        by_hour: dict[int, Counter] = defaultdict(Counter)
        fuels = Counter()
        n = 0
        for g in gen.iter("Generator"):
            n += 1
            fuel = g.findtext("FuelType") or "?"
            fuels[fuel] += 1
            for o in g.iter("Output"):
                h = int(o.findtext("Hour") or 0)
                mw = o.findtext("EnergyMW")
                if mw not in (None, ""):
                    by_hour[h][fuel] += float(mw)
        print(f"{n} generators; fuels: {dict(fuels)}")
        for h in sorted(by_hour)[-3:]:
            print(f"hour {h}: total {sum(by_hour[h].values()):.0f} MW", dict(by_hour[h]))
        first = next(gen.iter("Generator"))
        print("one generator:", ET.tostring(first, encoding="unicode")[:900])

        tie = get(client, "IntertieScheduleFlow/PUB_IntertieScheduleFlow.xml")
        for zone in tie.iter("IntertieZone"):
            name = zone.findtext("IntertieZoneName")
            tags = sorted({el.tag for el in zone.iter()})
            last_sched = [s for s in zone.iter("Schedule")][-1:]
            print(f"zone {name}: tags {tags}")
            if last_sched:
                print(
                    "   last schedule:",
                    ET.tostring(last_sched[0], encoding="unicode").strip()[:200],
                )
            actuals = list(zone.iter("Actual"))
            if actuals:
                print(
                    f"   {len(actuals)} actuals; last:",
                    ET.tostring(actuals[-1], encoding="unicode").strip()[:300],
                )
        totals = list(tie.iter("Totals"))
        print("totals blocks:", len(totals))

        price = get(client, "RealtimeOntarioZonalPrice/PUB_RealtimeOntarioZonalPrice.xml")
        print("price doc:", ET.tostring(price, encoding="unicode")[:1500])


if __name__ == "__main__":
    main()
