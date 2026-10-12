"""Probe GIE ALSI per terminal: the listing of companies and facilities, one terminal's rows.

uv run python scripts/probe_alsi_terminals.py
"""

from __future__ import annotations

import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ.get("AGSI_API_KEY", "").strip()
URL = "https://alsi.gie.eu/api"

c = httpx.Client(timeout=60, headers={"x-key": KEY})

print("== listing")
r = c.get(f"{URL}/about", params={"show": "listing"})
print("HTTP", r.status_code, r.headers.get("content-type"), len(r.content), "bytes")
listing = r.json()
print("top type", type(listing).__name__, list(listing)[:5] if isinstance(listing, dict) else "")
print(json.dumps(listing, ensure_ascii=False)[:1500])

# find the first facility in the listing, whatever its shape
facilities: list[tuple[str, str, str, dict]] = []


def walk(node: object, country: str = "", company: str = "") -> None:
    if isinstance(node, dict):
        if "facilities" in node:
            comp = node.get("eic") or node.get("company") or company
            for f in node["facilities"]:
                facilities.append((node.get("country") or country, comp, f.get("eic", ""), f))
        for k, v in node.items():
            walk(v, k if len(str(k)) == 2 else country, company)
    elif isinstance(node, list):
        for v in node:
            walk(v, country, company)


walk(listing)
print("\nfacilities found:", len(facilities))
for row in facilities[:40]:
    print("  ", row[0], row[1], row[2], {k: v for k, v in row[3].items() if k != "eic"})

if facilities:
    country, company, eic, _ = facilities[0]
    print("\n== one terminal, last 3 days:", country, company, eic)
    r = c.get(URL, params={"country": country, "company": company, "facility": eic, "size": "3"})
    print("HTTP", r.status_code)
    d = r.json()
    print({k: d.get(k) for k in ("last_page", "total", "dataset")})
    for row in d.get("data", [])[:3]:
        print("  ", json.dumps(row, ensure_ascii=False)[:800])
