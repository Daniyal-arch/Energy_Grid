"""Probe GIE AGSI+ (gas storage) and Ember (yearly electricity data) with the keys in .env.

Small requests only: shapes, fields, date ranges, units.

    uv run python scripts/probe_gas_ember.py
"""

from __future__ import annotations

import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
AGSI = os.environ.get("AGSI_API_KEY", "")
EMBER = os.environ.get("EMBER_API_KEY", "")
client = httpx.Client(timeout=60)

print("== AGSI+ gas storage, EU aggregate and Germany")
for params in ({"type": "eu", "size": "3"}, {"country": "DE", "size": "3"}):
    r = client.get("https://agsi.gie.eu/api", params=params, headers={"x-key": AGSI})
    d = r.json()
    print(params, "HTTP", r.status_code, "last_page", d.get("last_page"), "total", d.get("total"))
    for row in d.get("data", [])[:2]:
        print(
            "  ",
            {
                k: row.get(k)
                for k in (
                    "name",
                    "code",
                    "gasDayStart",
                    "gasInStorage",
                    "full",
                    "trend",
                    "workingGasVolume",
                    "injection",
                    "withdrawal",
                    "unit",
                )
            },
        )

print("\n== Ember API: endpoints")
r = client.get("https://api.ember-energy.org/v1/", params={"api_key": EMBER})
print("root HTTP", r.status_code, r.text[:300])
for path, params in (
    (
        "electricity-generation/yearly",
        {"entity_code": "DEU", "start_date": "2023", "is_aggregate_series": "false"},
    ),
    (
        "electricity-generation/yearly",
        {"entity_code": "FRA", "start_date": "2000", "end_date": "2000"},
    ),
    ("carbon-intensity/yearly", {"entity_code": "DEU", "start_date": "2023"}),
):
    r = client.get(f"https://api.ember-energy.org/v1/{path}", params={**params, "api_key": EMBER})
    print(f"\n{path} {params} HTTP {r.status_code}")
    try:
        d = r.json()
    except json.JSONDecodeError:
        print("  ", r.text[:300])
        continue
    rows = d.get("data", d if isinstance(d, list) else [])
    print(
        "  keys:", list(d.keys()) if isinstance(d, dict) else type(d).__name__, "rows:", len(rows)
    )
    for row in rows[:4]:
        print("  ", row)
