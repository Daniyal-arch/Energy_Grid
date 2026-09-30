"""Snapshot of European power-system figures for the Europe view (?europe).

Asks Energy-Charts (Fraunhofer ISE; ENTSO-E data) one request at a time, because the
API answers 429 to bursts:
  /cbpf?country=xx          physical cross-border flows per neighbour
  /public_power?country=xx  load, generation by source, published renewable share
  /public_power?country=eu  the same for the EU aggregate

Values are passthrough from the newest interval every series has reported (the
newest one is often partial). Each border is reported by both sides; the value is
taken from the first country that has it (sign flipped as needed). Generation is
grouped by fuel (e.g. wind onshore + offshore) but not otherwise modified.

Writes frontend/public/data/eu/:
  flows.json  {"source", "fetched", "borders": [{"a", "b", "mw", "ts", "reported_by"}]}
              mw > 0 means power flows from a to b
  stats.json  {"source", "fetched", "eu": Power, "countries": {ISO: Power}}
              Power = {"ts", "load_mw", "renewable_share_of_generation", "generation_mw"}

    uv run python scripts/fetch_eu_snapshot.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.power_live import newest_complete_index  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu"
BASE = "https://api.energy-charts.info"
SOURCE = "Energy-Charts (Fraunhofer ISE), based on ENTSO-E Transparency data"

# Energy-Charts production type -> group shown in the view
FUEL_GROUP = {
    "Solar": "solar",
    "Wind onshore": "wind",
    "Wind offshore": "wind",
    "Nuclear": "nuclear",
    "Fossil gas": "gas",
    "Fossil coal-derived gas": "gas",
    "Fossil brown coal / lignite": "coal",
    "Fossil hard coal": "coal",
    "Fossil peat": "coal",
    "Fossil oil shale": "coal",
    "Fossil oil": "oil",
    "Hydro Run-of-River": "hydro",
    "Hydro water reservoir": "hydro",
    "Hydro pumped storage": "hydro",
    "Biomass": "bio",
    "Waste": "bio",
    "Geothermal": "other",
    "Other renewables": "other",
    "Others": "other",
    "Battery": "other",
}

# Energy-Charts country codes asked, in this order (earlier ones win a border)
CODES = [
    "de",
    "fr",
    "es",
    "it",
    "gb",
    "nl",
    "be",
    "at",
    "ch",
    "pl",
    "cz",
    "dk",
    "no",
    "se",
    "fi",
    "pt",
    "ie",
    "hu",
    "sk",
    "si",
    "hr",
    "ro",
    "bg",
    "gr",
    "rs",
    "ba",
    "me",
    "mk",
    "ee",
    "lv",
    "lt",
    "lu",
    "ua",
    "md",
    "xk",
]
NAME_TO_ISO = {
    "Albania": "AL",
    "Austria": "AT",
    "Belgium": "BE",
    "Bosnia-Herzegovina": "BA",
    "Bosnia and Herzegovina": "BA",
    "Bulgaria": "BG",
    "Croatia": "HR",
    "Czech Republic": "CZ",
    "Czechia": "CZ",
    "Denmark": "DK",
    "Estonia": "EE",
    "Finland": "FI",
    "France": "FR",
    "Germany": "DE",
    "Greece": "GR",
    "Hungary": "HU",
    "Ireland": "IE",
    "Italy": "IT",
    "Kosovo": "XK",
    "Latvia": "LV",
    "Lithuania": "LT",
    "Luxembourg": "LU",
    "Moldova": "MD",
    "Montenegro": "ME",
    "Netherlands": "NL",
    "North Macedonia": "MK",
    "Norway": "NO",
    "Poland": "PL",
    "Portugal": "PT",
    "Romania": "RO",
    "Serbia": "RS",
    "Slovakia": "SK",
    "Slovenia": "SI",
    "Spain": "ES",
    "Sweden": "SE",
    "Switzerland": "CH",
    "Ukraine": "UA",
    "United Kingdom": "GB",
}


def get(client: httpx.Client, path: str, code: str) -> dict | None:
    for attempt in range(5):
        try:
            r = client.get(BASE + path, params={"country": code})
        except httpx.TransportError as err:
            print(f"  {code}: {err.__class__.__name__}, retry", flush=True)
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code == 429:
            wait = float(r.headers.get("retry-after") or 10) + 2
            time.sleep(wait)
            continue
        if r.status_code != 200:
            return None
        return r.json()
    return None


def power(data: dict) -> dict | None:
    """Load, published renewable share and grouped generation at the newest complete interval."""
    series = {s["name"]: s.get("data", []) for s in data.get("production_types", [])}
    # a fuel a country does not report at all is left out, or no interval is ever complete
    gen = {
        name: col
        for name, col in series.items()
        if name in FUEL_GROUP and any(v is not None for v in col)
    }
    if not gen or "Load" not in series:
        return None
    i = newest_complete_index(list(gen.values()) + [series["Load"]])
    if i is None:
        return None
    grouped: dict[str, float] = {}
    for name, col in gen.items():
        grouped[FUEL_GROUP[name]] = grouped.get(FUEL_GROUP[name], 0.0) + float(col[i])
    share = series.get("Renewable share of generation", [])
    return {
        "ts": datetime.fromtimestamp(int(data["unix_seconds"][i]), tz=UTC).isoformat(),
        "load_mw": round(float(series["Load"][i]), 1),
        "renewable_share_of_generation": (
            round(float(share[i]), 1) if i < len(share) and share[i] is not None else None
        ),
        "generation_mw": {k: round(v, 1) for k, v in sorted(grouped.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT, help="output directory")
    out: Path = parser.parse_args().out
    borders: dict[frozenset[str], dict] = {}
    stats: dict[str, dict] = {}
    unknown: set[str] = set()
    with httpx.Client(timeout=90, headers={"User-Agent": "Germany-InfraAtlas/0.1"}) as client:
        eu = power(get(client, "/public_power", "eu") or {})
        time.sleep(3)
        for code in CODES:
            home = code.upper()
            pp = get(client, "/public_power", code)
            time.sleep(3)
            if pp and (row := power(pp)):
                stats[home] = row
            data = get(client, "/cbpf", code)
            time.sleep(3)
            if not data:
                print(f"{home}: no data")
                continue
            series = [s for s in data.get("countries", []) if s.get("name") not in (None, "sum")]
            i = newest_complete_index([s.get("data", []) for s in series])
            if i is None:
                print(f"{home}: no complete interval")
                continue
            ts = datetime.fromtimestamp(int(data["unix_seconds"][i]), tz=UTC).isoformat()
            added = 0
            for s in series:
                other = NAME_TO_ISO.get(s["name"])
                if not other:
                    unknown.add(s["name"])
                    continue
                key = frozenset((home, other))
                if key in borders:
                    continue
                # Energy-Charts: positive = import into the asked country
                import_mw = float(s["data"][i]) * 1000.0
                borders[key] = {
                    "a": other,
                    "b": home,
                    "mw": round(import_mw, 1),
                    "ts": ts,
                    "reported_by": home,
                }
                added += 1
            print(
                f"{home}: {len(series)} neighbours, {added} new borders, interval {ts}", flush=True
            )
    rows = sorted(borders.values(), key=lambda r: -abs(r["mw"]))
    fetched = datetime.now(UTC).isoformat(timespec="seconds")
    out.mkdir(parents=True, exist_ok=True)
    flows = {
        "source": SOURCE + ", cross-border physical flows",
        "fetched": fetched,
        "borders": rows,
    }
    (out / "flows.json").write_text(json.dumps(flows, indent=1), encoding="utf-8")
    summary = {"source": SOURCE, "fetched": fetched, "eu": eu, "countries": stats}
    (out / "stats.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"{len(rows)} borders, {len(stats)} countries with power data, EU aggregate: {bool(eu)}")
    if unknown:
        print("neighbours outside the map (skipped):", ", ".join(sorted(unknown)))


if __name__ == "__main__":
    main()
