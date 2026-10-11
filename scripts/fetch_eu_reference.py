"""Slow-changing reference figures for the Europe view (?europe).

  installed capacity  ENTSO-E Transparency A68 (installed capacity per production type,
                      processType A33, yearly), this year, else last year; a country
                      ENTSO-E has nothing for keeps its previous entry and its source
                      (Energy-Charts, fetched before it went down on 2026-09-24)
  reservoir energy    ENTSO-E Transparency A72 (weekly stored energy of hydro reservoirs),
                      newest week and the same week one year earlier

Values are passthrough, grouped by fuel like the snapshot (e.g. wind onshore + offshore).
ENTSO-E needs ENTSOE_API_KEY and is skipped without it (everything is carried over).

Writes frontend/public/data/eu/reference.json:
  {"fetched", "capacity": {ISO: {"year", "gw": {group: GW}, "source"}},
   "reservoirs": {ISO: {"week", "twh", "year_ago_week", "year_ago_twh"}}}

    uv run python scripts/fetch_eu_reference.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entsoe  # noqa: E402

load_dotenv()
OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
ENTSOE = "https://web-api.tp.entsoe.eu/api"

# ENTSO-E country areas with hydro reservoirs
RESERVOIR_AREA = {
    "AT": "10YAT-APG------L",
    "BG": "10YCA-BULGARIA-R",
    "CH": "10YCH-SWISSGRIDZ",
    "ES": "10YES-REE------0",
    "FI": "10YFI-1--------U",
    "FR": "10YFR-RTE------C",
    "HR": "10YHR-HEP------M",
    "IT": "10YIT-GRTN-----B",
    "LV": "10YLV-1001A00074",
    "ME": "10YCS-CG-TSO---S",
    "NO": "10YNO-0--------C",
    "PT": "10YPT-REN------W",
    "RO": "10YRO-TEL------P",
    "RS": "10YCS-SERBIATSOV",
    "SE": "10YSE-1--------K",
    "SI": "10YSI-ELES-----O",
    "SK": "10YSK-SEPS-----K",
}


def get(client: httpx.Client, url: str, params: dict[str, str]) -> httpx.Response | None:
    for attempt in range(5):
        try:
            r = client.get(url, params=params)
        except httpx.TransportError as err:
            print(f"  {err.__class__.__name__}, retry", flush=True)
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code == 429:
            time.sleep(float(r.headers.get("retry-after") or 10) + 2)
            continue
        return r
    return None


# ENTSO-E production types (scripts/entsoe.py PSR_NAME) -> group
A68_GROUP = {
    "Nuclear": "nuclear",
    "Fossil brown coal / lignite": "coal",
    "Fossil hard coal": "coal",
    "Fossil oil shale": "coal",
    "Fossil peat": "coal",
    "Fossil gas": "gas",
    "Fossil coal-derived gas": "gas",
    "Fossil oil": "oil",
    "Hydro Run-of-River": "hydro",
    "Hydro water reservoir": "hydro",
    "Hydro pumped storage": "hydro",
    "Biomass": "bio",
    "Waste": "bio",
    "Wind onshore": "wind",
    "Wind offshore": "wind",
    "Solar": "solar",
    "Battery": "storage",
    "Geothermal": "other",
    "Marine": "other",
    "Other renewables": "other",
    "Others": "other",
}


def capacity_entsoe(client: httpx.Client, key: str, eic: str) -> dict | None:
    """Installed capacity per production type (A68), this year, else last year, grouped (GW)."""
    for year in (datetime.now(UTC).year, datetime.now(UTC).year - 1):
        r = get(
            client,
            ENTSOE,
            {
                "securityToken": key,
                "documentType": "A68",
                "processType": "A33",
                "in_Domain": eic,
                "periodStart": f"{year}01010000",
                "periodEnd": f"{year}01020000",
            },
        )
        if r is None or r.status_code != 200:
            continue
        root = ET.fromstring(r.content)
        ns = {"n": root.tag.split("}")[0][1:]}
        grouped: dict[str, float] = {}
        for ts in root.findall("n:TimeSeries", ns):
            if ts.find("n:outBiddingZone_Domain.mRID", ns) is not None:
                continue  # consumption side
            name = entsoe.PSR_NAME.get(
                ts.findtext("n:MktPSRType/n:psrType", default="", namespaces=ns)
            )
            group = A68_GROUP.get(name or "")
            value = ts.findtext("n:Period/n:Point/n:quantity", namespaces=ns)
            if group and value is not None:
                grouped[group] = grouped.get(group, 0.0) + float(value) / 1000
        if sum(grouped.values()) > 0:
            return {
                "year": year,
                "gw": {k: round(v, 2) for k, v in sorted(grouped.items())},
                "source": "ENTSO-E A68",
            }
    return None


def reservoir(client: httpx.Client, key: str, eic: str) -> dict | None:
    end = datetime.now(UTC)
    start = end - timedelta(days=380)
    r = get(
        client,
        ENTSOE,
        {
            "securityToken": key,
            "documentType": "A72",
            "processType": "A16",
            "in_Domain": eic,
            "periodStart": start.strftime("%Y%m%d0000"),
            "periodEnd": end.strftime("%Y%m%d0000"),
        },
    )
    if r is None or r.status_code != 200:
        return None
    root = ET.fromstring(r.content)
    ns = {"n": root.tag.split("}")[0][1:]}
    weeks: dict[datetime, float] = {}
    for period in root.findall(".//n:Period", ns):
        begin = datetime.fromisoformat(
            period.find("n:timeInterval/n:start", ns).text.replace("Z", "+00:00")
        )
        for point in period.findall("n:Point", ns):
            pos = int(point.find("n:position", ns).text)
            weeks[begin + timedelta(weeks=pos - 1)] = float(point.find("n:quantity", ns).text)
    if not weeks:
        return None
    latest = max(weeks)
    target = latest - timedelta(weeks=52)
    ago = min(weeks, key=lambda w: abs(w - target))
    close = abs(ago - target) <= timedelta(days=4)
    return {
        "week": latest.date().isoformat(),
        "twh": round(weeks[latest] / 1e6, 2),
        "year_ago_week": ago.date().isoformat() if close else None,
        "year_ago_twh": round(weeks[ago] / 1e6, 2) if close else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT, help="output directory")
    out: Path = parser.parse_args().out
    caps: dict[str, dict] = {}
    caps_fetched = datetime.now(UTC).isoformat(timespec="seconds")
    reservoirs: dict[str, dict] = {}
    previous = (
        json.loads((out / "reference.json").read_text(encoding="utf-8"))
        if (out / "reference.json").exists()
        else {}
    )
    key = (os.environ.get("ENTSOE_API_KEY") or "").strip()
    with httpx.Client(timeout=120, headers={"User-Agent": "Europe-InfraAtlas/0.3"}) as client:
        if key:
            for iso, eic in entsoe.AREA_EIC.items():
                if row := capacity_entsoe(client, key, eic):
                    caps[iso] = row
            for iso, eic in RESERVOIR_AREA.items():
                if row := reservoir(client, key, eic):
                    reservoirs[iso] = row
            print(f"reservoir energy for {len(reservoirs)} countries", flush=True)
        else:
            print("ENTSOE_API_KEY not set: everything carried over")
    # a country without ENTSO-E figures keeps its previous entry and source
    for iso, row in previous.get("capacity", {}).items():
        if iso not in caps:
            caps[iso] = {**row, "source": row.get("source", "Energy-Charts")}
    print(
        f"installed capacity: {sum(1 for r in caps.values() if r['source'] == 'ENTSO-E A68')} "
        f"countries from ENTSO-E, {sum(1 for r in caps.values() if r['source'] != 'ENTSO-E A68')} carried over",
        flush=True,
    )
    if not reservoirs:
        reservoirs = previous.get("reservoirs", {})
    out.mkdir(parents=True, exist_ok=True)
    (out / "reference.json").write_text(
        json.dumps(
            {
                "source": "ENTSO-E Transparency A68 installed capacity per production type "
                "(per country 'source'; Energy-Charts where ENTSO-E has none); A72 reservoir filling",
                "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
                "capacity_fetched": caps_fetched,
                "capacity": caps,
                "reservoirs": reservoirs,
            },
            indent=1,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
