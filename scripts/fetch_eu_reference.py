"""Slow-changing reference figures for the Europe view (?europe).

  installed capacity  Energy-Charts /installed_power (yearly), newest year with values
  reservoir energy    ENTSO-E Transparency A72 (weekly stored energy of hydro reservoirs),
                      newest week and the same week one year earlier

Values are passthrough, grouped by fuel like the snapshot (e.g. wind onshore + offshore).
Energy-Charts is asked one request at a time (it answers 429 to bursts); ENTSO-E needs
ENTSOE_API_KEY and is skipped without it.

Writes frontend/public/data/eu/reference.json:
  {"fetched", "capacity": {ISO: {"year", "gw": {group: GW}}},
   "reservoirs": {ISO: {"week", "twh", "year_ago_week", "year_ago_twh"}}}

    uv run python scripts/fetch_eu_reference.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
EC = "https://api.energy-charts.info"
ENTSOE = "https://web-api.tp.entsoe.eu/api"

COUNTRIES = [
    "de", "fr", "es", "it", "nl", "be", "at", "ch", "pl", "cz", "dk", "no", "se", "fi", "pt",
    "ie", "hu", "sk", "si", "hr", "ro", "bg", "gr", "rs", "ba", "me", "mk", "ee", "lv", "lt",
    "lu", "ua", "md", "xk", "al",
]  # fmt: skip

# Energy-Charts installed-power series -> group; solar prefers AC (inverter) over DC
CAPACITY_GROUP = {
    "Nuclear": "nuclear",
    "Fossil brown coal / lignite": "coal",
    "Fossil hard coal": "coal",
    "Fossil gas": "gas",
    "Fossil coal-derived gas": "gas",
    "Fossil oil": "oil",
    "Hydro": "hydro",
    "Hydro Run-of-River": "hydro",
    "Hydro water reservoir": "hydro",
    "Hydro pumped storage": "hydro",
    "Biomass": "bio",
    "Waste": "bio",
    "Wind onshore": "wind",
    "Wind offshore": "wind",
    "Solar AC": "solar",
    "Battery storage (power)": "storage",
    "Geothermal": "other",
    "Others": "other",
    "Other, non-renewable": "other",
}

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


def capacity(data: dict) -> dict | None:
    """Grouped GW for the newest year in which the existing (non-planned) series have values."""
    years = data.get("time", [])
    series = {s["name"]: s.get("data", []) for s in data.get("production_types", [])}
    if "Solar AC" not in series and "Solar DC" in series:
        series["Solar AC"] = series.pop("Solar DC")
    for i in range(len(years) - 1, -1, -1):
        grouped: dict[str, float] = {}
        for name, col in series.items():
            group = CAPACITY_GROUP.get(name)
            if group and i < len(col) and col[i] is not None:
                grouped[group] = grouped.get(group, 0.0) + float(col[i])
        if sum(grouped.values()) > 0:
            return {"year": years[i], "gw": {k: round(v, 2) for k, v in sorted(grouped.items())}}
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
    with httpx.Client(timeout=120, headers={"User-Agent": "Europe-InfraAtlas/0.3"}) as client:
        first = get(client, EC + "/installed_power", {"country": "de", "time_step": "yearly"})
        if first is not None and first.status_code == 200:
            for code in COUNTRIES:
                r = get(client, EC + "/installed_power", {"country": code, "time_step": "yearly"})
                time.sleep(3)
                if r is not None and r.status_code == 200 and (row := capacity(r.json())):
                    caps[code.upper()] = row
        if not caps and (OUT / "reference.json").exists():
            # Energy-Charts unreachable: keep the capacity fetched last time, with its date
            previous = json.loads((OUT / "reference.json").read_text(encoding="utf-8"))
            caps = previous.get("capacity", {})
            caps_fetched = previous.get("capacity_fetched") or previous.get("fetched", "")
            print(f"Energy-Charts unreachable: installed capacity from {caps_fetched}", flush=True)
        print(f"installed capacity for {len(caps)} countries", flush=True)
        key = os.environ.get("ENTSOE_API_KEY")
        if key:
            for iso, eic in RESERVOIR_AREA.items():
                if row := reservoir(client, key, eic):
                    reservoirs[iso] = row
            print(f"reservoir energy for {len(reservoirs)} countries", flush=True)
        else:
            print("ENTSOE_API_KEY not set: reservoirs skipped")
    out.mkdir(parents=True, exist_ok=True)
    (out / "reference.json").write_text(
        json.dumps(
            {
                "source": "Energy-Charts (Fraunhofer ISE) installed power; "
                "ENTSO-E Transparency A72 reservoir filling",
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
