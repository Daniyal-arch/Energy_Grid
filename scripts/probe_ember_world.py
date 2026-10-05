"""Probe Ember's API for a world-wide transition map (Transition tab).

1. One request without an entity: are all countries returned (paging, row count)?
2. Several entity codes in one request (comma-separated)?
3. Which aggregate series exist (e.g. "Wind and solar", "Fossil", "Clean")?
4. Does world.json carry ISO codes we can join on?

  uv run python scripts/probe_ember_world.py
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ["EMBER_API_KEY"]
URL = "https://api.ember-energy.org/v1"
c = httpx.Client(timeout=120)

print("== 1. all entities, one year")
t0 = time.monotonic()
r = c.get(
    f"{URL}/electricity-generation/yearly",
    params={"start_date": "2024", "end_date": "2024", "api_key": KEY},
)
d = r.json()
rows = d.get("data", [])
print(f"HTTP {r.status_code} in {time.monotonic() - t0:.1f}s, rows {len(rows)}, keys {list(d)[:6]}")
ents = sorted(
    {(x["entity"], x["entity_code"], x["is_aggregate_entity"]) for x in rows},
    key=lambda e: str(e[1]),
)
print(
    f"entities {len(ents)}: countries {sum(not e[2] for e in ents)}, aggregates {[e[0] for e in ents if e[2]][:25]}"
)
print("series:", sorted({(x["series"], x["is_aggregate_series"]) for x in rows}))

print("\n== 2. comma-separated entity codes, 2000-2025")
r = c.get(
    f"{URL}/electricity-generation/yearly",
    params={"entity_code": "DEU,FRA,CHN", "start_date": "2000", "api_key": KEY},
)
rows = r.json().get("data", [])
print(
    f"HTTP {r.status_code}, rows {len(rows)}, entities {sorted({x['entity_code'] for x in rows})}"
)

print("\n== 3. carbon intensity, all entities, 2000-2025")
t0 = time.monotonic()
r = c.get(f"{URL}/carbon-intensity/yearly", params={"start_date": "2000", "api_key": KEY})
rows = r.json().get("data", [])
print(f"HTTP {r.status_code} in {time.monotonic() - t0:.1f}s, rows {len(rows)}, sample {rows[:1]}")

print("\n== 4. world.json properties")
w = json.loads(
    (Path(__file__).resolve().parents[1] / "frontend/public/data/eu/world.json").read_text(
        encoding="utf-8"
    )
)
print(w["features"][0]["properties"], len(w["features"]))
