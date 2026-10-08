"""Ontario's grid, live (IESO public reports, no key; scripts/probe_ieso.py).

  RealtimeTotals              5-min "ONTARIO DEMAND" (MW), the newest file of the hour
  RealtimeOntarioZonalPrice   5-min Ontario zonal price (CAD/MWh, "LmpCap")
  GenOutputCapability         hourly output of every generator (MW) with its fuel
  IntertieScheduleFlow        5-min actual flow on each intertie (MW, positive = export
                              from Ontario; checked against the export/import schedules)

IESO's clock is Eastern Standard Time all year (UTC-5); hours are "hour ending", so
hour 1 is 00:00-01:00 and interval 1 of an hour starts at its first minute.

Values are passthrough. Computed: generation per fuel and in total = sum of the
generators reporting for the newest hour with output from at least 80 % of them;
the flow to each neighbour = sum of its interties (Québec has several, Manitoba two),
at the newest 5-min interval reported for every intertie.

Writes frontend/public/data/eu/ontario.json:
  {"source", "fetched", "demand": {"at", "mw"}, "price": {"at", "cad_mwh"},
   "generation": {"at", "total_mw", "by_fuel": {FUEL: MW}, "units": [[name, fuel, MW]]},
   "interties": {"at", "flows": [{"to", "name", "mw"}]}}

    uv run python scripts/fetch_ontario.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
BASE = "https://reports-public.ieso.ca/public"
SOURCE = "IESO public reports (Ontario)"
EST = timezone(timedelta(hours=-5))
MIN_REPORTING = 0.8
# intertie zone -> neighbour code; the map draws one arrow per neighbour
NEIGHBOUR = {
    "MANITOBA": "MB",
    "MANITOBA SK": "MB",
    "MINNESOTA": "MN",
    "MICHIGAN": "MI",
    "NEW-YORK": "NY",
}
NAMES = {"QC": "Québec", "MB": "Manitoba", "MN": "Minnesota", "MI": "Michigan", "NY": "New York"}


def neighbour(zone: str) -> str | None:
    return "QC" if zone.startswith("PQ.") else NEIGHBOUR.get(zone)


def strip(root: ET.Element) -> ET.Element:
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def get_xml(client: httpx.Client, path: str) -> ET.Element:
    r = client.get(f"{BASE}/{path}")
    r.raise_for_status()
    return strip(ET.fromstring(r.content))


def stamp(day: str, hour: int, interval: int = 1) -> str:
    """Start of an hour-ending hour (and 5-min interval) in EST, as ISO with offset."""
    start = datetime.fromisoformat(day).replace(tzinfo=EST)
    return (start + timedelta(hours=hour - 1, minutes=5 * (interval - 1))).isoformat()


def num(text: str | None) -> float | None:
    try:
        return float(text) if text not in (None, "") else None
    except ValueError:
        return None


def demand(client: httpx.Client) -> dict | None:
    # the newest file of the hour (names sort by date-hour, then version)
    listing = client.get(f"{BASE}/RealtimeTotals/").text
    files = sorted(
        set(re.findall(r"PUB_RealtimeTotals_(\d{10})_v(\d+)\.xml", listing)),
        key=lambda f: (f[0], int(f[1])),
    )
    if not files:
        return None
    hour_key, version = files[-1]
    root = get_xml(client, f"RealtimeTotals/PUB_RealtimeTotals_{hour_key}_v{version}.xml")
    day, hour = root.findtext(".//DeliveryDate"), int(root.findtext(".//DeliveryHour") or 0)
    best = None
    for iv in root.iter("IntervalEnergy"):
        for mq in iv.iter("MQ"):
            if (
                mq.findtext("MarketQuantity") == "ONTARIO DEMAND"
                and (mw := num(mq.findtext("EnergyMW"))) is not None
            ):
                best = {"at": stamp(day, hour, int(iv.findtext("Interval") or 1)), "mw": mw}
    return best


def price(client: httpx.Client) -> dict | None:
    root = get_xml(client, "RealtimeOntarioZonalPrice/PUB_RealtimeOntarioZonalPrice.xml")
    day, hour = root.findtext(".//DeliveryDate"), int(root.findtext(".//DeliveryHour") or 0)
    best = None
    for zp in root.iter("ZonalPrice"):
        if (v := num(zp.findtext("LmpCap"))) is not None:
            best = {"at": stamp(day, hour, int(zp.findtext("Interval") or 1)), "cad_mwh": v}
    return best


def generation(client: httpx.Client) -> dict | None:
    root = get_xml(client, "GenOutputCapability/PUB_GenOutputCapability.xml")
    day = root.findtext(".//Date")
    gens = []
    for g in root.iter("Generator"):
        out = {int(o.findtext("Hour") or 0): num(o.findtext("EnergyMW")) for o in g.iter("Output")}
        gens.append((g.findtext("GeneratorName") or "", g.findtext("FuelType") or "OTHER", out))
    if not gens:
        return None
    hours = [
        h
        for h in range(24, 0, -1)
        if sum(1 for *_, out in gens if out.get(h) is not None) >= MIN_REPORTING * len(gens)
    ]
    if not hours:
        return None
    h = hours[0]
    units = [[name, fuel, out[h]] for name, fuel, out in gens if out.get(h) is not None]
    by_fuel: dict[str, float] = {}
    for _, fuel, mw in units:
        by_fuel[fuel] = round(by_fuel.get(fuel, 0.0) + mw, 1)
    return {
        "at": stamp(day, h),
        "total_mw": round(sum(by_fuel.values()), 1),
        "by_fuel": dict(sorted(by_fuel.items(), key=lambda kv: -kv[1])),
        "units": sorted(units, key=lambda u: -u[2]),
    }


def interties(client: httpx.Client) -> dict | None:
    root = get_xml(client, "IntertieScheduleFlow/PUB_IntertieScheduleFlow.xml")
    day = root.findtext(".//Date")
    per_zone: dict[str, dict[tuple[int, int], float]] = {}
    for z in root.iter("IntertieZone"):
        name = z.findtext("IntertieZoneName") or ""
        if not neighbour(name):
            continue
        per_zone[name] = {
            (int(a.findtext("Hour") or 0), int(a.findtext("Interval") or 0)): v
            for a in z.iter("Actual")
            if (v := num(a.findtext("Flow"))) is not None
        }
    common = set.intersection(*(set(v) for v in per_zone.values())) if per_zone else set()
    if not common:
        return None
    hour, interval = max(common)
    sums: dict[str, float] = {}
    for zone, flows in per_zone.items():
        code = neighbour(zone)
        sums[code] = round(sums.get(code, 0.0) + flows[(hour, interval)], 1)
    return {
        "at": stamp(day, hour, interval),
        "flows": [
            {"to": c, "name": NAMES[c], "mw": mw}
            for c, mw in sorted(sums.items(), key=lambda kv: -abs(kv[1]))
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out: Path = parser.parse_args().out
    with httpx.Client(timeout=90, headers={"User-Agent": "Europe-InfraAtlas/0.3"}) as client:
        parts = {}
        for key, fn in [
            ("demand", demand),
            ("price", price),
            ("generation", generation),
            ("interties", interties),
        ]:
            try:
                parts[key] = fn(client)
            except (httpx.HTTPError, ET.ParseError) as err:
                print(f"{key} skipped: {err}", flush=True)
                parts[key] = None
    if not any(parts.values()):
        raise SystemExit("IESO answered nothing usable; keeping the old file")
    data = {"source": SOURCE, "fetched": datetime.now(UTC).isoformat(timespec="seconds"), **parts}
    out.mkdir(parents=True, exist_ok=True)
    path = out / "ontario.json"
    path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    g, d, p = data["generation"], data["demand"], data["price"]
    print(
        f"{path.name}: demand {d and d['mw']} MW ({d and d['at']}), price {p and p['cad_mwh']} CAD/MWh, "
        f"generation {g and g['total_mw']} MW ({g and g['at']}), "
        f"interties {data['interties'] and [(f['to'], f['mw']) for f in data['interties']['flows']]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
