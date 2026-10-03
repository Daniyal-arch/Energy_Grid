"""Snapshot of European power-system figures for the Europe view (?europe).

Asks Energy-Charts (Fraunhofer ISE; ENTSO-E data) one request at a time, because the
API answers 429 to bursts:
  /cbpf?country=xx          physical cross-border flows per neighbour
  /public_power?country=xx  load, generation by source, published renewable share
  /public_power?country=eu  the same for the EU aggregate
  /price?bzn=zone           day-ahead price per bidding zone

Values are passthrough from the newest interval every series has reported (the
newest one is often partial). Each border is reported by both sides; the value is
taken from the first country that has it (sign flipped as needed). Generation is
grouped by fuel (e.g. wind onshore + offshore) but not otherwise modified.

Writes frontend/public/data/eu/:
  flows.json  {"source", "fetched", "series_start", "series_step_s",
               "borders": [{"a", "b", "mw", "ts", "reported_by", "series": [MW | null]}]}
              mw > 0 means power flows from a to b
  stats.json  {"source", "fetched", "eu": Power, "countries": {ISO: Power},
               "day_ahead_prices": {zone: {"country", "ts", "eur_mwh"}}}
              Power = {"ts", "load_mw", "renewable_share_of_generation", "generation_mw"}

    uv run python scripts/fetch_eu_snapshot.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

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


# day-ahead price zones (Energy-Charts bzn codes) -> country; several per country for
# DK, IT, NO and SE, one shared by DE and LU
PRICE_ZONES = {
    "AT": "AT", "BE": "BE", "BG": "BG", "CH": "CH", "CZ": "CZ", "DE-LU": "DE", "DK1": "DK",
    "DK2": "DK", "EE": "EE", "ES": "ES", "FI": "FI", "FR": "FR", "GR": "GR", "HR": "HR",
    "HU": "HU", "IT-North": "IT", "IT-Centre-North": "IT", "IT-Centre-South": "IT",
    "IT-South": "IT", "IT-Calabria": "IT", "IT-Sicily": "IT", "IT-Sardinia": "IT", "LT": "LT",
    "LV": "LV", "ME": "ME", "NL": "NL", "NO1": "NO", "NO2": "NO", "NO3": "NO", "NO4": "NO",
    "NO5": "NO", "PL": "PL", "PT": "PT", "RO": "RO", "RS": "RS", "SE1": "SE", "SE2": "SE",
    "SE3": "SE", "SE4": "SE", "SI": "SI", "SK": "SK",
}  # fmt: skip
STEP = 900  # 15-min flow series for the 24 h replay


def newest_complete_index(columns: list[list[float | None]]) -> int | None:
    """Index of the newest interval that every series has fully reported.

    Energy-Charts publishes its newest 15-minute interval before every TSO has
    reported; a missing value shows up as None or as an exact 0 that replaces a
    non-zero value, and is filled in later. Such intervals are skipped. A zero that
    follows a zero (an idle link) is a real reading and is kept.
    """
    length = max((len(col) for col in columns), default=0)
    for i in range(length - 1, -1, -1):
        complete = True
        for col in columns:
            value = col[i] if i < len(col) else None
            previous = col[i - 1] if 0 < i <= len(col) else None
            if value is None or (value == 0 and previous not in (None, 0)):
                complete = False
                break
        if complete:
            return i
    return None


def get(client: httpx.Client, path: str, code: str = "", **params: str) -> dict | None:
    query = {"country": code, **params} if code else params
    for attempt in range(5):
        try:
            r = client.get(BASE + path, params=query)
        except httpx.TransportError as err:
            print(f"  {code or params}: {err.__class__.__name__}, retry", flush=True)
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


def price_now(data: dict, now: float) -> tuple[str, float] | None:
    """Day-ahead price of the interval that contains `now` (the feed runs into tomorrow)."""
    rows = [
        (t, p)
        for t, p in zip(data.get("unix_seconds", []), data.get("price", []), strict=False)
        if p is not None and t <= now
    ]
    if not rows:
        return None
    t, p = rows[-1]
    return datetime.fromtimestamp(int(t), tz=UTC).isoformat(), round(float(p), 2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT, help="output directory")
    out: Path = parser.parse_args().out
    borders: dict[frozenset[str], dict] = {}
    stats: dict[str, dict] = {}
    prices: dict[str, dict] = {}
    unknown: set[str] = set()
    now = datetime.now(UTC)
    series_start = int((now - timedelta(hours=24)).timestamp()) // STEP * STEP
    steps = (int(now.timestamp()) - series_start) // STEP + 1
    window = {
        "start": (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%MZ"),
        "end": now.strftime("%Y-%m-%dT%H:%MZ"),
    }
    with httpx.Client(timeout=90, headers={"User-Agent": "Germany-InfraAtlas/0.1"}) as client:
        eu = power(get(client, "/public_power", "eu") or {})
        time.sleep(3)
        for code in CODES:
            home = code.upper()
            pp = get(client, "/public_power", code)
            time.sleep(3)
            if pp and (row := power(pp)):
                stats[home] = row
            data = get(client, "/cbpf", code, **window)
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
                # 24 h series on a common 15-min grid, up to the newest complete interval
                values: list[float | None] = [None] * steps
                for k, (sec, v) in enumerate(zip(data["unix_seconds"], s["data"], strict=False)):
                    slot = (int(sec) - series_start) // STEP
                    if k <= i and v is not None and 0 <= slot < steps:
                        values[slot] = round(float(v) * 1000.0)
                borders[key] = {
                    "a": other,
                    "b": home,
                    "mw": round(import_mw, 1),
                    "ts": ts,
                    "reported_by": home,
                    "series": values,
                }
                added += 1
            print(
                f"{home}: {len(series)} neighbours, {added} new borders, interval {ts}", flush=True
            )
        for zone, iso in PRICE_ZONES.items():
            data = get(client, "/price", bzn=zone)
            time.sleep(3)
            if data and (row := price_now(data, now.timestamp())):
                prices[zone] = {"country": iso, "ts": row[0], "eur_mwh": row[1]}
        print(f"day-ahead prices for {len(prices)} of {len(PRICE_ZONES)} zones", flush=True)
    rows = sorted(borders.values(), key=lambda r: -abs(r["mw"]))
    fetched = datetime.now(UTC).isoformat(timespec="seconds")
    out.mkdir(parents=True, exist_ok=True)
    flows = {
        "source": SOURCE + ", cross-border physical flows",
        "fetched": fetched,
        # series[k] is the 15-min interval starting at series_start + k * 900 s
        "series_start": datetime.fromtimestamp(series_start, tz=UTC).isoformat(),
        "series_step_s": STEP,
        "borders": rows,
    }
    (out / "flows.json").write_text(json.dumps(flows, indent=1), encoding="utf-8")
    summary = {
        "source": SOURCE,
        "fetched": fetched,
        "eu": eu,
        "countries": stats,
        "day_ahead_prices": prices,
    }
    (out / "stats.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"{len(rows)} borders, {len(stats)} countries with power data, EU aggregate: {bool(eu)}")
    if unknown:
        print("neighbours outside the map (skipped):", ", ".join(sorted(unknown)))


if __name__ == "__main__":
    main()
