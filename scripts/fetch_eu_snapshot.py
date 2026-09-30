"""Snapshot of physical cross-border electricity flows across Europe.

Asks Energy-Charts (/cbpf, ENTSO-E physical flows as published by Fraunhofer ISE)
once per country, one request at a time because the API answers 429 to bursts.
Each border is reported by both sides; the value is taken from the first country
that has it for the newest complete interval (sign flipped as needed). Values
are passthrough: no netting, no modelling.

Writes frontend/public/data/eu/flows.json:
  {"source", "fetched", "borders": [{"a", "b", "mw", "ts", "reported_by"}]}
  mw > 0 means power flows from a to b.

    uv run python scripts/fetch_eu_flows.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.power_live import newest_complete_index  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "eu" / "flows.json"
BASE = "https://api.energy-charts.info/cbpf"

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


def get(client: httpx.Client, code: str) -> dict | None:
    for attempt in range(5):
        try:
            r = client.get(BASE, params={"country": code})
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


def main() -> None:
    borders: dict[frozenset[str], dict] = {}
    unknown: set[str] = set()
    with httpx.Client(timeout=90, headers={"User-Agent": "Germany-InfraAtlas/0.1"}) as client:
        for code in CODES:
            home = code.upper()
            data = get(client, code)
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
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "source": "Energy-Charts (Fraunhofer ISE), cross-border physical flows (ENTSO-E)",
                "fetched": datetime.now(UTC).isoformat(timespec="seconds"),
                "borders": rows,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"{len(rows)} borders -> {OUT}")
    if unknown:
        print("neighbours outside the map (skipped):", ", ".join(sorted(unknown)))


if __name__ == "__main__":
    main()
