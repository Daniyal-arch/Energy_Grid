"""Probe Energy-Charts for one complete past day (input for the 24 h Europe time-lapse).

Checks resolution and completeness of /price, /public_power and /cbpf when asked with
start/end for a whole day.

    uv run python scripts/probe_eu_day.py 2026-10-02
"""

from __future__ import annotations

import sys
import time
from datetime import UTC, datetime

import httpx

BASE = "https://api.energy-charts.info"
day = sys.argv[1] if len(sys.argv) > 1 else "2026-10-02"
window = {"start": f"{day}T00:00Z", "end": f"{day}T23:59Z"}
client = httpx.Client(timeout=90)


def get(path: str, **params: str) -> dict | None:
    for _ in range(5):
        try:
            r = client.get(BASE + path, params={**params, **window})
        except httpx.TransportError:
            time.sleep(10)
            continue
        if r.status_code == 429:
            time.sleep(float(r.headers.get("retry-after") or 10) + 2)
            continue
        return r.json() if r.status_code == 200 else None
    return None


def span(seconds: list[int]) -> str:
    if not seconds:
        return "no timestamps"
    step = seconds[1] - seconds[0] if len(seconds) > 1 else 0
    first = datetime.fromtimestamp(seconds[0], tz=UTC).strftime("%H:%M")
    last = datetime.fromtimestamp(seconds[-1], tz=UTC).strftime("%H:%M")
    return f"{len(seconds)} points, step {step} s, {first}-{last} UTC"


for zone in ["DE-LU", "FR", "IT-North", "NO2"]:
    d = get("/price", bzn=zone)
    time.sleep(3)
    if d:
        nones = sum(v is None for v in d["price"])
        print(
            f"price {zone}: {span(d['unix_seconds'])}, missing {nones}, min {min(v for v in d['price'] if v is not None)}"
        )

for country in ["eu", "fr", "pl", "it"]:
    d = get("/public_power", country=country)
    time.sleep(3)
    if d:
        names = {s["name"]: s["data"] for s in d["production_types"]}
        solar = names.get("Solar", [])
        print(
            f"public_power {country}: {span(d['unix_seconds'])}; "
            f"solar missing {sum(v is None for v in solar)}, "
            f"has load {'Load' in names}, has share {'Renewable share of generation' in names}"
        )

for country in ["fr", "de"]:
    d = get("/cbpf", country=country)
    time.sleep(3)
    if d:
        missing = {s["name"]: sum(v is None for v in s["data"]) for s in d["countries"]}
        print(f"cbpf {country}: {span(d['unix_seconds'])}; missing per neighbour {missing}")
