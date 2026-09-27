"""Probe the Electricity Maps API (v3) with the configured trial key.

Goal: figure out exactly what data is available for Germany (DE zone) so we
can design the gridwatch data model + UI around real response shapes, not
guesses. Hits the documented v3 REST endpoints:
  - GET /v3/zones                          zone catalogue (confirm DE naming)
  - GET /v3/carbon-intensity/latest         live gCO2eq/kWh
  - GET /v3/carbon-intensity/forecast       forecast gCO2eq/kWh
  - GET /v3/power-breakdown/latest          live generation mix + cross-border
                                             import/export breakdown
  - GET /v3/power-breakdown/forecast        forecast generation mix
  - GET /v3/power-breakdown/history         recent history (for context)

Auth: `auth-token` header (per electricitymaps developer docs). If that 401s,
the script retries with `?auth-token=` query param as a fallback.
"""

from __future__ import annotations

import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ["Electricty_Maps"]
BASE = "https://api.electricitymaps.com/v3"
ZONE = "DE"


def call(path: str, **params) -> httpx.Response:
    headers = {"auth-token": KEY}
    r = httpx.get(f"{BASE}{path}", headers=headers, params=params, timeout=30)
    if r.status_code == 401:
        params = {**params, "auth-token": KEY}
        r = httpx.get(f"{BASE}{path}", params=params, timeout=30)
    return r


def show(label: str, r: httpx.Response, max_chars: int = 1800) -> None:
    print(f"\n=== {label} === HTTP {r.status_code}")
    try:
        body = json.dumps(r.json(), indent=2)
    except Exception:
        body = r.text
    print(body[:max_chars] + ("... [truncated]" if len(body) > max_chars else ""))


def main() -> None:
    show("zones", call("/zones"))
    show("carbon-intensity/latest", call("/carbon-intensity/latest", zone=ZONE))
    show("carbon-intensity/forecast", call("/carbon-intensity/forecast", zone=ZONE))
    show("power-breakdown/latest", call("/power-breakdown/latest", zone=ZONE))
    show("power-breakdown/forecast", call("/power-breakdown/forecast", zone=ZONE))
    show("power-breakdown/history", call("/power-breakdown/history", zone=ZONE))


if __name__ == "__main__":
    main()
