"""Power plants offline right now in Europe (ENTSO-E unavailability of generation units).

ENTSO-E A80 per bidding zone (ENTSOE_API_KEY; scripts/probe_gb_outages.py): a zip of
one document per outage, with the unit, its plant, fuel (psrType), nominal power, planned
(A53) or forced (A54), and the available capacity over time. Units of 100 MW and more
must report.

Rules (documented in docs/DATA_SOURCES.md):
  - the newest revision of each outage document; cancelled (A09) and withdrawn (A13)
    documents are left out
  - offline now = nominal power - available capacity at this moment (computed); units
    with less than 1 MW offline are left out
  - totals per zone and fuel are sums of the units (computed)
  - a unit reporting a nominal power above 2,000 MW is left out as mis-reported: no
    single generating unit in Europe is that large (Italy's operator sends kW labelled
    as MW); each zone counts the units left out ("left_out")

Units carry no coordinates and powerplantmatching has almost no EIC codes to join on,
so outages are shown per bidding zone and country, never placed on a plant.

Writes frontend/public/data/eu/outages.json:
  {"source", "fetched", "at", "total": {...}, "countries": {ISO: {"offline_mw", "planned_mw", "forced_mw",
   "left_out"}}, "zones": {zone: {"country", "offline_mw", "planned_mw", "forced_mw",
   "left_out", "by_fuel": {group: MW}}}, "units": [{"zone", "country", "unit", "plant",
   "fuel", "nominal_mw", "available_mw", "offline_mw", "type", "start", "end"}]}

    uv run python scripts/fetch_outages.py [--out DIR]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entsoe  # noqa: E402
from fetch_eu_snapshot import FUEL_GROUP, PRICE_ZONES, USER_AGENT  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
DROP_STATUS = {"A09", "A13"}  # cancelled, withdrawn
MAX_UNIT_MW = 2000  # larger "units" are reporting errors (e.g. kW sent as MW)
TYPE = {"A53": "planned", "A54": "forced"}
STEP_S = {"PT1M": 60, "PT15M": 900, "PT30M": 1800, "PT60M": 3600, "P1D": 86400}


def _t(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)


def documents(client: httpx.Client, zone: str, now: datetime) -> list[ET.Element]:
    params = {
        "securityToken": os.environ["ENTSOE_API_KEY"],
        "documentType": "A80",
        "biddingZone_Domain": entsoe.ZONE_EIC[zone],
        "periodStart": (now - timedelta(hours=1)).strftime("%Y%m%d%H00"),
        "periodEnd": (now + timedelta(hours=1)).strftime("%Y%m%d%H00"),
    }
    for attempt in range(4):
        try:
            r = client.get(entsoe.BASE, params=params)
        except httpx.TransportError:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code != 200 or not r.content.startswith(b"PK"):
            return []  # an acknowledgement: no outages
        z = zipfile.ZipFile(io.BytesIO(r.content))
        return [ET.fromstring(z.read(name)) for name in z.namelist()]
    return []


def available_at(series: ET.Element, ns: dict, now: datetime) -> float | None:
    """Available capacity at `now` from an A03 curve (a point holds until the next)."""
    for period in series.findall("n:Available_Period", ns):
        start = _t(period.findtext("n:timeInterval/n:start", namespaces=ns) or "")
        end = _t(period.findtext("n:timeInterval/n:end", namespaces=ns) or "")
        if not start <= now < end:
            continue
        step = STEP_S.get(period.findtext("n:resolution", default="", namespaces=ns) or "", 60)
        pos = int((now - start).total_seconds() // step) + 1
        value = None
        for p in sorted(
            (
                int(x.findtext("n:position", namespaces=ns) or 0),
                float(x.findtext("n:quantity", namespaces=ns) or 0),
            )
            for x in period.findall("n:Point", ns)
        ):
            if p[0] <= pos:
                value = p[1]
        return value
    return None


def outages(docs: list[ET.Element], zone: str, now: datetime) -> list[dict]:
    newest: dict[str, tuple[int, ET.Element]] = {}
    for root in docs:
        ns = {"n": root.tag.split("}")[0].strip("{")}
        mrid = root.findtext("n:mRID", namespaces=ns) or ""
        rev = int(root.findtext("n:revisionNumber", default="0", namespaces=ns) or 0)
        if mrid not in newest or rev > newest[mrid][0]:
            newest[mrid] = (rev, root)
    rows = []
    for _, root in newest.values():
        ns = {"n": root.tag.split("}")[0].strip("{")}
        if root.findtext("n:docStatus/n:value", namespaces=ns) in DROP_STATUS:
            continue
        for ts in root.findall("n:TimeSeries", ns):
            # flat tag names, e.g. production_RegisteredResource.pSRType.psrType
            res = "n:production_RegisteredResource"
            nominal = ts.findtext(f"{res}.pSRType.powerSystemResources.nominalP", namespaces=ns)
            avail = available_at(ts, ns, now)
            if nominal is None or avail is None:
                continue
            if float(nominal) > MAX_UNIT_MW:
                rows.append({"zone": zone, "implausible": True})
                continue
            offline = float(nominal) - avail
            if offline < 1:
                continue
            psr = ts.findtext(f"{res}.pSRType.psrType", default="", namespaces=ns) or ""
            start = f"{ts.findtext('n:start_DateAndOrTime.date', namespaces=ns)}T{(ts.findtext('n:start_DateAndOrTime.time', namespaces=ns) or '')[:5]}Z"
            end = f"{ts.findtext('n:end_DateAndOrTime.date', namespaces=ns)}T{(ts.findtext('n:end_DateAndOrTime.time', namespaces=ns) or '')[:5]}Z"
            rows.append(
                {
                    "zone": zone,
                    "country": PRICE_ZONES[zone],
                    "unit": ts.findtext(f"{res}.pSRType.powerSystemResources.name", namespaces=ns),
                    "plant": ts.findtext(f"{res}.name", namespaces=ns),
                    "fuel": FUEL_GROUP.get(entsoe.PSR_NAME.get(psr, ""), "other"),
                    "nominal_mw": round(float(nominal), 1),
                    "available_mw": round(avail, 1),
                    "offline_mw": round(offline, 1),
                    "type": TYPE.get(ts.findtext("n:businessType", namespaces=ns) or "", "other"),
                    "start": start,
                    "end": end,
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out: Path = parser.parse_args().out
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    zones = [z for z in PRICE_ZONES if z in entsoe.ZONE_EIC and z != "UA-IPS"]
    with httpx.Client(timeout=300, headers=USER_AGENT) as client:
        got = entsoe.run(
            [(z, lambda z=z: outages(documents(client, z, now), z, now)) for z in zones]
        )
    found = [u for rows in got.values() if isinstance(rows, list) for u in rows]
    units = sorted((u for u in found if not u.get("implausible")), key=lambda u: -u["offline_mw"])

    def blank(zone: str) -> dict:
        return {
            "country": PRICE_ZONES[zone],
            "offline_mw": 0.0,
            "planned_mw": 0.0,
            "forced_mw": 0.0,
            "left_out": 0,
            "by_fuel": {},
        }

    per_zone: dict[str, dict] = {}
    for u in found:
        if u.get("implausible"):
            per_zone.setdefault(u["zone"], blank(u["zone"]))["left_out"] += 1
    for u in units:
        z = per_zone.setdefault(u["zone"], blank(u["zone"]))
        z["offline_mw"] += u["offline_mw"]
        if u["type"] in ("planned", "forced"):
            z[f"{u['type']}_mw"] += u["offline_mw"]
        z["by_fuel"][u["fuel"]] = z["by_fuel"].get(u["fuel"], 0.0) + u["offline_mw"]
    for z in per_zone.values():
        for k in ("offline_mw", "planned_mw", "forced_mw"):
            z[k] = round(z[k], 1)
        z["by_fuel"] = {
            k: round(v, 1) for k, v in sorted(z["by_fuel"].items(), key=lambda kv: -kv[1])
        }
    # per country: the sum of its zones (DE-LU counts for Germany)
    countries: dict[str, dict] = {}
    for z in per_zone.values():
        c = countries.setdefault(
            z["country"], {"offline_mw": 0.0, "planned_mw": 0.0, "forced_mw": 0.0, "left_out": 0}
        )
        for k in ("offline_mw", "planned_mw", "forced_mw", "left_out"):
            c[k] += z[k]
    for c in countries.values():
        for k in ("offline_mw", "planned_mw", "forced_mw"):
            c[k] = round(c[k], 1)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "ENTSO-E Transparency Platform, A80 unavailability of generation units",
        "fetched": now.isoformat(timespec="seconds"),
        "at": now.isoformat(timespec="seconds"),
        "total": {
            k: round(sum(c[k] for c in countries.values()), 1) for k in ("offline_mw", "planned_mw", "forced_mw", "left_out")
        },
        "countries": dict(sorted(countries.items())),
        "zones": dict(sorted(per_zone.items())),
        "units": units,
    }
    (out / "outages.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    total = sum(z["offline_mw"] for z in per_zone.values())
    print(
        f"outages.json: {len(units)} units offline in {len(per_zone)} zones, {total / 1000:.1f} GW"
    )


if __name__ == "__main__":
    main()
