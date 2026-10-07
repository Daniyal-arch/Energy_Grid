"""Slow-changing country figures for the Europe view's country cards.

  gas storage   GIE AGSI+ (AGSI_API_KEY): daily fill per country and the EU, last ~400
                days. Passthrough: `full` (% of working gas volume), `gasInStorage` and
                `workingGasVolume` (TWh), `trend` (percentage points per day).
  LNG           GIE ALSI (same key as AGSI+): daily LNG send-out into the grid
                (GWh/d), declared total reference send-out capacity "dtrs" (GWh/d)
                and LNG in tanks (GWh) per country with terminals and the EU, last
                ~400 days, passthrough.
  25 years      Ember yearly electricity data (EMBER_API_KEY): generation by source
                (TWh) per year since 2000, the published renewable share of generation,
                and the published carbon intensity of generation (gCO2/kWh).

Writes frontend/public/data/eu/dossier.json:
  {"fetched", "gas": {ISO|"EU": {"date", "full", "in_storage_twh", "capacity_twh",
   "trend_pp", "series": [[date, full], ...]}},
   "lng": {ISO|"EU": {"date", "send_out", "capacity", "inventory_gwh",
           "series": [[date, send_out], ...]}},
   "ember": {ISO|"EU": {"years": [...], "series": {name: [TWh, ...]},
   "renewable_pct": [...], "intensity": [...]}}}

    uv run python scripts/fetch_eu_dossier.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
AGSI_URL = "https://agsi.gie.eu/api"
ALSI_URL = "https://alsi.gie.eu/api"
# countries with LNG terminals reporting to ALSI (scripts/probe_prices_lng.py)
LNG_COUNTRIES = ["BE", "DE", "ES", "FI", "FR", "GR", "HR", "IT", "LT", "NL", "PL", "PT"]
EMBER_URL = "https://api.ember-energy.org/v1"

# the mapped countries (same list as build_eu_grid.py), with their Ember (ISO 3166-1 alpha-3) code
ISO3 = {
    "AL": "ALB", "AT": "AUT", "BA": "BIH", "BE": "BEL", "BG": "BGR", "CH": "CHE", "CZ": "CZE",
    "DE": "DEU", "DK": "DNK", "EE": "EST", "ES": "ESP", "FI": "FIN", "FR": "FRA", "GB": "GBR",
    "GR": "GRC", "HR": "HRV", "HU": "HUN", "IE": "IRL", "IT": "ITA", "LT": "LTU", "LU": "LUX",
    "LV": "LVA", "ME": "MNE", "MD": "MDA", "MK": "MKD", "NL": "NLD", "NO": "NOR", "PL": "POL",
    "PT": "PRT", "RO": "ROU", "RS": "SRB", "SE": "SWE", "SI": "SVN", "SK": "SVK", "UA": "UKR",
    "XK": "XKX",
}  # fmt: skip
COUNTRIES = list(ISO3)


def get(client: httpx.Client, url: str, params: dict, headers: dict | None = None) -> dict | None:
    for attempt in range(4):
        try:
            r = client.get(url, params=params, headers=headers or {})
        except httpx.TransportError:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code != 200:
            return None
        return r.json()
    return None


def gas(client: httpx.Client, key: str, iso: str) -> dict | None:
    since = (date.today() - timedelta(days=400)).isoformat()
    params = {"type": "eu"} if iso == "EU" else {"country": iso}
    rows: list[dict] = []
    page = 1
    while True:
        d = get(
            client,
            AGSI_URL,
            {**params, "from": since, "size": "300", "page": str(page)},
            {"x-key": key},
        )
        if not d or not d.get("data"):
            break
        rows += d["data"]
        if page >= int(d.get("last_page") or 1):
            break
        page += 1
    rows = [r for r in rows if r.get("full") not in (None, "", "-")]
    if not rows:
        return None
    rows.sort(key=lambda r: r["gasDayStart"])
    last = rows[-1]

    def num(v: str | None) -> float | None:
        try:
            return round(float(v), 2) if v not in (None, "", "-") else None
        except ValueError:
            return None

    return {
        "date": last["gasDayStart"],
        "full": num(last["full"]),
        "in_storage_twh": num(last.get("gasInStorage")),
        "capacity_twh": num(last.get("workingGasVolume")),
        "trend_pp": num(last.get("trend")),
        "series": [[r["gasDayStart"], num(r["full"])] for r in rows],
    }


def _num(v: object) -> float | None:
    try:
        return round(float(v), 1) if v not in (None, "", "-") else None  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def lng(client: httpx.Client, key: str, iso: str) -> dict | None:
    """Daily LNG send-out of a country's terminals (or the EU), last ~400 days."""
    since = (date.today() - timedelta(days=400)).isoformat()
    params = {"type": "eu"} if iso == "EU" else {"country": iso}
    rows: list[dict] = []
    page = 1
    while True:
        d = get(
            client,
            ALSI_URL,
            {**params, "from": since, "size": "300", "page": str(page)},
            {"x-key": key},
        )
        if not d or not d.get("data"):
            break
        rows += d["data"]
        if page >= int(d.get("last_page") or 1):
            break
        page += 1
    rows = sorted(
        (r for r in rows if _num(r.get("sendOut")) is not None), key=lambda r: r["gasDayStart"]
    )
    if not rows:
        return None
    last = rows[-1]
    inventory = last.get("inventory") if isinstance(last.get("inventory"), dict) else {}
    return {
        "date": last["gasDayStart"],
        "send_out": _num(last["sendOut"]),
        "capacity": _num(last.get("dtrs")),
        "inventory_gwh": _num(inventory.get("gwh")),
        "series": [[r["gasDayStart"], _num(r["sendOut"])] for r in rows],
    }


def ember(client: httpx.Client, key: str, entity: str) -> dict | None:
    # countries by ISO alpha-3 code; Ember's aggregates (the EU) by name
    who = {"entity": entity} if entity == "EU" else {"entity_code": entity}
    gen = get(
        client,
        f"{EMBER_URL}/electricity-generation/yearly",
        {**who, "start_date": "2000", "api_key": key},
    )
    if not gen or not gen.get("data"):
        return None
    years = sorted({r["date"] for r in gen["data"]})
    series: dict[str, list] = {}
    renewable = [None] * len(years)
    for r in gen["data"]:
        i = years.index(r["date"])
        # "Net imports" is trade, not generation: left out of the mix
        if not r["is_aggregate_series"] and r["series"] != "Net imports":
            series.setdefault(r["series"], [None] * len(years))[i] = r["generation_twh"]
        elif r["series"] == "Renewables":
            renewable[i] = r["share_of_generation_pct"]
    ci = get(
        client,
        f"{EMBER_URL}/carbon-intensity/yearly",
        {**who, "start_date": "2000", "api_key": key},
    )
    intensity = [None] * len(years)
    for r in (ci or {}).get("data", []):
        if r["date"] in years:
            intensity[years.index(r["date"])] = r["emissions_intensity_gco2_per_kwh"]
    return {
        "years": years,
        "series": dict(sorted(series.items())),
        "renewable_pct": renewable,
        "intensity": intensity,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    out: Path = parser.parse_args().out
    agsi_key = os.environ.get("AGSI_API_KEY", "").strip()
    ember_key = os.environ.get("EMBER_API_KEY", "").strip()
    gas_out: dict[str, dict] = {}
    lng_out: dict[str, dict] = {}
    ember_out: dict[str, dict] = {}
    with httpx.Client(timeout=90, headers={"User-Agent": "Europe-InfraAtlas/0.2"}) as client:
        if agsi_key:
            for _ in range(2):
                for iso in ["EU", *COUNTRIES]:
                    if iso not in gas_out and (row := gas(client, agsi_key, iso)):
                        gas_out[iso] = row
                    time.sleep(0.5)
            print(f"gas storage: {len(gas_out)} countries/aggregates", flush=True)
            # GIE answers some requests with nothing now and then: a second pass for those
            for _ in range(2):
                for iso in ["EU", *LNG_COUNTRIES]:
                    if iso not in lng_out and (row := lng(client, agsi_key, iso)):
                        lng_out[iso] = row
                    time.sleep(0.5)
            print(f"LNG send-out: {len(lng_out)} countries/aggregates", flush=True)
        else:
            print("AGSI_API_KEY not set: gas storage skipped")
        if ember_key:
            for iso in ["EU", *COUNTRIES]:
                entity = "EU" if iso == "EU" else ISO3.get(iso)
                if entity and (row := ember(client, ember_key, entity)):
                    ember_out[iso] = row
                time.sleep(0.3)
            print(f"ember: {len(ember_out)} countries/aggregates", flush=True)
        else:
            print("EMBER_API_KEY not set: Ember skipped")
    out.mkdir(parents=True, exist_ok=True)
    (out / "dossier.json").write_text(
        json.dumps(
            {
                "source": "GIE AGSI+ (gas storage), GIE ALSI (LNG); Ember yearly electricity data (CC BY 4.0)",
                "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
                "gas": gas_out,
                "lng": lng_out,
                "ember": ember_out,
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    size = (out / "dossier.json").stat().st_size / 1e6
    print(f"dossier.json: {size:.2f} MB")


if __name__ == "__main__":
    main()
